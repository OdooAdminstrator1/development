# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class purchase_discount(models.Model):
#     _name = 'purchase_discount.purchase_discount'
#     _description = 'purchase_discount.purchase_discount'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
from odoo import models, fields, api
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class ProductProduct(models.Model):
     _inherit = 'product.template'

     unified_price = fields.Float(string='Unified Price')

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    discount_type = fields.Selection([('none', 'None'),('order', 'For Order')], string='Discount Type',
                                      default='none', required=True)
    discount_method = fields.Selection([('percentage', 'Percentage'), ('amount', 'Amount')], string='Discount Method',required=True,
                                     default='percentage')
    discount_value=fields.Float(string='Discount Value')

    @api.onchange('discount_type')
    def compute_type1(self):
        if self.discount_type == 'line':
            for line in self.order_line:
                line.discount_type=True
        else:
            for line in self.order_line:
                line.discount_type = False

        if self.discount_type == 'none' or self.discount_type == False:
            self.discount_value = 0
            for line in self.order_line:
                line.discount = 0
                line.price_unit = line.old_pric_unit

    @api.onchange('discount_value','discount_method','order_line')
    def compute_type(self):

        for line in self.order_line:


            if self.discount_type == 'order':

                if self.discount_method=='percentage':
                    product_qty=line.product_qty
                    if product_qty==0:
                        product_qty=1
                    val=self.discount_value
                    line.write({'discount':val})
                    subtotal = line.old_pric_unit*product_qty
                    valu=subtotal - (subtotal * line.discount) / 100
                    new_p_unit = valu/product_qty
                    line.write({'price_unit' : new_p_unit })
                if self.discount_method == 'amount':
                    self._compute_amount_disc()
            line._onchange_discount()
            line._onchange_discount1()

    def _compute_amount_disc(self):

        amount=0
        for line in self.order_line:
            amount+=line.product_qty*line.old_pric_unit
        for line in self.order_line:
            if amount != 0:
                val=self.discount_value*line.product_qty*line.old_pric_unit/amount
            else:
                val = 0
            line.write({'discount':val})
            subtotal = line.old_pric_unit * line.product_qty
            line.write({'price_unit' : (subtotal - line.discount)/line.product_qty})



class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    discount = fields.Float(string='discount %')
    discount_type=fields.Boolean(string=' test discount',deafult=False)
    old_pric_unit=fields.Float(string='Unit Price', digits='Product Price')

    # @api.depends('product_qty', 'price_unit', 'taxes_id','discount')
    # def _compute_amount(self):
    #     for line in self:
    #         vals = line._prepare_compute_all_values()
    #         taxes = line.taxes_id.compute_all(
    #             vals['price_unit'],
    #             vals['currency_id'],
    #             vals['product_qty'],
    #             vals['product'],
    #             vals['partner'])
    #         line.update({
    #             'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
    #             'price_total': taxes['total_included'],
    #             'price_subtotal': taxes['total_excluded']-line.price_unit*line.product_qty*line.discount/100,
    #         })


    @api.onchange('old_pric_unit')
    def _onchange_discount1(self):
        subtotal = self.old_pric_unit * self.product_qty
        product_qty = self.product_qty
        if product_qty == 0:
            product_qty = 1
        if self.order_id.discount_method=='percentage' and self.order_id.discount_type=='line':
            self.price_unit = (subtotal - (subtotal * self.discount) / 100)/product_qty
        if self.order_id.discount_method=='amount' and self.order_id.discount_type=='line':
            self.price_unit = (subtotal - self.discount)/product_qty

    @api.onchange('discount')
    def _onchange_discount(self):
        subtotal = self.old_pric_unit * self.product_qty
        product_qty = self.product_qty
        if product_qty == 0:
            product_qty = 1
        if self.order_id.discount_method == 'percentage' and self.order_id.discount_type == 'line':
            self.price_unit = (subtotal - (subtotal * self.discount) / 100)/product_qty
        if self.order_id.discount_method == 'amount' and self.order_id.discount_type == 'line':
            self.price_unit = (subtotal -  self.discount)/product_qty

    @api.onchange( 'product_qty')
    def _onchange_quantity_mhd(self):
        if not self.product_id:
            return
        params = {'order_id': self.order_id}
        seller = self.product_id._select_seller(
            partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.order_id.date_order and self.order_id.date_order.date(),
            uom_id=self.product_uom,
            params=params)

        if seller or not self.date_planned:
            self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)



        self.old_pric_unit = self.product_id.unified_price or 0.0
