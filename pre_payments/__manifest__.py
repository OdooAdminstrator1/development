# -*- coding: utf-8 -*-
{
    'name': "Advance Payments",
    'summary': "Manage advance payments and custom payment popovers",
    'author': "HMID",
    'category': 'Accounting/Payment Acquirers',
    'version': '16.0.0.2',  # Best practice: prefix with Odoo version
    'license': 'LGPL-3',    # Added license key

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'web'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            # Ensure 'pre_payments' matches your actual folder name
            'pre_payments/static/src/xml/payment_popover.xml', 
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
