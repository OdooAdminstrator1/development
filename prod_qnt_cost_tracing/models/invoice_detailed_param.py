from odoo import models, fields, api, _
from datetime import datetime, timedelta

class InvoiceDetailParam(models.Model):
    _name = "invoice.detailed.param"
    fromdate = fields.Datetime('from Date')
    todate = fields.Datetime('to Date')
    cost_account = fields.Many2many('account.account'
                   ,'cost_param_account_account_rel'
                   ,'param_id', 'account_id',string= 'Cost Account')

    revenue_account = fields.Many2many('account.account'
                   ,'revenue_param_account_account_rel'
                   ,'param_id', 'account_id',string= 'Rev Account')
    


    def prepare_for_query(self,distinct_revenus,distinct_costs):
        """Create default record if none exists"""
        if not self.search_count([]):
            # Set dates (example: current month)
            today = datetime.now()
            return self.create({
                'todate': today,
                'cost_account': [(6, 0, distinct_costs)],
                'revenue_account': [(6, 0, distinct_revenus)],
            })
        else:
            today = datetime.now()
            return self.write({
                'todate': today,
                'cost_account': [(6, 0, distinct_costs)],
                'revenue_account': [(6, 0, distinct_revenus )],
            })
    
    def prepare_for_datequery(self,fromdate,todate):
        """Create default record if none exists"""
        if not self.search_count([]):
            # Set dates (example: current month)
            return self.create({
                'fromdate': fromdate,
                'todate': todate,
            })
        else:
            return self.write({
                'fromdate': fromdate,
                'todate': todate,
            })
    
