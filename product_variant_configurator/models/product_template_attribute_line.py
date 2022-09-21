# Copyright 2015 Oihane Crucelaegui - AvanzOSC
# Copyright 2015-2017 Tecnativa - Pedro M. Baeza
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3

from odoo import api, fields, models


class ProductTemplateAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    required = fields.Boolean(
        default=False,
    )

    @api.onchange("attribute_id")
    def _onchange_attribute_id_clean_value(self):
        """This is for consistency when changing attribute in the product."""
        self.value_ids = False
