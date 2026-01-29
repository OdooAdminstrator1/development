{
    'name': 'Business Data Analysis',
    'version': '1.4.0',
    'summary': 'Trace the change on quantity and cost of products',
    'description': """
        Trace the change on quantity and cost of products
    """,
    'category': 'Inventory/Inventory',
    'author': 'Iyad Husary',
    'depends': ['base', 'product','web','stock', 'account', 'purchase', 'sale_management', 'mrp'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/stock_product_trace_wizard.xml',
        'views/res_config_settings_views.xml',
        'views/product_view.xml',
        'views/invoice_view.xml',
        'views/mrp_bom_views.xml',
        'views/cearance.xml',
        'views/cearance_stockout.xml',
        'views/clearance_landed_stockin.xml',
    ],
    'images': ['static/description/icon.png'],
    'assets': {
    'web.assets_backend': [
        'prod_qnt_cost_tracing/static/src/js/list_custom_renderer.js',
        'prod_qnt_cost_tracing/static/src/js/stock_product_trace.js',
        'prod_qnt_cost_tracing/static/src/css/list_custom.css',
    ],
    'web.assets_qweb':['prod_qnt_cost_tracing/static/src/xml/stock_product_trace_buttons.xml'],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'post_init_hook': 'post_init_hook',
}
