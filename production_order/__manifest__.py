{
    'name': "Production order",
    'author': "Iyad Husary",
    'category': "Sales/CRM",
    'version': '0.2.0',

    'summary': 'Custom Production Order linked with CRM Opportunities',
    'depends': ['crm', 'sale_management', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': True,

}

