{
    'name': "Deliver Extension",
    'author': "IH",
    'category': 'Accounting/Payment Acquirers',
    
    'version': '17.0.1.1',
    'depends': ['production_order','stock','sale_stock'],
    'data': [
        'views/views.xml',
        'views/report_delivery_note.xml',
        'views/sale_order_views.xml',
        'views/report_sale_invoice.xml',
    ],
}
