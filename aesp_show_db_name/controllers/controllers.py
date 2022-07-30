# -*- coding: utf-8 -*-
# from odoo import http


# class AespShowDbName(http.Controller):
#     @http.route('/aesp_show_db_name/aesp_show_db_name', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/aesp_show_db_name/aesp_show_db_name/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('aesp_show_db_name.listing', {
#             'root': '/aesp_show_db_name/aesp_show_db_name',
#             'objects': http.request.env['aesp_show_db_name.aesp_show_db_name'].search([]),
#         })

#     @http.route('/aesp_show_db_name/aesp_show_db_name/objects/<model("aesp_show_db_name.aesp_show_db_name"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('aesp_show_db_name.object', {
#             'object': obj
#         })
