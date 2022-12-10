# -*- coding: utf-8 -*-
# from odoo import http


# class AdvancedLandedCost(http.Controller):
#     @http.route('/advanced_landed_cost/advanced_landed_cost/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/advanced_landed_cost/advanced_landed_cost/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('advanced_landed_cost.listing', {
#             'root': '/advanced_landed_cost/advanced_landed_cost',
#             'objects': http.request.env['advanced_landed_cost.advanced_landed_cost'].search([]),
#         })

#     @http.route('/advanced_landed_cost/advanced_landed_cost/objects/<model("advanced_landed_cost.advanced_landed_cost"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('advanced_landed_cost.object', {
#             'object': obj
#         })
