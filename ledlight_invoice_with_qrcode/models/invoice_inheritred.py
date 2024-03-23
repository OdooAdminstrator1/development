# customer in parent invoice should have same customer in matched advance
# you cannot match with already matched advance invoice
from ast import literal_eval
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

class AccountMoveLineInherited(models.Model):
    _inherit = 'account.move.line'

    matched_advance_id = fields.Many2one('account.move')


class AccountMoveInherited(models.Model):
    _inherit = 'account.move'

    matched_invoice_ids = fields.Many2many('account.move', 'rel_match_invoice_advance', 'real_invoice_id',
                                             'advance_invoice_id', domain=[('move_type', '=', 'out_invoice')]
                                           )
    is_matched = fields.Boolean('Is Matched', default=False, copy=False)
    default_destination_domain = fields.Char(string="Field Invoice Matching", compute='_compute_invoice_matching_domain')

    def _compute_invoice_matching_domain(self):
        for rec in self:
            rec.default_destination_domain = json.dumps([('partner_id', '=', self.partner_id.id),
                                                         ('move_type', '=', 'out_invoice'),
                                                         ('is_matched', '=', False)
                                                         ])

    def write(self, vals):
        if 'matched_invoice_ids' in vals:
            deleted_ids = set(self.matched_invoice_ids.ids) - set(vals['matched_invoice_ids'][0][2])
            new_ids = vals['matched_invoice_ids'][0][2]
            delete_obj = self.env['account.move'].search([('id', 'in', list(deleted_ids))])
            new_obj = self.env['account.move'].search([('id', 'in', list(new_ids))]).filtered(lambda v: not v.is_matched)

            self.de_apply_match(delete_obj)
            self.apply_match(new_obj)

        return super(AccountMoveInherited, self).write(vals)

    def show_matched_accrual_list(self):
        self.ensure_one()
        copy_context = dict(self.with_context(arr=self.invoice_line_ids.account_id.ids, current_invoice_date= self.date)._context)
        res = self.env['ir.actions.act_window']._for_xml_id('ledlight_invoice_with_qrcode.matching_invoice_tree_view_check_box_action')
        res.update(
            context=dict(copy_context),
            res_id=self.id,
            domain=[[('move_type', '=', 'out_invoice'), ('is_matched', '=', False), ('partner_id', '=', self.id)]]
        )
        return res

    def button_draft(self):
        # OVERRIDE
        result = super(AccountMoveInherited, self).button_draft()
        for res in self:
            if res.is_matched:
                raise UserError(_('You cannot rest to draft a matched advance customer, please remove it from the related invoice'))
            # DeInverse the related accrual bill if any
            if res.move_type == 'out_invoice' and len(res.matched_invoice_ids) > 0:
                res.matched_invoice_ids = [(6, 0, [])]
        return result

    def de_apply_match(self, invoices):
        self.ensure_one()
        if not invoices:
            return
        for item in invoices:
            item.is_matched = False
            lines_to_remove = self.invoice_line_ids.filtered(lambda v: v.matched_advance_id.id == item.id)
            self.invoice_line_ids = [(3, elem.id) for elem in lines_to_remove]
        self._onchange_invoice_line_ids()
        self._recompute_dynamic_lines(recompute_all_taxes=True, recompute_tax_base_amount=True)

    def apply_match(self, invoices):
        self.ensure_one()
        advance_account_ids_config = self.env['ir.config_parameter'].sudo().get_param('ledlight_invoice_with_qrcode.advance_payment_account_ids')
        advance_account_ids = literal_eval(advance_account_ids_config) if advance_account_ids_config else []
        sales_taxes = self.env['account.tax'].sudo().search([('type_tax_use', '=', 'sale')])
        tax_account_ids = sales_taxes.invoice_repartition_line_ids.account_id.ids
        new_line_ids = []
        lumpsum_tax = 0
        for invoice in invoices:
            if invoice.is_matched:
                raise UserError(_("Already Matched Invoice %s")%(invoice.name))
            invoice.is_matched = True
            for advance_account_id in advance_account_ids:
                total_of_advance = sum(line.balance for line in invoice.line_ids.filtered(lambda v: v.account_id.id == advance_account_id))
                if abs(total_of_advance) > 0:
                    new_line_ids.append((0, 0, {
                                        'price_unit': total_of_advance,
                                        'name': "Advanced Customer %s"%(invoice.name),
                                        'exclude_from_invoice_tab': False,
                                        'amount_residual': 0,
                                        'price_subtotal': total_of_advance,
                                        'matched_advance_id': invoice.id,
                                        'account_id': advance_account_id
                                     }))
            for tax_account_id in tax_account_ids:
                lumpsum_tax += sum(line.balance for line in invoice.line_ids.filtered(lambda v: v.account_id.id == tax_account_id))
                already_matched_invoices_tax = sum(line.balance for line in self.matched_invoice_ids.line_ids.filtered(lambda v: v.account_id.id == tax_account_id))
                lumpsum_tax += already_matched_invoices_tax
        self.invoice_line_ids = new_line_ids
        tax_line = self.line_ids.filtered(lambda v: v.tax_line_id.id != False)
        receivable_account = self.partner_id.property_account_receivable_id
        receivable_line = self.line_ids.filtered(lambda v: v.account_id.id == receivable_account.id)
        self.line_ids = [(1, tax_line.id, {'credit': tax_line.credit + lumpsum_tax}),
                         (1, receivable_line.id, {'debit': receivable_line.debit + lumpsum_tax}),
                         ]