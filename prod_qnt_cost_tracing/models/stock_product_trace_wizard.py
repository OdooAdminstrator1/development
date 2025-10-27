from odoo import models, fields

class ProductTraceWizard(models.TransientModel):
    _name = 'stock.product.trace.wizard'
    _description = 'Product Trace Date Filter Wizard'

    date = fields.Date('Accounting Date', required=True, default=fields.Date.today)

    def action_apply_filter(self):
        self.ensure_one()
        dd = fields.Datetime.to_datetime(self.date)
        latest_traces = self.env['stock.product.trace'].get_latest_traces_fast(dd)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Traces',
            'res_model': 'stock.product.trace',
            'view_mode': 'tree',
            'domain': [('id', 'in', latest_traces)],
            'target': 'current',
        }