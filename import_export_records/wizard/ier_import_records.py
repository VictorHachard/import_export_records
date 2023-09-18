# -*- coding: utf-8 -*-
import base64
import csv
import io
import json
import zipfile

from odoo import models, fields, exceptions, _, api


class IERImportWizard(models.TransientModel):
    _name = 'ier.import.wizard'
    _description = 'IER Import Wizard'

    zip_file = fields.Binary(string='Upload your File', required=True)
    zip_file_name = fields.Char("File Name")

    error_html = fields.Html()
    warning_html = fields.Html()
    success_html = fields.Html()

    # Manifest
    is_importable = fields.Boolean(compute='_compute_manifest_data', store=True)
    manifest_datetime = fields.Datetime(compute='_compute_manifest_data', string='Created At', store=True)
    manifest_dbname = fields.Char(compute='_compute_manifest_data', string='From Database', store=True)
    manifest_username = fields.Char(compute='_compute_manifest_data', string='By User', store=True)
    manifest_userlogin = fields.Char(compute='_compute_manifest_data', store=True)
    manifest_export = fields.Html(compute='_compute_manifest_data', store=True)
    manifest_record_count = fields.Integer(compute='_compute_manifest_data', store=True)
    manifest_post_process_code = fields.Text(compute='_compute_manifest_data', store=True)

    def _reopen_self(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "name": self._description,
            "view_mode": "form",
            "target": "new",
        }

    def _import_record_and_execute(self, model, decoded_csv, fields):
        """
        Import record and execute the action
        """
        import_record = self.env['base_import.import'].create({
            'res_model': model,
            'file': decoded_csv,
            'file_type': 'text/csv',
            'file_name': model,
        })
        result = import_record.execute_import(
            fields,
            fields,
            {'quoting': '"', 'separator': ',', 'has_headers': True},
            False
        )
        return result

    @api.depends('zip_file')
    def _compute_manifest_data(self):
        for rec in self:
            rec.update({
                'manifest_datetime': False,
                'manifest_dbname': '',
                'manifest_username': '',
                'manifest_userlogin': '',
                'manifest_export': '',
                'manifest_record_count': 0,
                'manifest_post_process_code': '',
                'is_importable': False,
            })
            if rec.zip_file:
                decoded_zip = base64.b64decode(rec.zip_file)
                io_bytes_zip = io.BytesIO(decoded_zip)

                if zipfile.is_zipfile(io_bytes_zip):
                    with zipfile.ZipFile(io_bytes_zip, mode="r") as archive:
                        manifest_content = next((archive.read(name) for name in archive.namelist() if name == "manifest.json"), None)
                        if manifest_content is not None:
                            rec._set_manifest_field(json.loads(manifest_content))

    def _set_manifest_field(self, data):
        def wrap_field_with_badge(field):
            return f'<span class="badge ier_badge">{field}</span>'
        table_html = '<table>'
        table_html += '<tr><th>Export Name</th><th>Model Name</th><th>Fields</th></tr>'
        for export in data.get('ir_exports', []):
            export_name = export.get('name', '')
            model_name = export.get('model_name', '')
            field = ''.join([wrap_field_with_badge(field) for field in export.get('fields', [])])
            table_html += f'<tr><td>{export_name}</td><td>{model_name}</td><td>{field}</td></tr>'
        table_html += '</table>'

        self.update({
            'manifest_datetime': data.get('datetime', False),
            'manifest_dbname': data.get('dbname', ''),
            'manifest_username': data.get('username', ''),
            'manifest_userlogin': data.get('userlogin', ''),
            'manifest_export': table_html,
            'manifest_record_count': data.get('record_count', 0),
            'manifest_post_process_code': data.get('post_process_code', ''),
            'is_importable': True,
        })

    def import_action(self):
        if self.zip_file:
            self.success_html = False
            error_html, warning_html = '', ''

            record_count = 0
            decoded_zip = base64.b64decode(self.zip_file)
            io_bytes_zip = io.BytesIO(decoded_zip)

            if zipfile.is_zipfile(io_bytes_zip):
                with zipfile.ZipFile(io_bytes_zip, mode="r") as archive:
                    csv_files = {name: archive.read(name) for name in archive.namelist() if '.csv' in name}
                    for model, csv_file in csv_files.items():
                        decoded_csv = csv_file.decode()
                        io_string_csv = io.StringIO(decoded_csv)
                        csvreader = csv.reader(io_string_csv)
                        headers = next(csvreader)
                        model_name = '.'.join(model.split('.')[1:-1])
                        result = self._import_record_and_execute(model_name, decoded_csv, headers)
                        record_count += len(result['ids']) if result['ids'] else 0

                        if result and 'messages' in result and len(result['messages']) > 0:
                            for msg in result['messages']:
                                if msg['type'] == 'warning':
                                    if msg['field']:
                                        warning_html += f"<tr><td>{model_name}</td><td>{msg['field']}</td><td>{msg['record']}</td><td>{msg['message']}</td></tr>\n"
                                    else:
                                        warning_html += f"<tr><td colspan='3'>{model_name}</td><td>{msg['message']}</td></tr>\n"
                                else:
                                    if msg['field']:
                                        error_html += f"<tr><td>{model_name}</td><td>{msg['field']}</td><td>{msg['record']}</td><td>{msg['message']}</td></tr>\n"
                                    else:
                                        error_html += f"<tr><td colspan='3'>{model_name}</td><td>{msg['message']}</td></tr>\n"

            self.error_html = "<table><tr><th>Model</th><th>Field</th><th>Record</th><th>Message</th></tr>" + error_html + "</table>" if error_html else ''
            self.warning_html = "<table><tr><th>Model</th><th>Field</th><th>Record</th><th>Message</th></tr>" + warning_html + "</table>" if warning_html else ''
            self.success_html = f"<p>{_('%s records successfully imported', str(record_count))}</p>"
            return self._reopen_self()
