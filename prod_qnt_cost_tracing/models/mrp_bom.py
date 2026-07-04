# models/mrp_bom_smart_button.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MrpBom(models.Model):
    _inherit = 'mrp.bom'
    
    # Compute count for smart button (optional - shows existing MOs count)
    mo_count = fields.Integer(
        string='Manufacturing Orders',
        compute='_compute_mo_count'
    )
    
    def _compute_mo_count(self):
        """Count manufacturing orders for this product"""
        for bom in self:
            if bom.product_id:
                bom.mo_count = self.env['mrp.production'].search_count([
                    ('product_id', '=', bom.product_id.id)
                ])
            else:
                bom.mo_count = 0
    
    def action_create_manufacturing_order(self):
        """Action to create new manufacturing order with this product"""
        self.ensure_one()
        
        # Get the product from BOM
        product = self.product_id or self.product_tmpl_id.product_variant_id
        
        if not product:
            raise UserError(_("No product defined for this Bill of Materials"))
        
        # Prepare context for default values
        context = {
            'default_product_id': product.id,
            'default_bom_id': self.id,
            'default_product_uom_qty': 1,
            'default_product_uom_id': product.uom_id.id,
            'state' : 'draft',
        }
        
        # Return action to create new manufacturing order
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Manufacturing Order'),
            'res_model': 'mrp.production',
            'view_mode': 'form',
            'target': 'current',
            'context': context,
        }
    
    def action_view_manufacturing_orders(self):
        """View existing manufacturing orders for this product"""
        self.ensure_one()
        product = self.product_id or self.product_tmpl_id.product_variant_id
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manufacturing Orders'),
            'res_model': 'mrp.production',
            'view_mode': 'tree,form',
            'domain': [('product_id', '=', product.id)],
            'context': {'create': False},
        }
