from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountAccount(models.Model):
    _inherit = 'account.account'

    advanced = fields.Boolean(index=True, default=False, string="Advanced Account")

    @api.constrains('account_type', 'advanced')
    def _check_advanced_account_type(self):
        for record in self:
            # Check the "Advanced" logic
            # In Odoo 16, 'asset_current' and 'liability_current' are the selection keys
            if record.advanced and record.account_type not in ('asset_current', 'liability_current'):
                raise ValidationError(_('Advanced Account must be of type "Current Assets" or "Current Liabilities".'))

            # Note: Odoo 16 core already prevents multiple 'equity_unaffected' accounts.
            # If you still want a custom check for it, it would look like this:
            if record.account_type == 'equity_unaffected':
                domain = [
                    ('account_type', '=', 'equity_unaffected'),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id)
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(_('You cannot have more than one account with "Current Year Earnings" as type.'))

