# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from lxml import etree


class AccrualBill(models.Model):
    _name = 'account.move'
    _inherit = 'account.move'

    is_accrual = fields.Boolean('IS Accrual', readonly=True, default=False, index=True)
    is_matched = fields.Boolean('matched', readonly=True, default=False, index=True)
    we_have_accrual_not_matched = fields.Boolean('Need accrual matching', readonly=True, compute = '_compute_we_have_accrual_not_matched', default=False)
    acc_bill_id = fields.Many2many('account.move', 'rel_accrual_bill_match_real_bill', 'real_bill_id',
                                   'accrual_bill_id')

    def _move_autocomplete_invoice_lines_values(self):
        if self.is_accrual:
            self.line_ids = self._get_credit_debit_accrual_line()
            self.line_ids.filtered(lambda x:x.debit >0).exclude_from_invoice_tab = False
            self.invoice_line_ids = self.invoice_line_ids.filtered(lambda v: not v.exclude_from_invoice_tab)
            # for line in self.line_ids:
            #     if not line._cache.get('account_id') and not line.display_type and not line.exclude_from_invoice_tab:
            #         line.account_id = line._get_computed_account()
            # self.line_ids._onchange_price_subtotal()
            # self._recompute_dynamic_lines(recompute_all_taxes=True)

            values = self._convert_to_write(self._cache)
            # values.pop('invoice_line_ids', None)
            return values
        else:
            return super(AccrualBill, self)._move_autocomplete_invoice_lines_values()

    @api.onchange('is_accrual')
    def _onchange_is_accrual(self):
        if self.is_accrual:
            self.journal_id = self._get_accrual_journal_type()
            if self.journal_id.currency_id:
                self.currency_id = self.journal_id.currency_id
            else:
                self.currency_id = self.company_id.currency_id

    @api.model
    def _get_default_journal(self):
        if self.is_accrual:
            return self._get_accrual_journal_type()
        else:
            return super(AccrualBill, self)._get_default_journal()

    def _get_accrual_journal_type(self):
        return self.env['account.journal'].search([('name', '=', 'Accrual Journal'), ('code', '=', 'ACC')], limit=1)

    @api.onchange('journal_id')
    def _onchange_journal(self):
        super(AccrualBill, self)._onchange_journal()
        if self.is_accrual:
            self._onchange_invoice_line_ids()

    def button_draft(self):
        # OVERRIDE

        # check if it is and accrual matched to a bill
        for res in self:
            if res.is_accrual and res.move_type == 'entry' and res.is_matched:
                raise UserError(_('You cannot rest to draft a matched accrual bill, please remove it from the related bill'))
            # DeInverse the related accrual bill if any
            if res.move_type == 'in_invoice' and not res.is_accrual:
                res.acc_bill_id = [(6, 0, [])]
                # for matched_accrual in res.acc_bill_id:
                #     res._deiverse_accrual_journal(accrual=matched_accrual)
                #     matched_accrual.is_matched = False

        super(AccrualBill, self).button_draft()

    def button_cancel(self):
        # OVERRIDE

        if self.move_type == 'in_invoice' and not self.is_accrual:
            for matched_accrual in self.acc_bill_id:
                self._deiverse_accrual_journal(accrual=matched_accrual)

        super(AccrualBill, self).button_cancel()

    def convert_object_to_write(self, obj):
        vals = {}
        fields = obj._fields
        for f in fields:
            field = fields[f]
            value = field.convert_to_write(obj[f], self)
            vals[f] = value

        return vals

    def _inverse_accrual_journal(self, accrual):
        line_ids = accrual.line_ids
        new_line_ids = []
        # if not accrual.ref:
        #     move_ref = 'Inverse-'
        # else:
        #     move_ref = 'Inverse-' + accrual.ref
        move_ref = self.ref
        move_date = self.date

        credit_line = line_ids.filtered(lambda v: v.credit > 0)

        credit_value = self.convert_object_to_write(credit_line)
        debit_line = line_ids.filtered(lambda v: v.debit > 0)
        debit_value = self.convert_object_to_write(debit_line)
        credit_value['debit'] = debit_value['debit']
        debit_value['credit'] = credit_value['credit']

        credit_value['credit'] = 0
        credit_value['move_id'] = False
        credit_value['id'] = False
        credit_value['ref'] = move_ref
        credit_value['date'] = move_date
        credit_value['product_id'] = False
        credit_value['date_maturity'] = move_date
        credit_value['exclude_from_invoice_tab'] = True
        credit_value['amount_residual'] = 0
        credit_value['matched_accrual_id'] = accrual.id

        debit_value['debit'] = 0
        debit_value['move_id'] = False
        debit_value['id'] = False
        debit_value['ref'] = move_ref
        debit_value['product_id'] = False
        debit_value['date'] = move_date
        debit_value['date_maturity'] = move_date
        debit_value['exclude_from_invoice_tab'] = True
        debit_value['amount_residual'] = 0
        debit_value['matched_accrual_id'] = accrual.id

        # for line in self.line_ids:
        #     new_line_ids.append((0,0,line))

        new_line_ids.append((0, 0, credit_value))
        new_line_ids.append((0, 0, debit_value))
        self.line_ids = new_line_ids
        # self.env['account.move'].create({
        #     'type': 'entry',
        #     'ref': move_ref,
        #     'date': move_date,
        #     'journal_id': accrual.journal_id.id,
        #     'company_id': accrual.company_id.id,
        #     'line_ids': new_line_ids
        # })

    def _deiverse_accrual_journal(self, accrual):
        invese_lines = self.line_ids.filtered(lambda rec: rec.matched_accrual_id == accrual.id)
        deleted_lines = []
        for delete_line in invese_lines:
            deleted_lines.append((3, delete_line.id))

        self.update({'line_ids': deleted_lines})

    @api.model
    def create(self, vals_list):
        # for val in vals_list:
        if 'default_is_accrual' in self._context and self._context.get('default_is_accrual'):
            default_debit_credit_journal_type_id = self.env['account.journal'].search([('id', '=', vals_list['journal_id'])]).default_account_id
            if not default_debit_credit_journal_type_id:
                raise ValidationError('please add default debit/credit account for journal type')

        moves = super(AccrualBill, self).create(vals_list)
        return moves

    def write(self, vals):
        if 'acc_bill_id' in vals:
            deleted_ids = set(self.acc_bill_id.ids) - set(vals['acc_bill_id'][0][2])
            new_ids = vals['acc_bill_id'][0][2]
            delete_obj = self.env['account.move'].search([('id', 'in', list(deleted_ids))])
            new_obj = self.env['account.move'].search([('id', 'in', list(new_ids))])
            for item in delete_obj:
                item.is_matched = False
                self._deiverse_accrual_journal(accrual=item)
            for item in new_obj:
                if not item.is_matched:
                    item.is_matched = True
                    self._inverse_accrual_journal(accrual=item)

        return super(AccrualBill, self).write(vals)


    # Matching Accrual Bill method
    def _get_unmatched_accrual_bill(self):
        return self.env['account.move'].search([('is_accrual', '=', True), ('is_matched', '=', False),
                                                ('line_ids.account_id', 'in', self.real_bill_id.line_ids.account_id.ids)])

    def show_matched_accrual_list(self):
        self.ensure_one()
        copy_context = dict(self.with_context(arr=self.invoice_line_ids.account_id.ids, current_invoice_date= self.date)._context)
        res = self.env['ir.actions.act_window']._for_xml_id('ict_accrual_expenses.matching_bill_tree_view_check_box_action')
        res.update(
            context=dict(copy_context),
            res_id=self.id
        )
        return res

    # ------------------end matching method--------------------------
    def _compute_we_have_accrual_not_matched(self):

        if self.is_accrual:
            self.we_have_accrual_not_matched = False
        else:
            count = self.env['account.move'].search_count([('is_accrual', '=', True), ('line_ids.account_id', 'in', self.line_ids.account_id.ids), ('is_matched', '=', False)])

            if count > 0:
                if len(self.line_ids.filtered(lambda v: v.matched_accrual_id > 0)) > 0:
                    self.we_have_accrual_not_matched = False
                else:
                    self.we_have_accrual_not_matched = True
            else:
                self.we_have_accrual_not_matched = False

    @api.onchange('invoice_line_ids')
    def _get_invoice_line_count(self):
        if ('is_accrual' in self._context and self._context['is_accrual']) or self.is_accrual:
            self.ensure_one()
            count = 0
            for line in self.invoice_line_ids:
                count = count + 1

            if count > 1:
                raise ValidationError(_('Only one line allowed'))

    def show_accrual_bill(self):
        self.ensure_one()
        copy_context = dict(self.env.context)
        res = self.env['ir.actions.act_window']._for_xml_id('ict_accrual_expenses.ict_accrual_expenses_accrual_bill_action')
        res.update(
            context=dict(copy_context, default_is_accrual=True, default_type='entry'),
            domain=[('is_accrual','=', True) ]
        )
        return res

    @api.depends('move_type')
    def _compute_invoice_filter_type_domain(self):
       # OVERIDE
        for move in self:
            if move.is_accrual:
                move.invoice_filter_type_domain = 'purchase'
            else:
                super(AccrualBill, self)._compute_invoice_filter_type_domain()

    @api.onchange('invoice_line_ids')
    def _onchange_invoice_line_ids(self):
        # OVERRIDE

        if self.is_accrual:
            self.line_ids = self._get_credit_debit_accrual_line()
            self.invoice_line_ids = self.invoice_line_ids.filtered(lambda v: not v.exclude_from_invoice_tab)
            # self.invoice_line_ids.price_total = self.invoice_line_ids._get_price_total_and_subtotal()['price_subtotal']
        else:
            super(AccrualBill, self)._onchange_invoice_line_ids()

    def _get_credit_debit_accrual_line(self):
        line_ids = []
        res = self.env['account.move.line']
        if self.invoice_line_ids and self.is_accrual:
            invoice_lines = self.invoice_line_ids[0]
            subtotal = invoice_lines.quantity * invoice_lines.price_unit
            invoice_lines.price_subtotal = subtotal
            currency = self.currency_id
            amount_currency = 0

            credit_acc_id = self.journal_id.default_account_id
            debit_acc_id = invoice_lines.account_id

            credit_line = self.env['account.move.line'].new({'amount_currency': amount_currency,
                                                             'account_id': credit_acc_id.id, #credit_acc_id,
                                                             'credit': subtotal,
                                                             'ref': self.ref,
                                                             'move_id': self.id,
                                                             'name': invoice_lines.name,
                                                             'exclude_from_invoice_tab': True,
                                                             'price_subtotal': subtotal,
                                                             'price_total': subtotal,
                                                             'price_unit': invoice_lines.price_unit,
                                                             'is_rounding_line': False,
                                                             'date_maturity': self.invoice_date,
                                                             'is_accrual': True
                                                             })
            res |= credit_line
            debit_line = self.env['account.move.line'].new({'amount_currency': amount_currency,
                                                            'account_id': debit_acc_id.id,
                                                            'ref': self.ref,
                                                            'name': invoice_lines.name,
                                                            'debit': subtotal,
                                                            'move_id': self.id,
                                                            'exclude_from_invoice_tab': True,
                                                            'price_subtotal': subtotal,
                                                            'price_total': subtotal,
                                                            'price_unit': invoice_lines.price_unit,
                                                            'is_rounding_line': False,
                                                            'amount_residual': subtotal,
                                                            'is_accrual': True,
                                                            'product_id': invoice_lines.product_id,
                                                            'quantity': invoice_lines.quantity,
                                                            'product_uom_id': invoice_lines.product_uom_id
                                                            })
            res |= debit_line
        return res

    @api.model
    def _move_autocomplete_invoice_lines_create(self, vals_list):
        new_vals_list = []

        for val in vals_list:
            if 'is_accrual' in val and val['is_accrual'] :
                # In accrual case we have only on invoice_line_ids and 2 line_ids autocomputed so we override this
                # function to prepare vals_list correctly
                move = self.new(vals_list[0])
                if 'line_ids' in val:
                    new_vals_list.append(val)
                else:
                    move.line_ids = move._get_credit_debit_accrual_line()
                    if len(move.invoice_line_ids.filtered(lambda v: not v.exclude_from_invoice_tab)) > 1:
                        raise UserError("Only one line allowed")
                    move.invoice_line_ids = move.invoice_line_ids.filtered(lambda v: not v.exclude_from_invoice_tab)
                    invoice_line = move.invoice_line_ids._convert_to_write(move.invoice_line_ids._cache)
                    debit_line = move.line_ids.filtered(lambda v: v.debit > 0)
                    debit_line.exclude_from_invoice_tab = False
                    debit_line.product_id = invoice_line['product_id']
                    debit_line.quantity = invoice_line['quantity']
                    debit_line.price_unit = invoice_line['price_unit']
                    debit_line.price_subtotal = invoice_line['price_subtotal']
                    res = move._convert_to_write(move._cache)
                    res.pop('invoice_line_ids', None)
                    new_vals_list.append(res)
            else:
                res = super(AccrualBill, self)._move_autocomplete_invoice_lines_create([val])
                new_vals_list.append(res[0])
        return new_vals_list

    @api.model
    def initialize_journal_type(self):

        company_ids = self.env['res.company'].search([])
        for c_id in company_ids:
            count = self.env['account.journal'].search_count(
                [('name', '=', 'Accrual Journal'), ('company_id', '=', c_id.id)])
            if count <= 0:
                journal_type_id = self.env['account.journal'].create({
                    'name': 'Accrual Journal',
                    'type': 'general',
                    'code': 'ACC',
                    'company_id': c_id.id,
                    'currency_id': c_id.currency_id.id,
                    'sapps_accrued_journal': True
                }).id


class AccrualLines(models.Model):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    is_accrual = fields.Boolean('is accrual', readonly=True, default=False)
    matched_accrual_id = fields.Integer(string='matched accrual', default=False)

    @api.onchange('product_id')
    def _onchange_product_id_accrual(self):
        for line in self:
            if line.is_accrual and line.product_id:
                if line.product_id.property_account_expense_id:
                    line.account_id = line.product_id.property_account_expense_id
                else:
                    line.account_id = line.product_id.categ_id.property_account_expense_categ_id

    def _get_computed_account(self):
        res = super(AccrualLines, self)._get_computed_account()
        if not res and self.product_id and self.is_accrual:
            res = self.account_id

        return res

    @api.onchange('quantity', 'discount', 'price_unit', 'tax_ids')
    def _onchange_price_subtotal(self):
        for line in self:
            if line.is_accrual:
                line.update(line._get_price_total_and_subtotal())
                line.update(line._get_fields_onchange_subtotal())
            else:
                super(AccrualLines, self)._onchange_price_subtotal()


class AccountJournalInherited(models.Model):
    _inherit = 'account.journal'

    sapps_accrued_journal = fields.Boolean(default=False)