from odoo import models, fields, tools , _


class ClearanceLandedStockin(models.Model):
    _name = "clearance.stockin.landedcost"
    _auto = False 
    
    landedcost_id = fields.Many2one('stock.landed.cost', 'Landed Cost', readonly=True)
    sumstock = fields.Float('Total Journal entries', readonly=True)
    sumbill = fields.Float('Total Vendor Bill', readonly=True)
    balance = fields.Float('Difference', readonly=True)
    date = fields.Date(string='Date', related='landedcost_id.date',readonly=True,)


    def init(self):
        """Initialize SQL view"""
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
select row_number() OVER(order by A.id) AS id, A.id as landedcost_id,
COALESCE(B.sumstock,A.total) as sumstock,COALESCE(B.sumbill,0) as sumbill,COALESCE(B.balance,A.total) as balance
from
(select lc.id,lc.vendor_bill_id,
 (select sum(balance) from account_move_line where move_id=lc.account_move_id
 and account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
 ) as total
 from  stock_landed_cost lc 
	inner join account_move_line aml on lc.account_move_id=aml.move_id
	where lc.state='done' and aml.parent_state='posted'  
	and aml.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
	and aml.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
group by lc.id,lc.vendor_bill_id
) as A left join 
(
select A.vendor_bill_id,A.sumstock,B.sumbill ,(A.sumstock+B.sumbill)  as balance 
from
(SELECT lc.vendor_bill_id,sum(aml.balance) as sumstock
	FROM stock_landed_cost lc
	inner join account_move_line aml on lc.account_move_id=aml.move_id
	where lc.state='done' and aml.parent_state='posted'  
	and aml.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
	and aml.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
	group by lc.vendor_bill_id
) as A inner join 
(SELECT lc.vendor_bill_id ,sum(aml.balance) as sumbill
	FROM stock_landed_cost lc
	inner join account_move_line aml on lc.vendor_bill_id=aml.move_id
	where lc.state='done' and aml.parent_state='posted'  and aml.is_landed_costs_line=true 
	and aml.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
	group by lc.vendor_bill_id
 ) as B on (A.vendor_bill_id=B.vendor_bill_id)
 ) as B
 on (A.vendor_bill_id=B.vendor_bill_id ) 
 where B.balance is null or B.balance<>0  
        )
        """ % self._table)


    def getSummary2(self):
        return {
                'difference' : self.getSumDifference(),
            }
    


        

    def getSumDifference(self):
        sqql="""
select sum(COALESCE(B.balance,A.total)) 
from
(select lc.id,lc.vendor_bill_id,
 (select sum(balance) from account_move_line where move_id=lc.account_move_id
 and account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
 ) as total
 from  stock_landed_cost lc 
	inner join account_move_line aml on lc.account_move_id=aml.move_id
	where lc.state='done' and aml.parent_state='posted'  
	and aml.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
	and aml.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
	group by lc.id,lc.vendor_bill_id
) as A left join 
(
select A.vendor_bill_id,A.sumstock,B.sumbill ,(A.sumstock+B.sumbill)  as balance 
from
(SELECT lc.vendor_bill_id,sum(aml.balance) as sumstock
	FROM stock_landed_cost lc
	inner join account_move_line aml on lc.account_move_id=aml.move_id
	where lc.state='done' and aml.parent_state='posted'  
	and aml.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
	and aml.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
	group by lc.vendor_bill_id
) as A inner join 
(SELECT lc.vendor_bill_id ,sum(aml.balance) as sumbill
	FROM stock_landed_cost lc
	inner join account_move_line aml on lc.vendor_bill_id=aml.move_id
	where lc.state='done' and aml.parent_state='posted'  and aml.is_landed_costs_line=true 
	and aml.account_id =any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
	group by lc.vendor_bill_id
 ) as B on (A.vendor_bill_id=B.vendor_bill_id)
 ) as B
 on (A.vendor_bill_id=B.vendor_bill_id ) 
 where B.balance is null or B.balance<>0
 """

        self._cr.execute(sqql)
        query_res = self._cr.fetchone()
        if query_res:
            return query_res[0]
        
