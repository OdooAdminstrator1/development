# -*- coding: utf-8 -*-
{
    'name': "ict_accrual_expenses",

    'summary': """
        allow to add accrual bill """,

    'description': """
        it's offer a new type of bill (accrual bill) as a solution to adjust costing 
    """,

    'author': "Ali Haitham Ali",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Accounting/Accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account'],

    # always loaded
    'data': [
        #'security/ir.model.access.csv',
        'views/accrual_bill.xml',
        'views/matched_bills.xml',
        'data/journal_type.xml',
        'views/views.xml'
    ]
}
