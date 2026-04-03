from odoo import fields, models, api
from odoo.exceptions import UserError
from odoo.fields import Boolean


class AccountConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def _compute_allowed_changed(self):
        revs = self.env['reevaluation'].search_count([('state', '=', 'posted')])
        for re in self:
            if revs > 0:
                re.can_Allow_base_currency_accounts = False
            else:
                re.can_Allow_base_currency_accounts = True

    can_Allow_base_currency_accounts = fields.Boolean(string='can_Allow_base_currency_accounts', compute='_compute_allowed_changed')

    Allow_base_currency_accounts = fields.Boolean(

        string="Revaluation Base Currency Accounts",
        default=True
    )

    @api.model
    def get_values(self):
        res = super(AccountConfigSettings, self).get_values()

        params = self.env['ir.config_parameter'].sudo()
        Allow_base_currency_accounts = bool(params.get_param('Allow_base_currency_accounts'))
        can_Allow_base_currency_accounts = bool(params.get_param('can_Allow_base_currency_accounts'))
        res.update(
            Allow_base_currency_accounts=Allow_base_currency_accounts,
            can_Allow_base_currency_accounts=can_Allow_base_currency_accounts
        )
        return res

    def set_values(self):
        res = super(AccountConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param("Allow_base_currency_accounts",
                                                         self.Allow_base_currency_accounts)
        self.env['ir.config_parameter'].sudo().set_param("can_Allow_base_currency_accounts",
                                                         self.can_Allow_base_currency_accounts)
        return res


    revaluation_loss_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Revaluation loss account",
        domain=[("internal_type", "=", "other")],
    )
    revaluation_gain_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Revaluation gain account",
        domain=[("internal_type", "=", "other")],
    )

    currency_reval_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Currency gain & loss Default Journal",
        domain=[("type", "=", "general")],
    )


class AccountAccount(models.Model):
    _inherit = "account.account"

    currency_revaluation = fields.Boolean(
        string="Allow Currency revaluation", default=False
    )
