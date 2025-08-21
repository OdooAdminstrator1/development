from odoo import api, fields, models, tools

class ProductionOrder(models.Model):
    _name = 'production.order'
    _description = 'Production Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Optional but recommended for better UX

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    opportunity_id = fields.Many2one('crm.lead', string='Opportunity', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', compute='_compute_partner', store=True, readonly=True)
    
    # Attachment field
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        string='Attachments',
        relation='production_order_attachment_rel',
        column1='production_order_id',
        column2='attachment_id'
    )
    
    # Smart button fields (from previous implementation)
    sale_order_count = fields.Integer(string='Sale Order Count', compute='_compute_sale_order_count')
    mrp_production_count = fields.Integer(string='Manufacturing Order Count', compute='_compute_mrp_production_count')

    @api.depends('opportunity_id')
    def _compute_partner(self):
        for record in self:
            record.partner_id = record.opportunity_id.partner_id

    @api.depends('opportunity_id')
    def _compute_sale_order_count(self):
        for order in self:
            order.sale_order_count = self.env['sale.order'].search_count([('production_order_id', '=', order.id)])

    @api.depends('opportunity_id')
    def _compute_mrp_production_count(self):
        for order in self:
            order.mrp_production_count = self.env['mrp.production'].search_count([('production_order_id', '=', order.id)])

    @api.onchange('opportunity_id')
    def _onchange_opportunity_id(self):
        """Auto-fill name from opportunity if empty."""
        if self.opportunity_id and not self.name:
            self.name = self.opportunity_id.name

    # Action methods for smart buttons
    def action_view_sale_orders(self):
        action = self.env.ref('sale.action_orders').read()[0]
        action['domain'] = [('production_order_id', '=', self.id)]
        action['context'] = {'create': False}
        return action

    def action_view_mrp_productions(self):
        action = self.env.ref('mrp.mrp_production_action').read()[0]
        action['domain'] = [('production_order_id', '=', self.id)]
        action['context'] = {'create': False}
        return action
