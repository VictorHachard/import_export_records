# -*- coding: utf-8 -*-
import base64
import csv
import io
import zipfile

from odoo import models, fields, exceptions, _


class IERImportWizard(models.TransientModel):
    _name = 'ier.import.wizard'
    _description = 'IER Import Wizard'

    zip_file = fields.Binary(string='Upload your File', required=True)
    zip_file_name = fields.Char("File Name", readonly=True)

    error_html = fields.Html(default="<p></p>")
    warning_html = fields.Html(default="<p></p>")

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

    def import_action(self):
        # TODO: delete zip file after import
        if self.zip_file:
            error_html = "<p></p>"
            warning_html = "<p></p>"

            record_count = 0
            decoded_zip = base64.b64decode(self.zip_file)
            io_bytes_zip = io.BytesIO(decoded_zip)

            if zipfile.is_zipfile(io_bytes_zip):
                with zipfile.ZipFile(io_bytes_zip, mode="r") as archive:
                    csv_files = {name: archive.read(name) for name in archive.namelist()}
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

                    # Create the complete HTML message
                    self.error_html = "<table><tr><th>Model</th><th>Field</th><th>Record</th><th>Message</th></tr>" + error_html + "</table>" if error_html else ''
                    self.warning_html = "<table><tr><th>Model</th><th>Field</th><th>Record</th><th>Message</th></tr>" + warning_html + "</table>" if warning_html else ''

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _('%s records successfully imported', str(record_count)),
                    'sticky': False,
                }
            }
