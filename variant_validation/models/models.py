


from odoo import fields,api, models, _
from odoo.exceptions import UserError



class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.onchange('attribute_line_ids')
    def _onchange_attribute_line_ids(self):
        values_ids = self.attribute_line_ids.value_ids.ids
        # values_ids = self.attribute_line_ids.product_template_value_ids.ids

        variant_value_ids = self.product_variant_ids.product_template_attribute_value_ids.product_attribute_value_id.ids

        check = all(item in values_ids for item in variant_value_ids)

        if not check:
            raise UserError(_("Cannot delete attribute or values that used in product variant  "))

