# -*- coding: utf-8 -*-
{
    'name': "sapps_netc_dashboard",

    'summary': """
        AESP Dashboard""",

    'description': """
        Report for sales, production, onhand quantity, cash flow and partner ledger
    """,

    'author': "SAPPS",
    'website': "http://s-apps.io",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'mrp', 'sale', 'stock', 'sale_stock', 'ict_overhead_expenses', 'account_reports'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/stock_location_view.xml',
        'views/finished_product_view.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'sapps_netc_dashboard/static/src/js/dashboard.js',
            'sapps_netc_dashboard/static/src/js/bootstrap-select.min.js',
            'sapps_netc_dashboard/static/src/css/bootstrap-select.min.css',
            'sapps_netc_dashboard/static/src/css/dashboard.css',

        ],
        'web.assets_qweb': [
            'sapps_netc_dashboard/static/src/xml/*',
        ],
    },
}
