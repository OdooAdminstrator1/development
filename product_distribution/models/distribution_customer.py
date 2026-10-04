from odoo import models, fields

class DistributionCustomer(models.Model):
    _name = 'distribution.customer'
    _description = 'Distribution Retail Customer'
    _order = 'name'

    name = fields.Char(string='Customer / Shop Name', required=True)
    phone_1 = fields.Char(string='Phone Number 1')
    phone_2 = fields.Char(string='Phone Number 2')
    
    # Matching Odoo's built-in geo-localization attribute standard
    partner_latitude = fields.Float(string='Geo Latitude', digits=(16, 5))
    partner_longitude = fields.Float(string='Geo Longitude', digits=(16, 5))
    date_localization = fields.Date(string='Geo Localization Date')

    # Retained attributes
    creator_reference = fields.Char(string='Creator Reference', help="Note about the origin information of the client")
    distributor_id = fields.Many2one(
        'hr.employee', 
        string='Assigned Distributor', 
        domain=[('isdistributor', '=', True)]
    )
    
    # Native support for multiple attachments/photos
    photo_ids = fields.One2many(
        'distribution.customer.image', 
        'property_id', 
        string='Photos'
    )
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    class PropertyImage(models.Model):
        _name = 'distribution.customer.image'
        _description = 'Property Image'
        _order = 'sequence, id'

        sequence = fields.Integer(string='Sequence', default=10)
        name = fields.Char(string='Caption')
        # Use image_1920 field type for automatic resizing and optimization
        image_1920 = fields.Image(
            string='Image', 
            max_width=1920, 
            max_height=1920, 
            required=True
        )
        property_id = fields.Many2one(
            'distribution.customer', 
            string='Property', 
            ondelete='cascade'
        )