


from odoo import fields,api, models, _
from odoo.exceptions import UserError



class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.onchange('attribute_line_ids')
    def _onchange_attribute_line_ids(self):
        values_ids = self.attribute_line_ids.value_ids.ids
        if self.product_variant_count>0:
            if len(self.attribute_line_ids)>len(self.attribute_line_ids.ids):
                raise UserError(_("Cannot add attribute to product  "))

        # values_ids = self.attribute_line_ids.product_template_value_ids.ids

        variant_value_ids = self.product_variant_ids.product_template_attribute_value_ids.product_attribute_value_id.ids

        check = all(item in values_ids for item in variant_value_ids)


        if not check:
            raise UserError(_("Cannot delete attribute or values that used in product variant  "))

class ProductProductInherited(models.Model):
    _inherit = 'product.product'

    product_template_variant_value_ids = fields.Many2many('product.template.attribute.value',
                                                          relation='product_variant_combination',
                                                          domain=[('attribute_line_id.value_count', '>=', 1)],
                                                          string="Variant Values", ondelete='restrict')
    product_template_variant_value_comma = fields.Char(string='Variant Values Comma Separated', compute='_compute_variant_value_comma')

    def _compute_variant_value_comma(self):
        for rec in self:
            rec.product_template_variant_value_comma = ', '.join([p.attribute_id.name + ': ' + p.name for p in rec.product_template_variant_value_ids.product_attribute_value_id])

