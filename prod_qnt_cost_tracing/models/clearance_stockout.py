from odoo import models, fields, tools , _
import ast

class ClearnessStockout(models.Model):
    _name = "clearance.stockout.sorder"
    _auto = False 
    
    order_id = fields.Many2one('sale.order', 'Sale Order', readonly=True)
    sumstock = fields.Float('Total Delivery', readonly=True)
    sumbill = fields.Float('Total Invoices', readonly=True)
    balance = fields.Float('Difference', readonly=True)
    date = fields.Datetime(string='Date', related='order_id.date_order',readonly=True,)


    def init(self):
        """Initialize SQL view"""
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
select row_number() OVER(order by A.id) AS id, A.id as order_id,A.sumstock,COALESCE( B.sumbill,0) as sumbill,(A.SumStock+COALESCE( B.sumbill,0)) as balance from (
select po.id,po.name, sum(accl.balance) as SumStock
from sale_order as po
inner join stock_move as sm on sm.origin=po.name
inner join stock_picking as sp on sp.id=sm.picking_id
inner join account_move  as  accm on accm.stock_move_id=sm.id
inner join account_move_line as  accl on accl.move_id=accm.id
where po.state='sale' and sp.state='done' and accl.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and accl.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date       
group by po.id,po.name
) as A
left join 
(
select po.id,po.name, sum(accl.balance) as sumbill
from sale_order as po
inner join sale_order_line  as  pol on pol.order_id=po.id
inner join account_move_line as  accl on accl.product_id=pol.product_id
where po.state='sale' and accl.parent_state='posted' and 
                        accl.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and accl.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date     
group by po.id,po.name
) as B on A.id=B.id
where (B.SumBill is null or ((A.SumStock+ B.SumBill) <>0) )
                         
        )
        """ % self._table)


    def getSummary2(self):
        return {
                'stockin' : self.getSum(),
                'difference' : self.getSumDifference(),
            }
    

    def getSum(self):
        sqql="""
select sum(accl.balance) as SumStock
from 
 account_move_line as  accl 
where 
accl.parent_state='posted' and
	 accl.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )  
"""

        self._cr.execute(sqql)
        query_res = self._cr.fetchone()
        if query_res:
            return query_res[0]
        

    def getSumDifference(self):
        sqql="""
select sum(A.SumStock+COALESCE( B.sumbill,0)) as balance from (
select po.id,po.name, sum(accl.balance) as SumStock
from sale_order as po
inner join stock_move as sm on sm.origin=po.name
inner join stock_picking as sp on sp.id=sm.picking_id
inner join account_move  as  accm on accm.stock_move_id=sm.id
inner join account_move_line as  accl on accl.move_id=accm.id
where po.state='sale' and sp.state='done' and accl.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and accl.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date       
group by po.id,po.name
) as A
left join 
(
select po.id,po.name, sum(accl.balance) as sumbill
from sale_order as po
inner join sale_order_line  as  pol on pol.order_id=po.id
inner join account_move_line as  accl on accl.product_id=pol.product_id
where po.state='sale' and accl.parent_state='posted' and 
                        accl.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and accl.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date     
group by po.id,po.name
) as B on A.id=B.id
where (B.SumBill is null or ((A.SumStock+ B.SumBill) <>0) )
"""

        self._cr.execute(sqql)
        query_res = self._cr.fetchone()
        if query_res:
            return query_res[0]
        

