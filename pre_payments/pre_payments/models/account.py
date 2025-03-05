from odoo import models, fields, api, _
from odoo.exceptions import  ValidationError


class AccountAccount(models.Model):
    _inherit = 'account.account'

    advanced = fields.Boolean(index=True, default=False , string="Advanced Account")

    @api.constrains('user_type_id')
    def _check_user_type_id(self):
        data_unaffected_earnings = self.env.ref('account.data_unaffected_earnings')
        data_account_type_current_liabilities= self.env.ref('account.data_account_type_current_liabilities')
        data_account_type_current_assets= self.env.ref('account.data_account_type_current_assets')
        result = self.read_group([('user_type_id', '=', data_unaffected_earnings.id)], ['company_id'], ['company_id'])
        for res in result:
            if res.get('company_id_count', 0) >= 2:
                account_unaffected_earnings = self.search([('company_id', '=', res['company_id'][0]),
                                                           ('user_type_id', '=', data_unaffected_earnings.id)])
                raise ValidationError(_('You cannot have more than one account with "Current Year Earnings" as type. (accounts: %s)') % [a.code for a in account_unaffected_earnings])
        if self.user_type_id not in (data_account_type_current_liabilities,data_account_type_current_assets) and self.advanced:
            raise ValidationError('Avanced Account must be current_liabilities or current_assets')

