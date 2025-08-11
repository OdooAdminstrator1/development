from odoo import api, fields, models, tools

class ProductionOrder(models.Model):
    _name = 'production.order'
    _description = 'Production Order'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    opportunity_id = fields.Many2one('crm.lead', string='Opportunity', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', compute='_compute_partner', store=True, readonly=True)

    @api.depends('opportunity_id')
    def _compute_partner(self):
        for record in self:
            record.partner_id = record.opportunity_id.partner_id


    @api.onchange('opportunity_id')
    def _onchange_opportunity_id(self):
        """Auto-fill name from opportunity if empty."""
        if self.opportunity_id and not self.name:
            self.name = self.opportunity_id.name


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    production_order_id = fields.Many2one(
        'production.order',
        string='Production Order',
        domain="[('partner_id', '=', partner_id)]"
    )

class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    partner_id = fields.Many2one('res.partner', string='Customer')
    production_order_id = fields.Many2one(
        'production.order',
        string='Production Order',
        domain="[('partner_id', '=', partner_id)]"
    )

    @api.onchange('sale_id')
    def _onchange_sale_id_set_partner(self):
        """If this MO has a sale order link, fill partner from it (if present)."""
        for rec in self:
            # check if sale_id field actually exists on the model (some installs may differ)
            if 'sale_id' in rec._fields and rec.sale_id:
                rec.partner_id = rec.sale_id.partner_id.id
            # otherwise keep partner_id as-is (user can fill it manually)