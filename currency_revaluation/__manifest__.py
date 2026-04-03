# -*- coding: utf-8 -*-
{
    'name': "currency_revaluation",

    'summary': "",

    'description': "",

    'author': "MHD Ali",
    'website': "",


    # for the full list
    'category': 'accounting',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','account_reports','account_accountant'],

    # always loaded
    'data': [
         'security/ir.model.access.csv',
        'views/views.xml',
    ],
    # only loaded in demonstration mode
    # 'demo': [
    #     'demo/demo.xml',
    # ],
}
