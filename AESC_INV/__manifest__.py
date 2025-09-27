{
    'name': 'AESCO Invoice Layout',
    'version': '1.0.0',
    'summary': 'Custom invoice layout for Advanced Energy Solutions Company',
    'description': """
        Customizes the invoice report to match AESCO requirements
    """,
    'category': 'Accounting',
    'author': 'Iyad Husary',
    'depends': ['account'],
    'data': [
    #    'views/report_templates.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
