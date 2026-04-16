from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # This exposes the company field to the settings view
    # 'readonly=False' allows the user to change it from the settings page
    adv_payment_journal_id = fields.Many2one(
        'account.journal',
        domain=[('type','=','general')],
        string="Advance Payment Journal",
        config_parameter='pre_payment.adv_payment_journal_id',  # Unique parameter
        help="Select a journal for advance payment"
    )



    @api.model
    def set_values(self):
        # --- Your Validation Logic ---
        journal = self.adv_payment_journal_id
        if journal:
            adv_accounts=self.env['account.account'].search([('advanced','=',True)]).ids
            # Ensure journal is of type 'bank' or 'cash'
            if journal.type not in ['general']:
                raise UserError(_("Please select a journal of type 'Miscellaneous'."))
            #advanced_payment
            count_advance_move_parent= self.env['account.move'].search_count([('advanced_payment','!=',None),('journal_id','!=',journal.id),('parent_state','=','posted')]).ids
            if count_advance_move_parent:
                # count_advance_move= self.env['account.move.line'].search_count([('account_id','in',adv_accounts),('journal_id','!=',journal.id),('parent_state','=','posted'),('move_id','in',count_advance_move_parent)])
                # if count_advance_move:
                    raise UserError(_("Different journal is already used, please fix journal entries of advance payment first."))

        super().set_values()