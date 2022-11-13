from odoo import models, fields, api, _
from ast import literal_eval
from odoo.exceptions import UserError


class OverheadProcedureMrpBom(models.Model):
    _inherit = 'mrp.bom'

    finishing_product_ok = fields.Boolean('Is Finishing Product')

    @api.constrains('bom_line_ids')
    def check_overhead_labor_line(self):
        standard_cost_product = literal_eval(self.env['ir.config_parameter'].sudo().get_param(
            'ict_overhead_expenses.ict_standard_cost_product_ids'))
        for rec in self:
            if rec.finishing_product_ok and len(rec.bom_line_ids.filtered(lambda v: v.product_id.id in standard_cost_product)) != len(standard_cost_product):
                raise UserError(_("Finished BOM should have standard overhead/labor defined in settings"))