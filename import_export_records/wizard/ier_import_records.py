# -*- coding: utf-8 -*-
import base64
import csv
import io
import zipfile
import re

import pytz
from datetime import datetime, timezone

from odoo import models, fields, exceptions, _
from odoo.tools import pycompat


def find_first_number_in_string(s: str) -> [int]:
    return list(map(int, re.findall('[0-9]+', s)))[0]


def sort_dict_by_list(un_dict, ordination: [str]) -> [int]:
    sorted_dict = dict()
    sorted_list = list((i, un_dict.get(i)) for i in ordination)
    for i in sorted_list:
        sorted_dict.setdefault(i[0], i[1])
    return sorted_dict


class IERImportWizard(models.TransientModel):
    _name = 'ier.import.wizard'
    _description = 'IER Import Wizard'

    zip_file = fields.Binary(string='Upload your File', required=True)
    zip_file_name = fields.Char("File Name", readonly=True)

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
                    result = self._import_record_and_execute('.'.join(model.split('.')[1:-1]), decoded_csv, headers)
                    record_count += len(result['name'])

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': str(record_count) + ' records successfully imported',
                    'sticky': True,
                }
            }
                    # if result and 'messages' in result and len(result['messages']) > 0:
                    #     for msg in result['messages']:
                    #         if msg['type'] == 'warning':
                    #             if msg['field']:
                    #                 self.warning_message += 'model: ' + model + ', field: ' + msg['field'] + ', record: ' + str(msg['record']) + ' -> ' + msg['message'] + '\n'
                    #             else:
                    #                 self.warning_message += 'model: ' + model + ' -> ' + msg['message'] + '\n'
                    #         else:
                    #             if msg['field']:
                    #                 self.error_message += 'model: ' + model + ', field: ' + msg['field'] + ', record: ' + str(msg['record']) + ' -> ' + msg['message'] + '\n'
                    #             else:
                    #                 self.warning_message += 'model: ' + model + ' -> ' + msg['message'] + '\n'
