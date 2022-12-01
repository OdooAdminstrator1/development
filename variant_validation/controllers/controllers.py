# -*- coding: utf-8 -*-
# from odoo import http


# class VariantValidation(http.Controller):
#     @http.route('/variant_validation/variant_validation', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/variant_validation/variant_validation/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('variant_validation.listing', {
#             'root': '/variant_validation/variant_validation',
#             'objects': http.request.env['variant_validation.variant_validation'].search([]),
#         })

#     @http.route('/variant_validation/variant_validation/objects/<model("variant_validation.variant_validation"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('variant_validation.object', {
#             'object': obj
#         })
