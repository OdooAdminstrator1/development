# -*- coding: utf-8 -*-
{
    'name': "ict_overhead_expenses",

    'summary': """
        This Module compute the actual cost in a period maximum(3 months) and increase/decrease the valuation of manufactured product
        in this period accordingly and track the sold products""",

    'description': """
        This Module compute the actual cost in a period maximum(3 months) and increase/decrease the valuation of manufactured product
        in this period accordingly and track the sol products
    """,

    'author': "Ali Haitham Ali",
    'website': "http://sapps.io",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting/Accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'mrp', 'stock', 'stock_account', 'analytic', 'sale_stock'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/overhead_load_cost.xml',
        'views/res_config_settings_views.xml',
        'views/product_template_view.xml',
        'views/account_view_move_form.xml',
        'views/bom_view_form.xml',
        'views/stock_picking_inherited.xml',
        'views/account_analytic.line.xml',
        'wizard/ict_overhead_uncosted_journal.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,

}
