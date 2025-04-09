from odoo import models, fields, api



class AccountmoveAdvance(models.AbstractModel):
    _inherit = 'purchase.order'

    # Define a computed field that will return True if any purchase order line has received = 0
    totaly_received = fields.Integer(
        string='Is Received',
        compute='_compute_has_not_received_item',
        store=True,
    )

    totaly_invoiced = fields.Integer(
        string='Is Invoiced',
        compute='_compute_has_not_invoiced_item',
        store=True,
    )

    @api.depends('order_line.product_qty','order_line.qty_received')
    def _compute_has_not_received_item(self):
        aux=False
        for order in self:
            aux= all(line.qty_received == line.product_qty for line in order.order_line)
            if aux:
                order.totaly_received=1
            else:
                order.totaly_received=0
        
    @api.depends('order_line.product_qty','order_line.qty_invoiced')
    def _compute_has_not_invoiced_item(self):
        aux=False
        for order in self:
            aux= all(line.qty_invoiced == line.product_qty for line in order.order_line)
            if aux:
                order.totaly_invoiced=1
            else:
                order.totaly_invoiced=0