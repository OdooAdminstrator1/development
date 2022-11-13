# -*- coding: utf-8 -*-
# from odoo import http


# class IctOverheadExpenses(http.Controller):
#     @http.route('/ict_overhead_expenses/ict_overhead_expenses/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ict_overhead_expenses/ict_overhead_expenses/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('ict_overhead_expenses.listing', {
#             'root': '/ict_overhead_expenses/ict_overhead_expenses',
#             'objects': http.request.env['ict_overhead_expenses.ict_overhead_expenses'].search([]),
#         })

#     @http.route('/ict_overhead_expenses/ict_overhead_expenses/objects/<model("ict_overhead_expenses.ict_overhead_expenses"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ict_overhead_expenses.object', {
#             'object': obj
#         })
