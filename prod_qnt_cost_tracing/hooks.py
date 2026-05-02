from odoo import api, SUPERUSER_ID


def post_init_hook(env):
    cr = env.cr

    """Backfill product trace records for existing valuation layers."""
    # env = api.Environment(cr, SUPERUSER_ID, {})
    valuation_layers = env['stock.valuation.layer'].search([], order='product_id, id')
    trace_model = env['stock.product.trace'].sudo()
    tracerecords =None
    current_product=None
    for vl in valuation_layers:
        if tracerecords:
            if current_product and current_product==vl.product_id.id:
                tracerecords=trace_model.create_from_valuation_layer(vl,tracerecords,True)
            else:
                if (current_product):
                    tracerecords.cost_system=tracerecords.product_id.standard_price
                tracerecords=trace_model.create_from_valuation_layer(vl,None,True)
                current_product=vl.product_id.id
        else:
            tracerecords=trace_model.create_from_valuation_layer(vl,None,True)
            current_product=vl.product_id.id
    if tracerecords:
        tracerecords.cost_system=tracerecords.product_id.standard_price
        
 
