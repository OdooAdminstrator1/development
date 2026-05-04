# -*- coding: utf-8 -*-
{
    'name': "Purchase received/billed extension",
    'author': "HSIH",
    'category': 'Inventory/Purchase',
    'version': '0.1.0',

    # any module necessary for this one to work correctly
    'depends': ['purchase'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
