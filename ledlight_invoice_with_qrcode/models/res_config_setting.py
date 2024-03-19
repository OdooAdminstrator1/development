from odoo import api, fields, models, _
from ast import literal_eval


class ResConfigSettingsInherited(models.TransientModel):
    _inherit = 'res.config.settings'

    advance_payment_account_ids = fields.Many2many('account.account', domain=[('user_type_id.name', '=', 'Current Liabilities')])

    @api.model
    def get_values(self):
        res = super(ResConfigSettingsInherited, self).get_values()
        advance_payment_account_ids = self.env['ir.config_parameter'].sudo().get_param('ledlight_invoice_with_qrcode.advance_payment_account_ids')

        if advance_payment_account_ids:
            adv = [(6, 0, literal_eval(advance_payment_account_ids))]
        else:
            adv = False

        res.update(
            advance_payment_account_ids=adv,
        )
        return res

    def set_values(self):
        res = super(ResConfigSettingsInherited, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('ledlight_invoice_with_qrcode.advance_payment_account_ids', self.advance_payment_account_ids.ids)
        return res