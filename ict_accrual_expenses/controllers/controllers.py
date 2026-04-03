# -*- coding: utf-8 -*-
# from odoo import http


# class AppsAccrualExpenses(http.Controller):
#     @http.route('/apps_accrual_expenses/apps_accrual_expenses/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/apps_accrual_expenses/apps_accrual_expenses/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('apps_accrual_expenses.listing', {
#             'root': '/apps_accrual_expenses/apps_accrual_expenses',
#             'objects': http.request.env['apps_accrual_expenses.apps_accrual_expenses'].search([]),
#         })

#     @http.route('/apps_accrual_expenses/apps_accrual_expenses/objects/<model("apps_accrual_expenses.apps_accrual_expenses"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('apps_accrual_expenses.object', {
#             'object': obj
#         })
