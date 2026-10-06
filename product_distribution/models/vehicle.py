from odoo import models, fields, api,_
from odoo.exceptions import ValidationError
import ast

class DistributionVehicle(models.Model):
    _name = 'distribution.vehicle'
    _description = 'Distribution Vehicle'

    name = fields.Char(string='Name', required=True)
    car_plate_number = fields.Char(string='Car Plate Number')
    driver_id = fields.Many2one('hr.employee', string='Driver')
    itinerary_id = fields.Many2one('distribution.itinerary', string='Line')
    location_id= fields.Many2one('stock.location','Location',domain="[('id', 'not in', assigned_location_ids), ('id', 'not in', allowed_parent_location_ids), ('id', 'child_of', allowed_parent_location_ids)]")
    product_list_id=fields.Many2one('list.template','Product List Template')
    active = fields.Boolean(default=True)
    assigned_location_ids = fields.Many2many(
        'stock.location',
        string='Assigned Locations',
        compute='_compute_assigned_location_ids'
    )

    allowed_parent_location_ids = fields.Many2many(
        'stock.location',
        string='Allowed Parent Locations',
        compute='_compute_allowed_parent_location_ids'
    )

    # Using Many2many to represent the products and lots available in this vehicle
    #product_variant_ids = fields.Many2many('product.product', string='Products')
    #lot_ids = fields.Many2many('stock.lot', string='Lots')
    #pricelist_id = fields.Many2one('product.pricelist', string='Price List')

    @api.depends('location_id')
    def _compute_assigned_location_ids(self):
        for rec in self:
            domain = [('location_id', '!=', False), ('active', '=', True)]
            if rec.id:
                domain.append(('id', '!=', rec.id))
            other_vehicles = self.search(domain)
            rec.assigned_location_ids = other_vehicles.mapped('location_id')


    @api.depends()
    def _compute_allowed_parent_location_ids(self):
        get_param = self.env['ir.config_parameter'].sudo().get_param
        param_value = get_param('product_distribution.distribution_location_ids', '')
        
        root_ids = []
        if param_value:
            try:
                parsed = ast.literal_eval(param_value)
                if isinstance(parsed, (list, tuple)):
                    root_ids = [int(i) for i in parsed if str(i).isdigit() or isinstance(i, int)]
                else:
                    root_ids = [int(parsed)]
            except Exception:
                root_ids = [int(i.strip()) for i in param_value.split(',') if i.strip().isdigit()]
        
        locations = self.env['stock.location'].browse(root_ids)
        for rec in self:
            rec.allowed_parent_location_ids = locations



    @api.constrains('location_id', 'active')
    def _check_unique_location(self):
        for rec in self:
            if rec.location_id and rec.active:
                existing = self.search([
                    ('location_id', '=', rec.location_id.id),
                    ('id', '!=', rec.id),
                    ('active', '=', True)
                ])
                if existing:
                    raise ValidationError(_('This location is already assigned to active vehicle: %s') % existing.name)
