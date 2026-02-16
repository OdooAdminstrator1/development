from odoo import models, fields, tools , _


class ClearanceLandedStockin(models.Model):
    _name = "clearance.stockin.landedcost"
    _auto = False 
    
    landedcost_id = fields.Many2one('stock.landed.cost', 'Landed Cost', readonly=True)
    vendor_bill_id = fields.Many2one('account.move', 'Vendor Bill', readonly=True)
    sumstock = fields.Float('Total Journal entries', readonly=True)
    sumbill = fields.Float('Total Vendor Bill', readonly=True)
    balance = fields.Float('Difference', readonly=True)
    date = fields.Date(string='Date', related='landedcost_id.date',readonly=True,)


    def init(self):
        """Initialize SQL view"""
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
select row_number() OVER(order by id) AS id, id as landedcost_id,vendor_bill_id,sumstock,sumbill,balance from
(
select lc.id,null as vendor_bill_id,sum(mv.balance)  as sumstock,0 as sumbill,sum(mv.balance)  as balance
from stock_landed_cost as lc inner join account_move_line as mv
on lc.account_move_id=mv.move_id
where
  mv.parent_state='posted'
 and mv.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
 and mv.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and lc.vendor_bill_id is null 
group by lc.id
union
Select A.lcid,A.vendor_bill_id,A.sumstock ,B.sumbill,  A.sumstock+B.sumbill as balance
from
(select min(lc.id) as lcid, lc.vendor_bill_id,sum(mv.balance) as sumstock
from stock_landed_cost as lc inner join account_move_line as mv
on lc.account_move_id=mv.move_id
where
  mv.parent_state='posted'
 and mv.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
 and mv.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
group by vendor_bill_id) As A inner join
(select  mv.move_id ,sum(mv.balance) as sumbill
from  account_move_line as mv
where 
  mv.parent_state='posted'
   and  mv.is_landed_costs_line=true 
and mv.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
group by mv.move_id) As B on A.vendor_bill_id=B.move_id 
where A.sumstock+B.sumbill<>0 
union 
Select case when A.lcid=0 then null else 0 end as lcid,A.move_id as vendor_bill_id, 0 as sumstock ,A.sumbill,  A.sumbill as balance
from
(select 0 as lcid, mv.move_id,sum(mv.balance) as sumbill
from  account_move_line as mv inner join account_move as am on am.id =mv.move_id 
  left join stock_landed_cost as lc on am.id= lc.vendor_bill_id
where
 lc.vendor_bill_id is null
 and  mv.parent_state='posted'
 and mv.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
 and mv.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
 and mv.is_landed_costs_line=true 
group by move_id) As A 
                         ) as H
        )
        """ % self._table)


    def getSummary2(self):
        return {
                'difference' : self.getSumDifference(),
            }
    


        

    def getSumDifference(self):
        sqql="""
select COALESCE(sum(balance),0) from (
select COALESCE(sum(mv.balance),0)  as balance
from stock_landed_cost as lc inner join account_move_line as mv
on lc.account_move_id=mv.move_id
where
  mv.parent_state='posted'
 and mv.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
 and mv.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and lc.vendor_bill_id is null 
group by lc.id
union
Select COALESCE(A.sumstock+B.sumbill,0) as balance
from
(select min(lc.id) as lcid, lc.vendor_bill_id,sum(mv.balance) as sumstock
from stock_landed_cost as lc inner join account_move_line as mv
on lc.account_move_id=mv.move_id
where
  mv.parent_state='posted'
 and mv.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
 and mv.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
group by vendor_bill_id) As A inner join
(select  mv.move_id ,sum(mv.balance) as sumbill
from  account_move_line as mv
where 
  mv.parent_state='posted'
   and  mv.is_landed_costs_line=true 
and mv.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
group by mv.move_id) As B on A.vendor_bill_id=B.move_id 
where A.sumstock+B.sumbill<>0
union
select sum(mv.balance) as balance
from  account_move_line as mv inner join account_move as am on am.id =mv.move_id 
 
 left join stock_landed_cost as lc on am.id= lc.vendor_bill_id
where
 lc.vendor_bill_id is null
 and  mv.parent_state='posted'
 and mv.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
 and mv.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
 and mv.is_landed_costs_line=true 
) as A
 """

        self._cr.execute(sqql)
        query_res = self._cr.fetchone()
        if query_res:
            return query_res[0]
        

