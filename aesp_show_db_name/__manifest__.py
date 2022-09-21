# -*- coding: utf-8 -*-
{
    'name': "AESP_show_db_name",

    'summary': """
        show database name without enable dev
        """,

    'description': """
        show database name without enable dev
    """,

    'author': "Ali Haitham Ali",
    'website': "http://s-apps.io",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Hidden',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'web'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        # 'static/src/xml/user_menu.xml',
        # 'views/templates.xml',
    ],
    # 'assets': {
    #     'web.assets_qweb': [
    #         'aesp_show_db_name/static/src/xml/user_menu.xml',
    #     ]
    # }
}
