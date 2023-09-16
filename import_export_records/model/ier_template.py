# -*- coding: utf-8 -*-
import base64
import io
import zipfile
from datetime import datetime, timezone

from odoo import models, fields, _, api
from odoo.exceptions import UserError
from odoo.tools import pytz


class IERTemplate(models.Model):
    _name = 'ier.template'
    _description = 'IER Template'

    name = fields.Char(required=True)
    lines = fields.One2many('ier.template.line', 'ier_template_id', context={'active_test': False})
    model_ids = fields.Many2many('ir.model', compute='_compute_model_ids', string='Models')
    import_compat = fields.Boolean(string='Import Compatible Export', default=False)

    @api.depends('lines.model_id')
    def _compute_model_ids(self):
        for rec in self:
            rec.model_ids = rec.lines.model_id.ids

    def export(self):
        """
        Prepares and exports data in CSV format for current template.
        It then compresses the CSV files into a ZIP archive and creates an attachment for download.
        """
        self.lines._check_ir_exports_id()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w") as zip_archive:
            for line in self.lines.filtered(lambda l: l.active):
                zip_archive.writestr(line.file_name + '.csv', line.export_files())

        datetime_str = datetime.now(timezone.utc).astimezone(pytz.timezone('Europe/Brussels')).strftime("%Y%m%d-%H%M%S")
        zip_filename = self.name.lower().replace(' ', '-') + '-' + datetime_str + '.zip'

        attachment_id = self.env['ir.attachment'].create({
            'name': zip_filename,
            'datas': base64.b64encode(zip_buffer.getvalue()),
            'res_model': 'ier.template',
            'res_id': self.id
        })
        self.env['ir.attachment']._file_delete(attachment_id.store_fname)  # TODO: test this

        return {
            'type': 'ir.actions.act_url',
            'url': "web/content/?model=ir.attachment&id=" + str(
                attachment_id.id) + "&filename_field=name&field=datas&download=true&name=" + attachment_id.name,
            'target': 'self',
        }

    def copy_data(self, default=None):
        if default is None:
            default = {}
        if 'lines' not in default:
            default['lines'] = [(0, 0, line.copy_data()[0]) for line in self.lines]
        return super().copy_data(default)

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = dict(default or {})
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        return super().copy(default=default)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_ier_exports_ier(self):
        ier_exports_ier = self.env.ref('import_export_records.ier_exports_ier')
        if ier_exports_ier in self:
            raise UserError(_("You cannot delete this template."))
