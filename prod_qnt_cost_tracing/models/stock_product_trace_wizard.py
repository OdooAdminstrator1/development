from odoo import models, fields

class ProductTraceWizard(models.TransientModel):
    _name = 'stock.product.trace.wizard'
    _description = 'Product Trace Date Filter Wizard'

    date = fields.Date('Accounting Date', required=True, default=lambda self: self.env.context.get('default_process_date',fields.Date.today()))
      

    def action_apply_filter(self):
        self.ensure_one()
        dd = fields.Datetime.to_datetime(self.date)
        latest_traces,tot = self.env['stock.product.trace'].get_latest_traces_fast(dd)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Traces',
            'res_model': 'stock.product.trace',
            'view_mode': 'tree',
            'view_id': self.env.ref('prod_qnt_cost_tracing.view_stock_product_trace_tree_resume').id,
            'domain': [('id', 'in', latest_traces)],
            'target': 'current',
            'context' : {'filterbydate': True,'Total':tot},
        }
    
    def action_update_move_dates(self):
        # selected records from tree view
        active_ids = self.env.context.get('active_ids', [])
        trace_model = self.env['stock.product.trace'].sudo()
        trace_model.update_move_dates(active_ids,self.date)
        return {'type': 'ir.actions.act_window_close'}