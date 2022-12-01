# -*- coding: utf-8 -*-
# from odoo import http


# class LedlightInvoiceWithQrcode(http.Controller):
#     @http.route('/ledlight_invoice_with_qrcode/ledlight_invoice_with_qrcode/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ledlight_invoice_with_qrcode/ledlight_invoice_with_qrcode/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('ledlight_invoice_with_qrcode.listing', {
#             'root': '/ledlight_invoice_with_qrcode/ledlight_invoice_with_qrcode',
#             'objects': http.request.env['ledlight_invoice_with_qrcode.ledlight_invoice_with_qrcode'].search([]),
#         })

#     @http.route('/ledlight_invoice_with_qrcode/ledlight_invoice_with_qrcode/objects/<model("ledlight_invoice_with_qrcode.ledlight_invoice_with_qrcode"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ledlight_invoice_with_qrcode.object', {
#             'object': obj
#         })
