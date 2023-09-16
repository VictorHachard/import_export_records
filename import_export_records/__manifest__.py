# -*- coding: utf-8 -*-
{
    'name': "Import Export Records",
    'summary': "",
    'description': "",
    'category': 'Technical',
    'version': '0.0.1',
    'author': "Victor Hachard",
    'license': 'OPL-1',
    'price': 0,
    'currency': 'EUR',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/res_groups.xml',

        'data/ier_exports.xml',

        'wizard/ier_export_records.xml',
        'wizard/ier_import_records.xml',

        'views/ier_template.xml',

        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'import_export_records/static/src/backend.scss',
        ],
    },
    'installable': True,
    'application': True,
}
