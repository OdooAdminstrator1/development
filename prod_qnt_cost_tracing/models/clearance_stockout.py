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
    pricediff = fields.Float('Price Difference', readonly=True)


    def init(self):
        """Initialize SQL view"""
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
select row_number() OVER(order by A.id) AS id, A.id as order_id,A.sumstock,COALESCE( B.sumbill,0) as sumbill,(A.SumStock+COALESCE( B.sumbill,0)) as balance 
, A.sumStockRet+COALESCE(B.sumAccountRet,0) as pricediff 
from (
select po.id,po.name, sum(accl.balance) as SumStock
, sum(case when accl.credit>0 then accl.balance else 0 end )  as sumStockRet
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
select A.id ,sum(accl.balance) as sumbill
, sum(case when accl.debit>0 then accl.balance else 0 end )  as sumAccountRet   from
(select distinct po.id, ac.id as move_id 
from sale_order as po
inner join sale_order_line  as  pol on pol.order_id=po.id
inner join sale_order_line_invoice_rel as rel on  rel.order_line_id = pol.id                  
inner join account_move_line as  accl on accl.id=rel.invoice_line_id
inner join account_move ac on ac.id=accl.move_id
where po.state='sale' and accl.parent_state='posted' and 
ac.move_type in ('out_invoice', 'out_refund')
and ac.invoice_date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date  
) as A
inner join  account_move_line as accl on  accl.move_id=A.move_id
where 
 accl.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
group by A.id
) as B on A.id=B.id
where (B.SumBill is null or ((A.SumStock+ B.SumBill) <>0) )
                         
        )
        """ % self._table)


    def getSummary2(self):
        diff,diffp=self.getSumDifference()
        return {
                'stockin' : self.getSum(),
                'difference' : diff,
                'differencep' : diffp,
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
select sum(A.SumStock+COALESCE( B.sumbill,0)) as balance 
, Sum(A.sumStockRet+COALESCE(B.sumAccountRet,0)) as pricediff 
from (
select po.id,po.name, sum(accl.balance) as SumStock
, sum(case when accl.credit>0 then accl.balance else 0 end )  as sumStockRet
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
select A.id ,sum(accl.balance) as sumbill
, sum(case when accl.debit>0 then accl.balance else 0 end )  as sumAccountRet  from
(select distinct po.id, ac.id as move_id 
from sale_order as po
inner join sale_order_line  as  pol on pol.order_id=po.id
inner join sale_order_line_invoice_rel as rel on  rel.order_line_id = pol.id                  
inner join account_move_line as  accl on accl.id=rel.invoice_line_id
inner join account_move ac on ac.id=accl.move_id
where po.state='sale' and accl.parent_state='posted' and 
ac.move_type in ('out_invoice', 'out_refund')
and ac.invoice_date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date  
) as A
inner join  account_move_line as accl on  accl.move_id=A.move_id
where 
 accl.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
group by A.id
) as B on A.id=B.id
where (B.SumBill is null or ((A.SumStock+ B.SumBill) <>0) )
"""

        self._cr.execute(sqql)
        query_res = self._cr.fetchone()
        if query_res:
            return query_res[0],query_res[1]
        

