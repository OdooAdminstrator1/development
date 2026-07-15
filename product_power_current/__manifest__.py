{
    "name": "Product Power & Current",
    "version": "17.0.1.0.0",
    "category": "Inventory/Product",
    "summary": "Adds Power and Current fields to product variants",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": [
        "product",
    ],
    "data": [
        "views/product_product_views.xml",
    ],
    "assets": {
    'web.assets_backend': [
        'product_power_current/static/src/css/product_power_current.css',
         ],
    },
    "installable": True,
    "application": False,
}