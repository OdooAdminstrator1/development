from odoo import models, fields

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    cash_user_ids = fields.Many2many(
        'res.users',
        'account_journal_res_users_rel',  # Relation table name
        'journal_id',                     # Current model field
        'user_id',                        # Target model field
        string='Authorized Cash Users',
        help="Users authorized to process payments using this cash journal."
    )