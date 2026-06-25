from odoo import api, fields, models


class DistributionPayment(models.Model):
    _name = 'distribution.payment'
    _description = 'Distribution Payment'
    _order = 'date desc, id desc'

    name = fields.Char(string="Reference", compute='_compute_name')
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    amount = fields.Monetary(string="Amount", required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string="Currency", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    state = fields.Selection(
        selection=[
            ('collected', 'Collected'),
            ('validated', 'Validated'),
        ],
        string="Status", default='collected', required=True,
        help="Collected = cash held by the distributor. "
             "Validated = handed over to the cashier and posted to accounting.",
    )
    delivery_run_id = fields.Many2one(
        'distribution.delivery.run', string="Delivery Run",
        required=True, ondelete='cascade', index=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order', string="Distribution Order",
        domain="[('is_distribution_order', '=', True)]",
        context={'is_distribution': True},
    )
    partner_id = fields.Many2one(
        'res.partner', related='sale_order_id.partner_id', string="Customer", store=True,
    )

    @api.depends('sale_order_id', 'date', 'amount')
    def _compute_name(self):
        for payment in self:
            ref = payment.sale_order_id.name or payment.delivery_run_id.name or ''
            payment.name = ("%s - %s" % (ref, payment.amount)).strip(' -')

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        # Late intake: a new payment recorded against an already (partially) closed run
        # flags it for re-validation so the manager validates the late customer intake.
        runs_to_flag = payments.delivery_run_id.filtered(
            lambda r: r.state in ('partial_closed', 'closed'))
        if runs_to_flag:
            runs_to_flag.write({'state': 'requires_validate'})
        return payments
