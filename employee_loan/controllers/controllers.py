# -*- coding: utf-8 -*-
# from odoo import http


# class EmployeeLoan(http.Controller):
#     @http.route('/employee_loan/employee_loan', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/employee_loan/employee_loan/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('employee_loan.listing', {
#             'root': '/employee_loan/employee_loan',
#             'objects': http.request.env['employee_loan.employee_loan'].search([]),
#         })

#     @http.route('/employee_loan/employee_loan/objects/<model("employee_loan.employee_loan"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('employee_loan.object', {
#             'object': obj
#         })
