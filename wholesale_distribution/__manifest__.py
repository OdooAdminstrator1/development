{
    'name': 'Wholesale Distribution',
    'version': '19.0.1.0.0',
    'category': 'Sales/Distribution',
    'summary': 'Mobile/retail wholesale distribution with a custom transactional buffer on top of sale.order',
    'description': """
Wholesale Distribution
=========================

Custom transactional buffer framework for distributing products to retailers via
mobile outlets (trucks) and retail outlets (shops).

The distributor creates distribution sale orders from a mobile app. Those orders:

* take a dedicated sequence (not the standard sale.order sequence),
* never generate a delivery picking or an invoice on confirmation,
* are isolated from the standard Sales app through record rules.

Inventory is moved through an explicit multi-leg pipeline (Charge -> Run close ->
End-of-day aggregation) and the accounting ledger is kept "clean" by emitting a
single master sale order / invoice at the end of the day.
""",
    'author': 'Mustafa Mustafa',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'sale_management',
        'sale_stock',
        'stock',
        'account',
    ],
    'data': [
        'security/distribution_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/distribution_data.xml',
        'views/res_config_settings_views.xml',
        'views/distribution_outlet_views.xml',
        'views/distribution_payment_views.xml',
        'views/distribution_delivery_run_views.xml',
        'views/sale_order_views.xml',
        'views/hr_employee_views.xml',
        'wizards/distribution_batch_wizard_views.xml',
        'views/distribution_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'wholesale_distribution/static/src/scss/cashier_intake.scss',
        ],
    },
    'application': True,
    'installable': True,
}
