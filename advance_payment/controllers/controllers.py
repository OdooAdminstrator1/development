# -*- coding: utf-8 -*-
# from odoo import http


# class AdvancePayment(http.Controller):
#     @http.route('/advance_payment/advance_payment/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/advance_payment/advance_payment/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('advance_payment.listing', {
#             'root': '/advance_payment/advance_payment',
#             'objects': http.request.env['advance_payment.advance_payment'].search([]),
#         })

#     @http.route('/advance_payment/advance_payment/objects/<model("advance_payment.advance_payment"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('advance_payment.object', {
#             'object': obj
#         })
