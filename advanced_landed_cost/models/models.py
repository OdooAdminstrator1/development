# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools import float_is_zero, float_round

# class advanced_landed_cost(models.Model):
#     _name = 'advanced_landed_cost.advanced_landed_cost'
#     _description = 'advanced_landed_cost.advanced_landed_cost'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
from odoo.addons.website import tools
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class LandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    advanced_valuation_adjustment_lines = fields.One2many(
        'stock.valuation.adjustment.lines.advanced', 'cost_id', 'Advanced Valuation Adjustments')

    def button_validate(self):
        for rec in self:
            if rec.vendor_bill_id and rec.vendor_bill_id.currency_id.id != rec.currency_id.id:
                raise UserError("Landed Cost Currency Must Match Selected Vendor Bill Currency")
            if rec.vendor_bill_id:
                landed_cost_products = rec.vendor_bill_id.invoice_line_ids.filtered(lambda v: v.product_id.landed_cost_ok)
                if len(landed_cost_products) == 0:
                    raise UserError("There's No Landed Cost Product in this bill")
                total_bill = sum(lc.price_subtotal for lc in landed_cost_products)
                total_lc = sum(lc.currency_price_unit for lc in rec.cost_lines)
                if total_bill != total_lc:
                    raise UserError(f"Total Defined Cost Not Equal To Related Bill Total ({total_bill}{rec.vendor_bill_id.currency_id.symbol})")

        if any(cost.state != 'draft' for cost in self):
            raise UserError(_('Only draft landed costs can be validated'))
        if not all(cost.picking_ids for cost in self):
            raise UserError(_('Please define the transfers on which those additional costs should apply.'))
        cost_without_adjusment_lines = self.filtered(lambda c: not c.valuation_adjustment_lines)
        if cost_without_adjusment_lines:
            cost_without_adjusment_lines.compute_landed_cost()
        if not self._check_sum():
            raise UserError(_('Cost and adjustments lines do not match. You should maybe recompute the landed costs.'))

        for cost in self:
            move = self.env['account.move']
            move_vals = {
                'journal_id': cost.account_journal_id.id,
                'date': cost.date,
                'ref': cost.name,
                'line_ids': [],
                'move_type': 'entry',
            }
            pr_added = []
            for line in cost.advanced_valuation_adjustment_lines.filtered(lambda line: line.move_id):
                if line.move_id.stock_valuation_layer_ids:
                    remaining_qty = sum(line.move_id.stock_valuation_layer_ids.mapped('remaining_qty'))
                    linked_layer = line.move_id.stock_valuation_layer_ids[-1]  # Maybe the LC layer should be linked to multiple IN layer?

                    cost_to_add = ((100-line.percentage)/100) * line.price_unit
                    if not cost.company_id.currency_id.is_zero(cost_to_add):
                        valuation_layer = self.env['stock.valuation.layer'].create({
                            'value': cost_to_add,
                            'unit_cost': 0,
                            'quantity': 0,
                            'remaining_qty': 0,
                            'stock_valuation_layer_id': linked_layer.id,
                            'description': cost.name,
                            'stock_move_id': line.move_id.id,
                            'product_id': line.move_id.product_id.id,
                            'stock_landed_cost_id': cost.id,
                            'company_id': cost.company_id.id,
                        })

                        move_vals['stock_valuation_layer_ids'] = [(6, None, [valuation_layer.id])]
                        linked_layer.remaining_value += cost_to_add

                # Update the AVCO
                product = line.move_id.product_id
                if product.cost_method == 'average' and not float_is_zero(product.quantity_svl, precision_rounding=product.uom_id.rounding):
                    product.with_context(force_company=self.company_id.id).sudo().standard_price += cost_to_add / product.quantity_svl
                # `remaining_qty` is negative if the move is out and delivered proudcts that were not
                # in stock.
                qty_out = 0
                if line.move_id._is_in():
                    qty_out = line.move_id.product_qty - remaining_qty
                elif line.move_id._is_out():
                    qty_out = line.move_id.product_qty
                move_vals['line_ids'] += line._create_accounting_entries(move, qty_out)


            move = move.create(move_vals)
            cost.write({'state': 'done', 'account_move_id': move.id})
            move.post()

            if cost.vendor_bill_id and cost.vendor_bill_id.state == 'posted' and cost.company_id.anglo_saxon_accounting:
                all_amls = cost.vendor_bill_id.line_ids | cost.account_move_id.line_ids
                for product in cost.cost_lines.product_id:
                    accounts = product.product_tmpl_id.get_product_accounts()
                    input_account = accounts['stock_input']
                    all_amls.filtered(lambda aml: aml.account_id == input_account and not aml.reconciled).reconcile()
        return True

    @api.onchange('picking_ids','cost_lines')
    def changeAdvaced(self):
        self.write({'advanced_valuation_adjustment_lines':False})
        for cc in self.cost_lines:
            value_split = 0.0
            l = []
            rounding = self.env.company.currency_id.rounding
            v_lines = self.get_advanced_valuation_lines()
            total_qty = 0.0
            total_cost = 0.0
            total_weight = 0.0
            total_volume = 0.0
            total_line = 0.0
            for val_line_value in v_lines:
                total_qty += val_line_value.get('quantity', 0.0)
                total_weight += val_line_value.get('weight', 0.0)
                total_volume += val_line_value.get('volume', 0.0)

                former_cost = val_line_value.get('former_cost', 0.0)
                # round this because former_cost on the valuation lines is also rounded
                total_cost += former_cost

                total_line += 1

            for val_line_values in v_lines:
                value = 0.0
                if cc.split_method == 'by_quantity' and total_qty:
                    per_unit = (cc.price_unit / total_qty)
                    value = val_line_values.get('quantity', 0.0) * per_unit
                elif cc.split_method == 'by_weight' and total_weight:
                    per_unit = (cc.price_unit / total_weight)
                    value = val_line_values.get('weight', 0.0) * per_unit
                elif cc.split_method == 'by_volume' and total_volume:
                    per_unit = (cc.price_unit / total_volume)
                    value = val_line_values.get('volume', 0.0) * per_unit
                elif cc.split_method == 'equal':
                    value = (cc.price_unit / total_line)
                elif cc.split_method == 'by_current_cost_price' and total_cost:
                    per_unit = (cc.price_unit / total_cost)
                    value = val_line_values.get('former_cost', 0.0) * per_unit
                else:
                    value = (cc.price_unit / total_line)

                if rounding:
                    value = float_round(value, precision_rounding=rounding, rounding_method='UP')
                    fnc = min if cc.price_unit > 0 else max
                    value = fnc(value, cc.price_unit - value_split)
                    value_split += value

                lines = [x for x in v_lines if x['move_id'] != False]
                dest = " "
                remaining_qty = 0
                qty_out = 0
                # for line in lines:
                remaining_qty = sum(val_line_values['move_id'].stock_valuation_layer_ids.mapped('remaining_qty'))
                dest += val_line_values['move_id'].mapped('location_dest_id').display_name
                qty_out = 0
                all_qty=val_line_values['product_id'].qty_available
                qty=val_line_values['move_id'].product_qty
                if val_line_values['move_id']._is_in():
                    qty_out = val_line_values['move_id'].product_qty - remaining_qty
                elif val_line_values['move_id']._is_out():
                    qty_out = val_line_values['move_id'].product_qty
                new_line = {
                    'move_id': val_line_values['move_id'],
                    'account_id': cc.account_id.id,
                    'cost_id': self.id,
                    'cost_line_id': cc,
                    'product_id': val_line_values['product_id'],
                    'quantity_in_stock': all_qty,
                    "quantity_po_in_stock": val_line_values['move_id'].product_qty,
                    'quantity_out_stock': qty_out,

                    'percentage': qty_out / ( val_line_values['move_id'].product_qty) * 100,
                    'dest': dest,
                    'cost_part_of_quantity_out': qty_out / ( val_line_values['move_id'].product_qty)  * value,
                    'quantity_out_account_id': val_line_values['product_id'].product_tmpl_id.get_product_accounts()[
                        'expense'].id,
                    'price_unit': value
                }
                l.append((0, 0, new_line))

            self.write({'advanced_valuation_adjustment_lines': l})

    def get_advanced_valuation_lines(self):
        lines = []

        for move in self.mapped('picking_ids').mapped('move_lines'):
            # it doesn't make sense to make a landed cost for a product
            # that isn't set as being valuated in real time at real cost
            if move.product_id.valuation != 'real_time' or move.product_id.cost_method not in ('fifo', 'average'):
                continue
            vals = {
                'product_id': move.product_id,
                'move_id': self.env['stock.move'].browse(move.id.origin),
                'quantity': move.product_qty,
                'former_cost': sum(move.stock_valuation_layer_ids.mapped('value')),
                'weight': move.product_id.weight * move.product_qty,
                'volume': move.product_id.volume * move.product_qty
            }
            if sum(move.stock_valuation_layer_ids.mapped('value'))>0:
                lines.append(vals)

        if not lines and self.mapped('picking_ids'):
            raise UserError(_("You cannot apply landed costs on the chosen transfer(s). Landed costs can only be applied for products with automated inventory valuation and FIFO or average costing method."))
        return lines


class LandedCostLine(models.Model):
    _inherit = 'stock.landed.cost.lines'

    advanced_valuation_adjustment_lines = fields.One2many(
        'stock.valuation.adjustment.lines.advanced', 'cost_line_id', 'Advanced Valuation Adjustments')


class ADvancedAdjustmentLines(models.Model):
    _name = 'stock.valuation.adjustment.lines.advanced'
    _description = 'Valuation Adjustment Lines'
    move_id = fields.Many2one('stock.move', 'Stock Move')
    cost_id = fields.Many2one(
        'stock.landed.cost', 'Landed Cost',
        ondelete='cascade', required=True)
    cost_line_id = fields.Many2one(
        'stock.landed.cost.lines', 'A Cost Line')
    product_id = fields.Many2one('product.product', 'Product', required=True)
    quantity_in_stock = fields.Float(
        'On Hand Qnt',
        digits=0, required=True)
    quantity_po_in_stock = fields.Float(
        'Total receipt Qnt/PO',
        digits=0, )

    quantity_out_stock = fields.Float(
        'Out Quantity/PO',
        digits=0, required=True)
    percentage = fields.Float(
        '% of Qnt out')
    dest = fields.Char(
        'Dest location',  readonly=True)
    cost_part_of_quantity_out = fields.Float(
        'cost part of quantity out')
    report_cost_part_of_quantity_out = fields.Float(
        'Report cost part of quantity out')
    quantity_out_account_id = fields.Many2one('account.account', 'Cost Out Account', domain=[('deprecated', '=', False)])
    account_id = fields.Many2one('account.account', 'Account')
    price_unit = fields.Float('Cost', digits='Product Price')
    report_price_unit = fields.Float('Report Cost', digits='Product Price')
    @api.onchange('percentage')
    def change_cost(self):
        for rec in self:
            rec.cost_part_of_quantity_out=rec.percentage*rec.price_unit/100
            rec.report_cost_part_of_quantity_out = rec.percentage * rec.report_price_unit / 100

    def _create_account_move_line_advanved(self, move, credit_account_id, debit_account_id, qty_out, already_out_account_id):
            """
            Generate the account.move.line values to track the landed cost.
            Afterwards, for the goods that are already out of stock, we should create the out moves
            """
            AccountMoveLine = []

            name =  (self.product_id.code or self.product_id.name or '')
            base_line = {
                'name': name,
                'product_id': self.product_id.id,
                'quantity': 0,
            }
            debit_line = dict(base_line, account_id=debit_account_id)
            credit_line = dict(base_line, account_id=credit_account_id)
            diff = self.price_unit

            if diff > 0:
                debit_line['debit'] = diff
                credit_line['credit'] = diff
            else:
                # negative cost, reverse the entry
                debit_line['credit'] = -diff
                credit_line['debit'] = -diff
            AccountMoveLine.append([0, 0, debit_line])
            AccountMoveLine.append([0, 0, credit_line])

            # Create account move lines for quants already out of stock
            if self.percentage > 0:
                debit_line = dict(base_line,
                                  name=(name + ": " + str(qty_out) + _(' already out')),
                                  quantity=0,
                                  account_id=already_out_account_id)
                credit_line = dict(base_line,
                                   name=(name + ": " + str(qty_out) + _(' already out')),
                                   quantity=0,
                                   account_id=debit_account_id)

                percentage=self.percentage/100
                diff = diff * percentage

                if diff > 0:
                    debit_line['debit'] = diff
                    credit_line['credit'] = diff
                else:
                    # negative cost, reverse the entry
                    debit_line['credit'] = -diff
                    credit_line['debit'] = -diff
                AccountMoveLine.append([0, 0, debit_line])
                AccountMoveLine.append([0, 0, credit_line])

                if self.env.company.anglo_saxon_accounting:
                    advanced=self.cost_id.advanced_valuation_adjustment_lines.filtered(lambda c :c.product_id==self.product_id)
                    # expense_account_id = self.product_id.product_tmpl_id.get_product_accounts()['expense'].id
                    expense_account_id=self.quantity_out_account_id.id
                    debit_line = dict(base_line,
                                      name=(name + ": " + str(qty_out) + _(' already out')),
                                      quantity=0,
                                      account_id=expense_account_id)
                    credit_line = dict(base_line,
                                       name=(name + ": " + str(qty_out) + _(' already out')),
                                       quantity=0,
                                       account_id=already_out_account_id)

                    if diff > 0:
                        debit_line['debit'] = diff
                        credit_line['credit'] = diff
                    else:
                        # negative cost, reverse the entry
                        debit_line['credit'] = -diff
                        credit_line['debit'] = -diff
                    AccountMoveLine.append([0, 0, debit_line])
                    AccountMoveLine.append([0, 0, credit_line])

            return AccountMoveLine

    def _create_accounting_entries(self, move, qty_out):
        # TDE CLEANME: product chosen for computation ?
        cost_product = self.product_id
        if not cost_product:
            return False
        accounts = self.product_id.product_tmpl_id.get_product_accounts()
        debit_account_id = accounts.get('stock_valuation') and accounts['stock_valuation'].id or False
        # If the stock move is dropshipped move we need to get the cost account instead the stock valuation account
        if self.move_id._is_dropshipped():
            debit_account_id = accounts.get('expense') and accounts['expense'].id or False
        already_out_account_id = accounts['stock_output'].id
        credit_account_id = self.account_id.id or cost_product.categ_id.property_stock_account_input_categ_id.id

        if not credit_account_id:
            raise UserError(_('Please configure Stock Expense Account for product: %s.') % (cost_product.name))

        return self._create_account_move_line_advanved(move, credit_account_id, debit_account_id, qty_out, already_out_account_id)

