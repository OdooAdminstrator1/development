# from odoo import models, fields, api

# class StockPicking(models.Model):
#     _inherit = 'stock.picking'

#     # You can add any custom fields or methods here if needed
#     def _get_report_base_filename(self):
#         """ Override to set custom report filename """
#         if self.picking_type_id and self.picking_type_id.code == 'internal':
#             return f"Internal Transfer - {self.name}"
#         return super()._get_report_base_filename()