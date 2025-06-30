{
    'name': 'Purchase Order Validation Notification',
    'version': '0.1.0',
    'summary': 'Send configurable email notifications on PO validation',
    'description': """
        Allows configuration of users to notify when a purchase order is validated.
    """,
    'category': 'Inventory/Purchase',
    'author': 'Iyad Husary',
    'depends': ['purchase'],
    'data': [
        'views/notification_config_views.xml',
 #       'views/email_templates.xml',
        'data/mail_template.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
}