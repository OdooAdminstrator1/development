# Copyright 2019 ForgeFlow S.L. (https://www.forgeflow.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _


class StockMove(models.Model):
    _inherit = "stock.picking"



    def action_get_all_account_moves(self):
        self.ensure_one()
        action_ref = self.env.ref('account.action_move_journal_line')
        if not action_ref:
            return False
        action_data = action_ref.read()[0]
        ids=[]
        for stock in self.move_lines:
            ids.append(stock.account_move_ids.id)
        action_data['domain'] = [('id', 'in', ids)]
        return action_data

class StockMove(models.Model):
    _inherit = "mrp.production"



    def action_get_all_account_moves(self):
        self.ensure_one()
        action_ref = self.env.ref('account.action_move_journal_line')
        if not action_ref:
            return False
        action_data = action_ref.read()[0]
        ids=[]
        for stock in self.move_raw_ids:
            for move in stock.account_move_ids:
                ids.append(move.id)

        for stock in self.move_finished_ids:
            for move in stock.account_move_ids:
                ids.append(move.id)
        action_data['domain'] = [('id', 'in', ids)]
        return action_data

class AccountMove(models.Model):
    _inherit = "account.move"

    active_model=fields.Char()
    active_id=fields.Integer()
    is_manual=fields.Boolean("Created manually",compute='_compute_is_manual',search='_search_is_manual')
    is_reversed=fields.Boolean(compute='_compute_is_reversed')
    parent = fields.Char(compute='_compute_parent')
    reversal_by= fields.Many2one('account.move', string="Reversal by", readonly=True, copy=False)
    reversal_by_name=fields.Char()

    def _search_is_manual(self, operator, value):
        lines = self.env['account.move'].search([])
        li=lines[0]
        line_ids = lines.filtered(lambda line: line.is_manual == value).ids
        return [('id', 'in', line_ids)]

    def _compute_is_manual(self):

        for record in self:
            manual = True
            if not record.line_ids:
                record.is_manual=False
            else:
                if record.move_type!='entry':
                    manual = False
                if record.move_type=='entry':
                    for line in record.line_ids:
                        if line.name:
                            manual=False
            record.is_manual=manual

    def _compute_is_reversed(self):

        for record in self:
            revers=self.env['account.move'].search_count([('reversed_entry_id', '=', record.id)])
            if revers>0:
                record.is_reversed=True
                record.reversal_by=self.env['account.move'].search([('reversed_entry_id', '=', record.id)])[0]
                record.reversal_by_name="Reversed By"
            else:
                record.is_reversed = False

    def button_fixed(self):

        fixed_EIDs = self.env['account.move'].search([('amount_total_signed', '=', 0), ('state', '=', 'posted'),('reversed_entry_id', '!=', False)])
        for eid in fixed_EIDs:
            if eid.amount_total_signed != eid.reversed_entry_id.amount_total_signed:
                eid.mapped('line_ids').remove_move_reconcile()
                eid.reversed_entry_id.mapped('line_ids').remove_move_reconcile()
                eid.write({'state': 'cancel'})
                eid.reversed_entry_id.write({'state': 'cancel'})




    def _compute_parent(self):

        for record in self:
            record.parent = False
            if record.is_manual:
                record.parent=False
            else:
                if record.stock_move_id:
                    record.parent = "Source"
                    record.active_model='stock.move'
                    record.active_id=record.stock_move_id.id
                else:
                    payment=False
                    if record.line_ids:
                        for line in record.line_ids:
                            if line.name=='Currency exchange rate difference':
                                if line.matched_credit_ids:
                                    payment=line.matched_credit_ids.credit_move_id.payment_id
                                if line.matched_debit_ids:
                                    payment = line.matched_debit_ids.debit_move_id.payment_id

                            if line.payment_id:
                                record.parent = "Source"
                                record.active_model = 'account.payment'
                                record.active_id = line.payment_id.id
                        if payment:
                            record.parent = "Source"
                            record.active_model = 'account.payment'
                            record.active_id = payment.id


    def action_get_reversed(self):
        self.ensure_one()
        if self.is_reversed:
            name = _('Reversed By')
            view_mode = 'tree,form'
            return {
                'name': name,
                'view_mode': view_mode,
                'res_model': 'account.move',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': self.reversal_by.id,
                'domain': [('id', '=', self.reversal_by.ids)],
                'context': self.env.context,

            }

    def action_get_parent(self):
        self.ensure_one()
        if self.active_model:

            name = _('Source')
            view_mode = 'tree,form'
            return {
                'name': name,
                'view_mode': view_mode,
                'res_model': self.active_model,
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': self.id,
                'domain': [('id', '=', self.active_id)],
                'context':self.env.context,

                 }

        else:
            return False