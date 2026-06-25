from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    delivery_run_id = fields.Many2one(
        'distribution.delivery.run', string="Distribution Run", copy=False, index=True,
        help="Delivery run whose validated intake produced this accounting payment.",
    )
    distribution_master_order_id = fields.Many2one(
        'sale.order', string="Reconciled Master Order", copy=False,
        help="Master order against whose invoice this run payment was reconciled.",
    )
