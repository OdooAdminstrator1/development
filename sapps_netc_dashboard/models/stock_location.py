from odoo import api, fields, models, _, tools, _lt
import datetime


class SappsNetcDashboardStockMove(models.Model):
    _inherit = 'stock.location'

    sapps_finished_location = fields.Boolean('Is Finished Production Location')