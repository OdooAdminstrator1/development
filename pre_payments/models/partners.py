from odoo import models, fields

class ResPartner(models.Model):
    _inherit = "res.partner"

    advance_account_payable_id = fields.Many2one(
        "account.account", 
        company_dependent=True,
        string="Vendor Advanced Account",
        domain="[('account_type', '=', 'asset_current'), ('deprecated', '=', False), ('advanced', '=', True)]",
        help="This account will be used instead of the default one as the payable account for the current partner"
    )

    advance_account_receivable_id = fields.Many2one(
        "account.account", 
        company_dependent=True,
        string="Customer Advanced Account",
        domain="[('account_type', '=', 'liability_current'), ('deprecated', '=', False), ('advanced', '=', True)]",
        help="This account will be used instead of the default one as the advance receivable account for the current partner"
    )
    supplier_advanced_count = fields.Integer(compute='_compute_advanced_count', string='# Advanced Payments')

    def _compute_advanced_count(self):
        # retrieve all children partners and prefetch 'parent_id' on them
        all_partners = self.search([('id', 'child_of', self.ids)])
        all_partners.read(['parent_id'])
        advance_domain = [('partner_id', 'in', all_partners.ids),
                  ('advance_ok', '=', True)]
        advanced_payment=self.env['account.payment'].search(advance_domain)

        supplier_advance_groups = self.env['account.payment'].read_group(
            domain=[('partner_id', 'in', all_partners.ids),
                  ('advance_ok', '=', True)],
            fields=['partner_id'], groupby=['partner_id']
        )
        partners = self.browse()
        for group in supplier_advance_groups:
            partner = self.browse(group['partner_id'][0])
            while partner:
                if partner in self:
                    partner.supplier_advanced_count += group['partner_id_count']
                    partners |= partner
                partner = partner.parent_id
        (self - partners).supplier_advanced_count = 0





