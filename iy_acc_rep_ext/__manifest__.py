{
    'name': 'Missing init balancd',
    'version': '0.9.0',
    'summary': 'Restore missing column "Initial Balance" ',
    'description': """
        Odoo new version deprecate a feature to show the 'initial balance' in report Balance Sheet
    """,
    'category': 'Accounting/Accounting',
    'author': 'Iyad Husary',
    'depends': ['account_accountant','account_reports'],
    'data': [
        'views/partner_ledger_columns.xml',
    ],
        'qweb': [
    ],
    'installable': True,
    'license': 'LGPL-3',
    'application': False,
    'auto_install': False,
}