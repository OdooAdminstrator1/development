# -*- coding: utf-8 -*-
{
    'name': "Advance Payments",
    'author': "HMID",
    'category': 'Accounting/Payment Acquirers',
    'version': '0.2',

    # any module necessary for this one to work correctly
    'depends': ['base','account','web'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        # 'views/views.xml',
    ],
    'qweb': [
    ],
    'assets': {
        'web.assets_qweb': [
            'pre_payments/static/src/xml/**/*',
        ],
    },
}
