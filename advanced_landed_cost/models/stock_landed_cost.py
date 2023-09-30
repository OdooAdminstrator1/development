# Copyright 2019 Komit Consulting - Duc Dao Dong
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class LandedCost(models.Model):
    _inherit = "stock.landed.cost"

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True,
        related="",
        default=lambda self: self.env.user.company_id.currency_id,
    )

    @api.onchange("account_journal_id")
    def _onchange_account_journal_id(self):
        if self.account_journal_id and self.account_journal_id.currency_id:
            self.currency_id = self.account_journal_id.currency_id

    @api.onchange("currency_id")
    def _onchange_currency_id(self):
        if self.currency_id:
            self.cost_lines._onchange_currency_price_unit()


class AccountMoveLandedCost(models.Model):
    _inherit = 'account.move'

    def button_create_landed_costs(self):
        """Create a `stock.landed.cost` record associated to the account move of `self`, each
        `stock.landed.costs` lines mirroring the current `account.move.line` of self.
        """
        self.ensure_one()
        landed_costs_lines = self.line_ids.filtered(lambda line: line.is_landed_costs_line)

        landed_costs = self.env['stock.landed.cost'].create({
            'vendor_bill_id': self.id,
            'currency_id':self.currency_id.id,
            'cost_lines': [(0, 0, {
                'product_id': l.product_id.id,
                'name': l.product_id.name,
                'account_id': l.product_id.product_tmpl_id.get_product_accounts()['stock_input'].id,
                'currency_price_unit': l.price_subtotal,
                'currency_id': self.currency_id.id,
                'price_unit': self.currency_id._convert(
                        l.price_subtotal, self.env.company.currency_id, self.env.company, l.date
                    ),
                'split_method': 'equal',
            }) for l in landed_costs_lines],
        })
        action = self.env.ref('stock_landed_costs.action_stock_landed_cost').read()[0]
        return dict(action, view_mode='form', res_id=landed_costs.id, views=[(False, 'form')])
