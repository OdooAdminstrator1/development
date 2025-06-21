{
    'name': 'Purchase Order Validation Notification',
    'version': '1.0.1.0.0',
    'summary': 'Send configurable email notifications on PO validation',
    'description': """
        Allows configuration of users to notify when a purchase order is validated.
    """,
    'category': 'Inventory',
    'author': 'Iyad Husary',
    'depends': ['purchase'],
    'data': [
        'views/notification_config_views.xml',
        'views/email_templates.xml',
    ],
    'installable': True,
    'application': False,
}
