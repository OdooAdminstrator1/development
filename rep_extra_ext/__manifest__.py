{
    'name': 'AESCO Report Extension',
    'version': '0.9.0',
    'summary': 'Custom Reports layout for Advanced Energy Solutions Company',
    'description': """
        Customizes reports to match AESCO requirements
    """,
    'category': 'Inventory/Inventory',
    'author': 'Iyad Husary',
    'depends': ['web','stock'],
    'data': [
        'views/report_templates.xml',
    ],
    # 'assets': {'web.report_assets_common' : ['rep_extra_ext/static/src/css/report_stock.css',],

    # },
        'qweb': [
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}