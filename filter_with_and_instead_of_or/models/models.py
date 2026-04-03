# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json


class FilterByMultipleAttribute(models.TransientModel):
    _name = 'search.product.attribute'

    filters = fields.One2many('search.product.attribute.choices', inverse_name='wizard_id')

    def filter_product_according_to_attribute(self):

        domain = []
        for filter in self.filters:
            domain.append(('product_template_attribute_value_ids.attribute_line_id.attribute_id.name','=',
                           filter.attribute_id.name))
            domain.append(('product_template_attribute_value_ids.product_attribute_value_id.id', 'in',
                           filter.value_id.ids))
        return {
            'type': 'ir.actions.act_window',
            "name": "Product Variants",
            'res_model': 'product.product',
            'view_mode': 'tree, form',
            'views': [(self.env.ref('product.product_product_tree_view').id, 'tree'), (False, 'form')],
            'domain': domain
            # 'context': {'default_mrp_order_id': self.id},
        }


class FilterByMultipleAttributeChoices(models.TransientModel):
    _name = 'search.product.attribute.choices'

    wizard_id = fields.Many2one('search.product.attribute')
    attribute_id = fields.Many2one('product.attribute', string='Choose Attribute')
    value_id = fields.Many2many('product.attribute.value')
    value_id_domain = fields.Char(compute='_compute_value_id_domain')

    @api.depends('attribute_id')
    def _compute_value_id_domain(self):
        for rec in self:
            if self.attribute_id:
                rec.value_id_domain = json.dumps([('id', 'in', self.attribute_id.value_ids.ids)])
            else:
                rec.value_id_domain = json.dumps([])
