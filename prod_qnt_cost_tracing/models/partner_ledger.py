from odoo import models, fields, tools,api, _
from lxml import etree
from datetime import date

class PartnerLedger(models.Model):
    _name = "trace.partner.ledger"
    _description = "Partner Ledger"
    _auto = False   

    id= fields.Integer(string='Internal Id', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    internal_type=fields.Char(string='Type', readonly=True)
    opening_balance = fields.Float(string='Initial Balance', readonly=True)
    debit = fields.Float(string='Debit', readonly=True)
    credit = fields.Float(string='Credit', readonly=True)
    balance = fields.Float(string='Balance', readonly=True)
    thisyear = fields.Boolean(string='this year', compute='_compute_dummy')
    lastyear = fields.Boolean(string='last year', compute='_compute_dummy')
    


    def _compute_dummy(self):
        for record in self:
            record.lastyear = False
            record.thisyear = False


    def init(self):
        """Initialize SQL view"""
        self._cr.execute("""
CREATE OR REPLACE VIEW %s AS (
select row_number() OVER() AS id,rp.id as partner_id,Q.internal_type,Q.opening_balance,Q.debit,Q.credit,Q.balance from (
select COALESCE(ob.partner_id, pa.partner_id) as id, 
		COALESCE(ob.internal_type, pa.internal_type) as internal_type, 
		COALESCE(ob.opening_balance, 0) as opening_balance,
		COALESCE(pa.period_debit, 0) as debit,
		COALESCE(pa.period_credit, 0) as credit,
		COALESCE(ob.opening_balance, 0) + COALESCE(pa.period_balance, 0) as balance
		from 
(SELECT 
        aml.partner_id,aa.account_type as internal_type,
        SUM(aml.balance) as opening_balance
    FROM 
        invoice_detailed_param p,
        account_move_line aml
        INNER JOIN account_move am ON am.id = aml.move_id
        INNER JOIN account_account aa ON aa.id = aml.account_id
    WHERE 
        am.state = 'posted'
        AND aa.account_type IN ('asset_receivable', 'liability_payable')
        AND aml.date < p.fromdate  
    GROUP BY 
        aml.partner_id,aa.account_type) as ob
		full outer join
(SELECT 
        aml.partner_id,aa.account_type as internal_type,
        SUM(aml.debit) as period_debit,
        SUM(aml.credit) as period_credit,
        SUM(aml.balance) as period_balance
    FROM 
        invoice_detailed_param p,
        account_move_line aml
        INNER JOIN account_move am ON am.id = aml.move_id
        INNER JOIN account_account aa ON aa.id = aml.account_id
    WHERE 
        am.state = 'posted'
        AND aa.account_type IN ('asset_receivable', 'liability_payable')
        AND (p.fromdate is null or aml.date>=p.fromdate)
        AND (p.todate is null or aml.date<p.todate)         
    GROUP BY 
        aml.partner_id,aa.account_type) as pa
		on pa.partner_id=ob.partner_id and pa.internal_type=ob.internal_type
) as Q inner join res_partner rp on rp.id=Q.id
where Q.opening_balance<>0 or Q.debit<>0 or Q.credit<>0 or Q.balance<>0
        )""" % self._table)


    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Override search method to use AND logic between search terms,
        including computed fields like attribute_search.
        """
        new_args = []
        search_terms = []
        fromdate=False
        todate = False
        

        for domain in args:
            if isinstance(domain, (list, tuple)) and len(domain) == 3:
                field, operator, value = domain
                new_args.append(domain)


                if field=='lastyear':
                    fromdate=date.today().replace(year=date.today().year - 1).strftime('%Y-01-01')
                    todate = date.today().strftime('%Y-01-01')
                

                if field=='thisyear':
                    if (fromdate):
                        todate=False
                    else:
                        fromdate = date.today().strftime('%Y-01-01')
            else:
                new_args.append(domain)

        # Combine search terms with AND (&) logic properly
        if search_terms:
            # Start with the first term
            combined_domain = [search_terms[0]]
            # For each next term, prepend an '&' and the new term
            for term in search_terms[1:]:
                combined_domain =combined_domain + [term]
            new_args += combined_domain  # extend, not append


        param=self.env['invoice.detailed.param'].sudo().search([], limit=1)
        param.prepare_for_datequery(fromdate,todate)
        self.env.cr.commit()
        return super(PartnerLedger, self).search(new_args, offset=offset, limit=limit, order=order, count=count)


    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        # 1. Call the parent method first to get the original view architecture
        arch, view = super()._get_view(view_id, view_type, **options)

        if view_type == 'search':
            item=etree.Element('filter', name='this_financial', string='This financial year',domain="[('thisyear', '=', 'True')]",context="{'group_by': False}")
            arch.append(item)
            item=etree.Element('filter', name='last_financial_year', string='Last financial year',domain="[('lastyear', '=', 'True')]",context="{'group_by': False}")
            arch.append(item)
        
        return arch, view


    @api.model    
    def getSummary2(self,domain):
        # if (not domain):
        #     domain=[]
        result = self.env['trace.partner.ledger'].read_group(domain, 
            ['balance:sum'],['internal_type'])
       
        receivable = '0'
        payable= '0'
        if result:
            for rec in result:
                if rec.get('internal_type')=='asset_receivable':
                    receivable=format(int(rec.get('balance', 0) or 0),',')
                if rec.get('internal_type')=='liability_payable':
                    payable=format(int(rec.get('balance', 0) or 0),',')

        return {
                'receivable' : receivable,
                'payable' : payable,
            }

      
