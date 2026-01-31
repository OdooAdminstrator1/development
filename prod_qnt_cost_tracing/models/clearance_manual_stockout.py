from odoo import models, fields, tools , _


class ClearanceManualStockout(models.Model):
    _name = "clearance.stockout.manual"
    _auto = False 
    
    move_id = fields.Many2one('account.move', 'Journal Entry', readonly=True)
    balance = fields.Float('Balance', readonly=True)
    date = fields.Date(string='Date', related='move_id.date',readonly=True,)
    stock_move_type = fields.Selection([
        ('qty_manualy', 'Update Quantity Manually'),
        ('adjustment', 'Inventory Adjustment'),
        ('cost_manually', 'Update Cost Manually'),
    ], string='Move Type',readonly=True)

    def init(self):
        """Initialize SQL view"""
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
select row_number() OVER(order by B.move_id) AS id, B.move_id as move_id,A.stock_move_type as stock_move_type,sum(B.balance) as balance from stock_product_trace A   inner join 
account_move_line B on A.move_id=B.move_id
 where A.stock_move_type in ('cost_manually','qty_manualy','adjustment')
 and B.parent_state='posted'
 and B.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and B.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
group by B.move_id,A.stock_move_type
        )
        """ % self._table)


    def getSummary2(self):
        return {
                'difference' : self.getSum(),
            }
    


        

    def getSum(self):
        sqql="""
select COALESCE(sum(B.balance),0) from stock_product_trace A   inner join 
account_move_line B on A.move_id=B.move_id
 where A.stock_move_type in ('cost_manually','qty_manualy','adjustment')
 and B.parent_state='posted'
 and B.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_out_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and B.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
 """

        self._cr.execute(sqql)
        query_res = self._cr.fetchone()
        if query_res:
            return query_res[0]
        

