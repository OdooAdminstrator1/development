{
    "name": "Product Power & Current",
    "version": "17.0.1.0.0",
    "category": "Inventory/Product",
    "summary": "Adds Power and Current fields to product variants",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": ['base', 'product', 'web','stock','prod_qnt_cost_tracing','production_order',
    ],
    "data": [
        "views/product_product_views.xml",
    ],
    "assets": {
    'web.assets_backend': [
        'product_power_current/static/src/css/product_power_current.css',
        'product_power_current/static/src/css/product_filter.css',
        'product_power_current/static/src/js/product_filter_controller.js',
     #   'product_power_current/static/src/js/product_filter_panel.js',
        'product_power_current/static/src/xml/product_filter_controller.xml',
     #   'product_power_current/static/src/xml/product_filter_panel.xml',
         ],
    },

    "installable": True,
    "application": False,
}