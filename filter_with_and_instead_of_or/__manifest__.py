# -*- coding: utf-8 -*-
{
    'name': "filter_with_and_instead_of_or",

    'summary': """
        To add ability to concat filters with AND operator instead of OR 
    """,

    'description': """
        To add ability to concat filters with AND operator instead of OR
    """,

    'author': "LED",
    'website': "LED",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Hidden',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['web'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        # 'views/views.xml',
        # 'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/filter_with_and_instead_of_or/static/src/js/control_panel_model_extensions_inherited.js',
            '/filter_with_and_instead_of_or/static/src/js/action_model_inherited.js'
        ]
    }

}
