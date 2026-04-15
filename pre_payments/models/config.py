from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # This exposes the company field to the settings view
    # 'readonly=False' allows the user to change it from the settings page
    adv_payment_journal_id = fields.Many2one(
        'account.journal',
        string="Advance Payment Journal",
        config_parameter='pre_payment.adv_payment_journal_id',  # Unique parameter
        help="Select a journal for advance payment"
    )