
from odoo import api, fields, models


class LandedCostLine(models.Model):
    _inherit = "stock.landed.cost.lines"

    price_unit = fields.Float(string="Cost in Base Currency")
    currency_id = fields.Many2one(related="cost_id.currency_id")
    currency_price_unit = fields.Monetary(currency_field="currency_id", string="Cost")

    @api.onchange("currency_price_unit")
    def _onchange_currency_price_unit(self):
        for rec in self:
            if rec.currency_price_unit:
                if rec.cost_id.vendor_bill_id and rec.cost_id.vendor_bill_id.currency_id != self.env.company.currency_id:
                    company = rec.cost_id.company_id
                    date = rec.cost_id.vendor_bill_id.date
                    rec.price_unit = rec.cost_id.currency_id._convert(
                            rec.currency_price_unit, company.currency_id, company, date
                        )
                else:
                    date = rec.cost_id.date
                    company = rec.cost_id.company_id
                    if rec.cost_id.currency_id != company.currency_id:
                        rec.price_unit = rec.cost_id.currency_id._convert(
                            rec.currency_price_unit, company.currency_id, company, date
                        )
                    else:
                        rec.price_unit = rec.currency_price_unit

    @api.onchange("product_id")
    def onchange_product_id(self):
        res = super(LandedCostLine, self).onchange_product_id()
        self.currency_price_unit = self.price_unit
        return res
