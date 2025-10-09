{
    'name': 'Product Quantity and Cost Tracing',
    'version': '0.1.0',
    'summary': 'Trace the change on quantity and cost of products',
    'description': """
        Trace the change on quantity and cost of products
    """,
    'category': 'Inventory/Inventory',
    'author': 'Iyad Husary',
    'depends': ['stock', 'account', 'purchase', 'sale_management', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_init_hook': 'post_init_hook',
}