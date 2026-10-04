from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DistributionOpenDate(models.Model):
    _name = 'distribution.open.date'
    _description = 'Open Day (Open-Day Master)'

    startup_date = fields.Date(string='Startup Date', default=fields.Date.context_today, required=True)
    status = fields.Selection([
        ('prepare', 'Prepare'),
        ('confirm', 'Confirm'),
        ('running', 'Running'),
        ('close', 'Close')
    ], string='Status', default='prepare')
    close_date = fields.Date(string='Close Date')
    
    # In Odoo, the primary key 'id' is standard. We can expose it or use a sequence.
    session_id = fields.Char(string='Session ID', readonly=True, copy=False, default='New')
    
    distributor_line_ids = fields.One2many('distribution.open.date.distributor', 'open_date_id', string='Distributors in Charge')
    count_distributors=fields.Integer("Distributors Nb",compte="_count_distributors")

    @api.depends('distributor_line_ids')
    def _count_distributors(self):
        for rec in self:
            rec.count_distributors=len(rec.distributor_line_ids)




    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('session_id', 'New') == 'New':
                # You will need to define this sequence in an XML data file
                vals['session_id'] = self.env['ir.sequence'].next_by_code('distribution.open.date') or 'New'
        return super().create(vals_list)

    def action_close_session(self):
        self.ensure_one()
        for record in self:
            record.status = 'close'
            record.close_date = fields.Date.context_today(record)
            
    def action_validate_session(self):
        self.ensure_one()
        for record in self:
            record.status = 'confirm'


class DistributionOpenDateDistributor(models.Model):
    _name = 'distribution.open.date.distributor'
    _description = 'Open Date Distributor Line'

    open_date_id = fields.Many2one('distribution.open.date', string='Open Date', required=True, ondelete='cascade')
    distributor_id = fields.Many2one('hr.employee', string='Distributor', domain=[('isdistributor', '=', True)])
    state = fields.Selection([
        ('loading', 'Loading'),
        ('running', 'Running'),
        ('done', 'Done')
    ], string='State', default='loading')
    
    actual_value = fields.Float(string='Actual Value', compute='_compute_values', store=True)
    expected_value = fields.Float(string='Expected Value', compute='_compute_values', store=True)
    picking_id = fields.Many2one('stock.picking', string='Internal Transfer', readonly=True)

    @api.depends('state', 'distributor_id')
    def _compute_values(self):
        for record in self:
            # Placeholder for complex valuation logic based on vehicle inventory
            if record.state == 'loading':
                record.actual_value = 0.0 # Implement sum of products in vehicle logic here
            elif record.state == 'running':
                record.expected_value = 0.0 # Implement expected running logic here

    def action_generate_internal_transfer(self):
        """ Generates an internal transfer based on system configurations """
        # Fetch configuration parameters
        ICP = self.env['ir.config_parameter'].sudo()
        customer_id = ICP.get_param('product_distribution.default_general_customer_id')
        src_location_id = ICP.get_param('product_distribution.default_distribution_location_id')
        dest_location_id = ICP.get_param('product_distribution.default_delevery_location_id')

        if not src_location_id or not dest_location_id:
            raise ValidationError("Configuration Error: Please set the default Source and Delivery locations in the Distribution Configuration Settings before generating a transfer.")

        # Find the operation type for Internal Transfers
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not picking_type:
            raise ValidationError("Could not find an Internal Transfer Operation Type for your company.")

        for record in self:
            if record.picking_id:
                continue  # Skip if transfer already exists

            # Create the stock picking (Internal Transfer)
            picking_vals = {
                'partner_id': int(customer_id) if customer_id else False,
                'location_id': int(src_location_id),
                'location_dest_id': int(dest_location_id),
                'picking_type_id': picking_type.id,
                'distributor_id': record.distributor_id.id,
                'open_date_id': record.open_date_id.id,
                'origin': record.open_date_id.session_id, # Good for tracking
            }

            picking = self.env['stock.picking'].create(picking_vals)
            
            # Link the new picking back to this line
            record.picking_id = picking.id
            record.state = 'loading'