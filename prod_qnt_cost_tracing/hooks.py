from odoo import api, SUPERUSER_ID

def post_init_hook(cr, registry):
    """Backfill product trace records for existing valuation layers."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    valuation_layers = env['stock.valuation.layer'].search([], order='id')
    trace_model = env['stock.product.trace'].sudo()
    tracerecords =None
    for vl in valuation_layers:
        if tracerecords:
            tracerecords=tracerecords+ trace_model.create_from_valuation_layer(vl,tracerecords,True)
        else:
            tracerecords=trace_model.create_from_valuation_layer(vl,tracerecords,True)
        
