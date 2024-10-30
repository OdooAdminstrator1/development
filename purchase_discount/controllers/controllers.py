# -*- coding: utf-8 -*-
# from odoo import http


# class PurchaseDisount(http.Controller):
#     @http.route('/purchase_discount/purchase_discount/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/purchase_discount/purchase_discount/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('purchase_discount.listing', {
#             'root': '/purchase_discount/purchase_discount',
#             'objects': http.request.env['purchase_discount.purchase_discount'].search([]),
#         })

#     @http.route('/purchase_discount/purchase_discount/objects/<model("purchase_discount.purchase_discount"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('purchase_discount.object', {
#             'object': obj
#         })
