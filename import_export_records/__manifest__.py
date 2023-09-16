# -*- coding: utf-8 -*-
{
    'name': "Import Export Records",
    'summary': "Simplify multi-model record export with templates and filters.",
    'description': "This module simplifies the process of exporting multiple records from various models by providing a flexible template-based approach, allowing users to define export templates and filter records using domains.",
    'category': 'Technical',
    'version': '0.0.1',
    'author': "Victor Hachard",
    'license': 'LGPL-3',
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
