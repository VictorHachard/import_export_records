# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging

from pytz import timezone

import odoo
from odoo import api, fields, models, tools, _, Command
from odoo.exceptions import MissingError, ValidationError, AccessError, UserError
from odoo.tools import pycompat, safe_eval
from odoo.tools.safe_eval import safe_eval, test_python_expr
from odoo.tools.float_utils import float_compare


_logger = logging.getLogger(__name__)


DEFAULT_PYTHON_CODE = """# Available variables:
#  - env
#  - model: current model
#  - records: recordset of all records from the model; may be void
#  - time, datetime, dateutil, timezone: useful Python libraries
#  - float_compare: Odoo function to compare floats based on specific precisions
#  - UserError: Warning Exception to use with raise
#  - uid, user: current user id and user record
# Return records in an ID list, assign: action = {'records': [ids]}\n\n\n\n"""


class IERTemplateLine(models.Model):
    _name = 'ier.template.line'
    _description = 'IER Template Line'

    def _default_sequence(self):
        record = self.search([], limit=1, order="sequence DESC")
        return record.sequence + 1 if record else 1

    sequence = fields.Integer(default=_default_sequence)
    ier_template_id = fields.Many2one('ier.template', required=True, ondelete='cascade')
    ir_exports_id = fields.Many2one('ir.exports', string='Exports Template')

    active = fields.Boolean(default=True)

    model_id = fields.Many2one('ir.model', compute='_compute_model_id', store=True)
    model_name = fields.Char(compute='_compute_model_id', store=True)
    file_name = fields.Char(compute='_compute_file_name', store=True)

    mode = fields.Selection([('easy', 'Simple'), ('advanced', 'Advanced')], required=True, default='easy')
    filter_domain = fields.Char()
    code = fields.Text(string='Python Code', default=DEFAULT_PYTHON_CODE,
                       help="Write Python code that the action will execute. Some variables are "
                            "available for use; help about python expression is given in the help tab.")

    line_ids = fields.Many2many('ir.exports.line', compute='_compute_line_ids')

    def export_action(self):
        self.ensure_one()
        return self.template_id.export()

    def name_get(self):
        return [(record.id, f'{record.ir_exports_id.name} [{record.model_id.name}]') for record in self]

    @api.constrains('code')
    def _check_python_code(self):
        for action in self.sudo().filtered('code'):
            msg = test_python_expr(expr=action.code.strip(), mode="exec")
            if msg:
                raise ValidationError(msg)

    @api.depends('model_name', 'sequence')
    def _compute_file_name(self):
        for rec in self:
            rec.file_name = str(rec.sequence) + '.' + rec.model_name

    @api.depends('ir_exports_id')
    def _compute_line_ids(self):
        for rec in self:
            rec.write({'line_ids': [(6, 0, rec.ir_exports_id.export_fields.ids)]})

    @api.depends('ir_exports_id')
    def _compute_model_id(self):
        for rec in self:
            if rec.ir_exports_id:
                rec.model_id = self.env['ir.model'].search([('model', '=', rec.ir_exports_id.resource)])
                rec.model_name = rec.ir_exports_id.resource
            else:
                rec.model_id = False
                rec.model_name = ''

    @api.depends('ir_exports_id')
    def _onchange_ir_exports_id(self):
        for rec in self:
            rec.filter_domain = ''

    def _get_domain(self):
        return eval(self.filter_domain) if self.filter_domain else []

    def _get_export_fields(self):
        export_fields = self.ir_exports_id.export_fields.mapped('name')
        # if self.ier_template_id.import_compat and 'id' not in export_fields:
        #     export_fields.insert(0, 'id')
        return export_fields

    def _export_template(self):
        self.ensure_one()

        model = self.env[self.model_name]
        # if self.ier_template_id.import_compat:
        #     model.with_context(import_compat=True)

        if self.mode == 'advanced':
            action = self.run()
            if not action:
                raise UserError(_("The action is empty. Return records in an ID list, assign: action = {'records': [ids]}"))
            elif 'records' not in action or not action['records']:
                raise UserError(_('There is no record in the return action'))
            records = model.browse(action['records'])
        else:
            records = model.search(self._get_domain())

        datas = records.export_data(self._get_export_fields()).get('datas', [])
        return datas

    def export_files(self):
        self.ensure_one()

        csv_file = io.StringIO()
        writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        datas = self._export_template()
        writer.writerows([self._get_export_fields()])
        for data in datas:
            row = []
            for d in data:
                row.append(pycompat.to_text(d))
            writer.writerow(row)
        return csv_file.getvalue()

    @api.model
    def _get_eval_context(self):
        """ evaluation context to pass to safe_eval """
        return {
            'uid': self._uid,
            'user': self.env.user,
            'time': tools.safe_eval.time,
            'datetime': tools.safe_eval.datetime,
            'dateutil': tools.safe_eval.dateutil,
            'timezone': timezone,
            'float_compare': float_compare,
            # orm
            'env': self.env,
            'model': self.env[self.model_name],
            # Exceptions
            'Warning': odoo.exceptions.Warning,
            'UserError': odoo.exceptions.UserError,
            # record
            'records': self.env[self.model_name].search([]),
        }

    def _run_action_code_multi(self, eval_context):
        safe_eval(self.code.strip(), eval_context, mode="exec", nocopy=True, filename=str(self))  # nocopy allows to return 'action'
        return eval_context.get('action')

    def run(self):
        self.ensure_one()
        eval_context = self._get_eval_context()
        records = eval_context.get('records')
        if records:
            try:
                records.check_access_rule('write')
            except AccessError:
                _logger.warning("Forbidden server action %r executed while the user %s does not have access to %s.",
                                self.display_name, self.env.user.login, records,)
                raise
        run_self = self.with_context(eval_context['env'].context)
        res = run_self._run_action_code_multi(eval_context=eval_context)
        return res or False
