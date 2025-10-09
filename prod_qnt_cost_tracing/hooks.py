# from odoo import api, SUPERUSER_ID

# def post_init_hook(cr, registry):
#     """Backfill product trace records for existing valuation layers."""
#     env = api.Environment(cr, SUPERUSER_ID, {})
#     valuation_layers = env['stock.valuation.layer'].search([],  order="id ASC")
#     trace_model = env['stock.product.trace'].sudo()

#     for vl in valuation_layers:
#         if not trace_model.search_count([('move_id', '=', vl.account_move_id.id)]):
#             trace_model.create_from_valuation_layer(vl)
from odoo import api, SUPERUSER_ID

def post_init_hook(cr, registry):
    """Backfill product trace records for existing valuation layers."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    valuation_layers = env['stock.valuation.layer'].search([], order='id')
    trace_model = env['stock.product.trace'].sudo()

    for vl in valuation_layers:
        # Skip if trace already exists for this valuation layer
        if trace_model.search_count([('move_id', '=', vl.account_move_id.id)]):
            continue
        if not vl.account_move_id.id:
            continue

        product_id = vl.product_id.id
        loc_id=vl.stock_move_id.location_id
        loc_dest_id=vl.stock_move_id.location_dest_id
        stock_landed_cost_id =vl.stock_landed_cost_id
        is_finished=False
        is_unbuild=vl.stock_move_id.unbuild_id
       # is_component=vl.stock_move_id.raw_material_production_id
        loc_usage=vl.stock_move_id.location_id.usage
        loc_dest_usage=vl.stock_move_id.location_dest_id.usage
        is_finished= vl.stock_move_id.production_id
        is_component=not (is_unbuild and product_id==is_unbuild.product_id.id)

        #  Get the latest trace record for the same product
        last_trace = trace_model.search(
            [('product_id', '=', product_id)],
            order='id desc',
            limit=1
        )

        #  Determine old cost value
        cost_old_value = last_trace.cost_new_value if last_trace else 0.0
        qty_old_value = last_trace.qty_new if last_trace else 0.0
        cost_avg_new =last_trace.cost_old_value if last_trace else vl.unit_cost

        #  Create the trace from valuation layer
        new_trace = trace_model.create_from_valuation_layer(vl)

        #  Update the old cost value
       # new_trace.cost_old_value = cost_old_value
        new_trace.cost_old_value=cost_old_value
        new_trace.qty_new = qty_old_value+new_trace.qty_done
        new_trace.qty_old = qty_old_value

        new_trace.cost_new_value=cost_old_value if last_trace else vl.unit_cost
        new_avg_cost=(cost_old_value*qty_old_value+new_trace.qty_done*vl.unit_cost)/(qty_old_value+new_trace.qty_done)

        if stock_landed_cost_id:
            new_trace.stock_move_type='landed_cost'
            new_trace.cost_new_value=(vl.value+cost_old_value*qty_old_value)/qty_old_value

        elif loc_id.name=='Vendors':
            new_trace.stock_move_type='preceipt'
            new_trace.cost_new_value=new_avg_cost
        elif loc_id.name=='Customers':
            new_trace.stock_move_type='sreturn'
        elif loc_dest_id.name=='Vendors':
            new_trace.stock_move_type='preturn'
        elif loc_dest_id.name=='Customers':
            new_trace.stock_move_type='sdeliver'
        elif loc_id.name=='Inventory adjustment' or loc_dest_id.name=='Inventory adjustment':
            new_trace.stock_move_type='adjustment'
        elif (not loc_id.name) and  (not loc_dest_id):
            new_trace.stock_move_type='cost_manually'
            new_trace.cost_new_value=cost_old_value+vl.value/qty_old_value
        elif (loc_dest_id.name=='Scrap'):
            new_trace.stock_move_type='scrap'
        elif (loc_dest_usage=='inventory'):
            new_trace.stock_move_type='inventory_loss'
        elif (is_finished and loc_id.name=='Production'):
            new_trace.stock_move_type='manufacturing'
            new_trace.cost_new_value=new_avg_cost
        elif (is_unbuild and product_id==is_unbuild.product_id.id and loc_dest_id.name=='Production'):
            new_trace.stock_move_type='unbuilt'
        elif (is_component and loc_id.name=='Production'):
            new_trace.stock_move_type='unbuilt_raw'
        elif (is_component and loc_dest_id.name=='Production'):
            new_trace.stock_move_type='manufacturing_raw'
        else:
            new_trace.stock_move_type='undefined'
