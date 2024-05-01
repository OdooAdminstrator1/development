# -*- coding: utf-8 -*-
# from odoo import http


# class FilterWithAndInsteadOfOr(http.Controller):
#     @http.route('/filter_with_and_instead_of_or/filter_with_and_instead_of_or', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/filter_with_and_instead_of_or/filter_with_and_instead_of_or/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('filter_with_and_instead_of_or.listing', {
#             'root': '/filter_with_and_instead_of_or/filter_with_and_instead_of_or',
#             'objects': http.request.env['filter_with_and_instead_of_or.filter_with_and_instead_of_or'].search([]),
#         })

#     @http.route('/filter_with_and_instead_of_or/filter_with_and_instead_of_or/objects/<model("filter_with_and_instead_of_or.filter_with_and_instead_of_or"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('filter_with_and_instead_of_or.object', {
#             'object': obj
#         })
