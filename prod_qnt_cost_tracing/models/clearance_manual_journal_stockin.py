from odoo import models, fields, tools , _


class ClearanceManualJournalStockin(models.Model):
    _name = "clearance.stockin.manual.journal"
    _auto = False 
    
    move_id = fields.Many2one('account.move', 'Journal Entry', readonly=True)
    balance = fields.Float('Balance', readonly=True)
    date = fields.Date(string='Date', related='move_id.date',readonly=True,)

    def init(self):
        """Initialize SQL view"""
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
select  row_number() OVER(order by A.id) AS id, A.id as move_id ,sum(ml.balance) as balance from account_move as A
inner join
(select distinct move_id from account_move_line where name is null or length(name)<3) as B
on A.id =B.move_id
inner join account_move_line as ml on a.id= ml.move_id
where A.move_type='entry' and A.state='posted' and A.stock_move_id is null
and ml.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and A.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
group by A.id
        )
        """ % self._table)


    def getSummary2(self):
        return {
                'difference' : self.getSum(),
            }
    


        

    def getSum(self):
        sqql="""
select COALESCE(sum(ml.balance),0) from account_move as A
inner join
(select distinct move_id from account_move_line where name is null or length(name)<3) as B
on A.id =B.move_id
inner join account_move_line as ml on a.id= ml.move_id
where A.move_type='entry' and A.state='posted' and A.stock_move_id is null
and ml.account_id=any(
                    string_to_array(
                        replace(replace(
                            (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.clearance_ids'),
                            '[', ''
                        ), ']', ''),
                        ','
                    )::int[]
                )
and A.date >(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.last_closing_year')::date 
"""

        self._cr.execute(sqql)
        query_res = self._cr.fetchone()
        if query_res:
            return query_res[0]
        

