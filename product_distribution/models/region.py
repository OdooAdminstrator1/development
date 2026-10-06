from odoo import models, fields

class DistributionRegion(models.Model):
    _name = 'distribution.region'
    _description = 'Distribution Region'

    name = fields.Char(string='Name', required=True)
    itinerary_id = fields.Many2one('distribution.itinerary', string='Line')
    sequence_order=fields.Integer('Order')




class SegmentLine(models.Model):
    _name = 'distribution.itinerary'
    _description = 'Distribution Line'
    name = fields.Char(string='Name', required=True)
    desc = fields.Char(string='Description')


