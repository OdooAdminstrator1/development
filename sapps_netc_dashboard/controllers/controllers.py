# -*- coding: utf-8 -*-
# from odoo import http


# class SappsNetcDashboard(http.Controller):
#     @http.route('/sapps_netc_dashboard/sapps_netc_dashboard/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sapps_netc_dashboard/sapps_netc_dashboard/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('sapps_netc_dashboard.listing', {
#             'root': '/sapps_netc_dashboard/sapps_netc_dashboard',
#             'objects': http.request.env['sapps_netc_dashboard.sapps_netc_dashboard'].search([]),
#         })

#     @http.route('/sapps_netc_dashboard/sapps_netc_dashboard/objects/<model("sapps_netc_dashboard.sapps_netc_dashboard"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sapps_netc_dashboard.object', {
#             'object': obj
#         })
