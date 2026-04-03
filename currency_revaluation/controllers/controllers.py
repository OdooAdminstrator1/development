# -*- coding: utf-8 -*-
# from odoo import http


# class SappsCurrencyRevaluation(http.Controller):
#     @http.route('/currency_revaluation/currency_revaluation/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/currency_revaluation/currency_revaluation/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('currency_revaluation.listing', {
#             'root': '/currency_revaluation/currency_revaluation',
#             'objects': http.request.env['currency_revaluation.currency_revaluation'].search([]),
#         })

#     @http.route('/currency_revaluation/currency_revaluation/objects/<model("currency_revaluation.currency_revaluation"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('currency_revaluation.object', {
#             'object': obj
#         })
