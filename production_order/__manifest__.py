# -*- coding: utf-8 -*-
{
    'name': "Production order",
    'author': "Iyad Husary",
    'category': "Sales/CRM",
    'version': '0.2.1',

    'summary': 'Custom Production Order linked with CRM Opportunities',
    'depends': ['crm', 'sale_management', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/productview.xml',
        'views/crmleadview.xml',
    ],
    'images': ['static/description/icon2.png'],
    'installable': True,
    'application': True,

}
