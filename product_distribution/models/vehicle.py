from odoo import models, fields

class DistributionVehicle(models.Model):
    _name = 'distribution.vehicle'
    _description = 'Distribution Vehicle'

    name = fields.Char(string='Name', required=True)
    car_plate_number = fields.Char(string='Car Plate Number')
    driver_id = fields.Many2one('hr.employee', string='Driver')
    itinerary_id = fields.Many2one('distribution.itinerary', string='Line')
    location_id= fields.Many2one('stock.location','Location')
    product_list_id=fields.Many2one('list.template','Product List Template')
    active = fields.Boolean(default=True)

    # Using Many2many to represent the products and lots available in this vehicle
    #product_variant_ids = fields.Many2many('product.product', string='Products')
    #lot_ids = fields.Many2many('stock.lot', string='Lots')
    #pricelist_id = fields.Many2one('product.pricelist', string='Price List')