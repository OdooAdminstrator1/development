from odoo import models, fields, tools,api, _
from lxml import etree
from datetime import date



class MaterialCorAnalysis(models.Model):
    _name = "material.cor.analysis"
    _description = "Material CoR Analysis"
    _auto = False   # <-- Important: no automatic table creation

    id= fields.Integer(string='Product Id', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    product_category_id = fields.Many2one(
        'product.category', 
        string='Product Category',
        related='product_id.categ_id',
        readonly=True,
        store=False  # Since _auto=False, store should typically be False
    )
    quantity = fields.Float(string='Quantity', readonly=True)
    revenue = fields.Float(string='CI Revenue', digits='Product Price', readonly=True)
    rest_revenue = fields.Float(string='Rest of Revenue', digits='Product Price', readonly=True)
    sub_tot_revenue = fields.Float(string='SubT Revenue',compute='_sub_tot_revenue', digits='Product Price', readonly=True)
    # discount = fields.Float(string='Discount', digits='Product Price', readonly=True)
    cost = fields.Float(string='CI Cost', digits='Product Price', readonly=True)
    rest_cost = fields.Float(string='Rest of Cost', digits='Product Price', readonly=True)
    sub_tot_cost = fields.Float(string='SubT Cost',compute='_sub_tot_cost', digits='Product Price', readonly=True)
    
    # tax = fields.Float(string='Tax', digits='Product Price', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True)
    landed_cost = fields.Float(string='Landed Cost', digits='Product Price', readonly=True)
    other_cost = fields.Float(string='Update Cost', digits='Product Price', readonly=True)
    attribute_search = fields.Char(string='Attribute Search', compute='_compute_dummy', search='_search_attribute')
    thisyear = fields.Boolean(string='this year', compute='_compute_dummy')
    lastyear = fields.Boolean(string='last year', compute='_compute_dummy')

    @api.depends('revenue', 'rest_revenue')
    def _sub_tot_revenue(self):
        for record in self:
            record.sub_tot_revenue = record.revenue+record.rest_revenue

    @api.depends('cost', 'rest_cost','landed_cost','other_cost')
    def _sub_tot_cost(self):
        for record in self:
            record.sub_tot_cost = record.cost+record.rest_cost+record.landed_cost+record.other_cost




    def _compute_dummy(self):
        for record in self:
            record.attribute_search = False
            record.lastyear = False
            record.thisyear = False



    def init(self):
        """Initialize SQL view"""
       # cost_account_ids = self.env['ir.config_parameter'].sudo().get_param('cost_account_ids.cost_account_ids')
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
select main.*,product.expense_account_id,product.income_account_id
,RV.tot * main.revenue/ COALESCE(NULLIF(sum(main.revenue) OVER (PARTITION BY product.income_account_id), 0), 1)  as rest_revenue
,RC.tot,RC.tot*(main.cost)/COALESCE(NULLIF(sum(main.cost) over (PARTITION BY product.expense_account_id), 0), 1)   as rest_cost
from
(
    select  COALESCE(g1.id, g2.product_id+1) as id,COALESCE(g1.product_id, g2.product_id) as product_id,COALESCE(g1.currency_id, g2.currency_id) as currency_id,g1.quantity,
	COALESCE(g1.cost,0) as cost,COALESCE(g1.revenue,0) as revenue,COALESCE(g2.landed_cost,0) as landed_cost,COALESCE(g2.other_cost,0) as other_cost
	from 
 	(  
        SELECT  COALESCE(sum(D.amount_currency),0) as tot
        from invoice_detailed_param p,account_move as A inner join account_move_line as D on A.id =D.Move_id
            where A.move_type not in ('out_invoice','out_refund')  and state='posted' 
            and  D.account_id=any (
                            string_to_array(
                                replace(replace(
                                    (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.revenue_ids'),
                                    '[', ''
                                ), ']', ''),
                                ','
                            )::int[]
                        )
	            and (p.fromdate is null or A.date>=p.fromdate)
                and (p.todate is null or A.date<p.todate)
	 
	) as RV,
	(                      
		select (M.product_id+1) as id, M.product_id,M.currency_id,
		sum(M.sign*M.quantity) as quantity,                        
		sum(M.sign*(M.price_total-M.price_subtotal)) as Tax,
		COALESCE(sum(M.sign*(M.quantity*M.cost_unit)),0) as cost,
		COALESCE(sum(M.sign*(M.quantity*M.price_unit-M.discount)),0) as revenue,
		sum(M.sign*(M.discount))  as discount              
		from
		(
				SELECT COALESCE(D.product_id, 0) as product_id, D.price_total,D.price_subtotal,D.quantity,D.price_unit,pc.price_unit as cost_unit, 
			  	A.currency_id, D.quantity*D.price_unit*D.discount/100 as discount,(CASE WHEN A.move_type='out_refund' THEN 1 ELSE -1 END) as sign
				FROM invoice_detailed_param p, account_move as A inner join account_move_line as D
				on A.id =D.Move_id
			  	FULL OUTER JOIN 
				(
					select COALESCE(product_id, 0) as product_id ,move_id,account_id,max(price_unit) as price_unit  from account_move_line where 
					parent_state='posted' and
							account_id =any(
								string_to_array(
									replace(replace(
										(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.cost_account_ids'),
										'[', ''
									), ']', ''),
									','
								)::int[]
							)
                	and journal_id=any (
										string_to_array(
											replace(replace(
												(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.cost_journal_ids'),
												'[', ''
											), ']', ''),
											','
										)::int[]
									)
            --    and account_id in (select account_id from cost_param_account_account_rel)
                group by product_id,move_id,account_id     
                         
				)    pc on COALESCE(D.product_id, 0) = pc.product_id and D.move_id=pc.move_id
			where A.move_type in ('out_invoice','out_refund')  and state='posted' and d.tax_line_id is null 
			   and  D.account_id=any (
							string_to_array(
								replace(replace(
									(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.revenue_ids'),
									'[', ''
								), ']', ''),
								','
							)::int[]
						)
			
		--	and  D.account_id in (select account_id from revenue_param_account_account_rel)
			and (p.fromdate is null or A.date>=p.fromdate)
			and (p.todate is null or A.date<p.todate)                     
		) as M
	group by  M.product_id,M.currency_id
	order by M.product_id
	) as g1 full outer join (

	select D.product_id,COALESCE(sum(CASE WHEN c.id is null THEN 0 ELSE D.amount_currency END),0) as landed_cost,M.currency_id
	,COALESCE(sum(CASE WHEN c.id is null THEN D.amount_currency ELSE 0  END),0) as other_cost	
					from invoice_detailed_param p, account_move_line D  inner join account_move M
					on M.id=D.move_id 
					 left join stock_landed_cost C on M.id =C.account_move_id
					 where M.state='posted' and
									 account_id =any(
						string_to_array(
							replace(replace(
								(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.cost_account_ids'),
								'[', ''
							), ']', ''),
							','
						)::int[]
					) and
					 D.journal_id=any (
						string_to_array(
							replace(replace(
								(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.inventory_val_journal_ids'),
								'[', ''
							), ']', ''),
							','
						)::int[]
					)
					and (p.fromdate is null or M.date>=p.fromdate)
					and (p.todate is null or M.date<p.todate)            
					group by product_id ,M.currency_id 
	) as g2 on g1.product_id=g2.product_id
) as main
left join (
SELECT
    p.id as product_id,COALESCE((select replace(value_reference,'account.account,','') from ir_property where value_reference like 'account.account,%%' and name='property_account_income_categ_id' and
				 res_id='product.category,' ||pt.categ_id),
						 (select replace(value_reference,'account.account,','') from ir_property where value_reference like 'account.account,%%' and name='property_account_income_categ_id' and
				 res_id is null) )::integer as income_account_id,
				 
    COALESCE((select replace(value_reference,'account.account,','') from ir_property where value_reference like 'account.account,%%' and name='property_account_expense_categ_id' and
				 res_id='product.category,' ||pt.categ_id),
						 (select replace(value_reference,'account.account,','') from ir_property where value_reference like 'account.account,%%' and name='property_account_expense_categ_id' and
				 res_id is null) )::integer as expense_account_id
FROM product_product p
JOIN product_template pt
    ON p.product_tmpl_id = pt.id
) as product on main.product_id=product.product_id
left join
(
			select acc.id as account_id ,sum(COALESCE(ml.amount_currency,0)) as tot from 
			( select id from account_account  where id =any(string_to_array( replace(replace(
										(SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.cost_account_ids'),
										'[', ''), ']', ''),',')::int[]
							)
			 ) as acc left join
			 (
				 select ml.account_id, ml.amount_currency  from account_move_line as ml,invoice_detailed_param p
				 where 
				ml.parent_state='posted' 
				and not ml.journal_id=any (
			string_to_array(replace(replace(
			(SELECT  STRING_AGG(cast(value as varchar),',') FROM ir_config_parameter 
			WHERE key = 'prod_qnt_cost_tracing.cost_journal_ids' or  key = 'prod_qnt_cost_tracing.inventory_val_journal_ids'),'[',''),']',''),',')::int[]
							)
							 and (p.fromdate is null or ml.date>=p.fromdate)
							and (p.todate is null or ml.date<p.todate)   
			 ) as ml on acc.id = ml.account_id
			 group by acc.id
) as RC
on  product.expense_account_id=rc.account_id
left join
 (
select acc.id as account_id ,sum(COALESCE(ml.amount_currency,0)) as tot from 
( select id from account_account  where id =any(string_to_array( replace(replace(
  (SELECT value FROM ir_config_parameter WHERE key = 'prod_qnt_cost_tracing.revenue_ids'),
       '[', ''), ']', ''),',')::int[]
      )
			 ) as acc inner join 
 (
 SELECT D.account_id,  D.amount_currency 
        from invoice_detailed_param p,account_move as A inner join account_move_line as D on A.id =D.Move_id
            where A.move_type not in ('out_invoice','out_refund')  and state='posted'  
 	         and (p.fromdate is null or A.date>=p.fromdate)
             and (p.todate is null or A.date<p.todate)
	 )  as ml on acc.id = ml.account_id
	 group by acc.id
) as RV 
on  product.income_account_id=RV.account_id
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
                if field =='attribute_search':
                    attrib=self.env['product.attribute.value'].search([('name', 'ilike', value)]).ids
                    search_terms.append(('product_id.product_template_attribute_value_ids.product_attribute_value_id', 'in', attrib))
                else:
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
        return super(MaterialCorAnalysis, self).search(new_args, offset=offset, limit=limit, order=order, count=count)


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(MaterialCorAnalysis, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
        # param = self.env['invoice.detailed.param'].sudo().search([], limit=1)
        # param._create_default_record()
        if view_type == 'search':
            print(res['arch'])
            arch = etree.fromstring(res['arch'])
            item=etree.Element('filter', name='this_financial', string='This financial year',domain="[('thisyear', '=', 'True')]",context="{'group_by': False}")
            arch.append(item)
            item=etree.Element('filter', name='last_financial_year', string='Last financial year',domain="[('lastyear', '=', 'True')]",context="{'group_by': False}")
            arch.append(item)
            res['arch'] = etree.tostring(arch, encoding='unicode')
        return res



    def action_open_this(self):
        summary=self.getSummary()

        txt =f"T CI Revenue: {summary['s_revenue']} --- T Rest of Revenue: {summary['s_rest_revenue']} --- Grand SubT Revenue: {summary['s_sub_tot_revenue']} --- T Cost: {summary['s_cost']} --- T Rest of Cost: {summary['s_rest_cost']} --- T Landed Cost: {summary['s_landed_cost']} --- T Update Cost: {summary['s_other_cost']} --- Grand SubT Cost: {summary['s_sub_tot_cost']}"
        return {
            'type': 'ir.actions.act_window',
            'name': 'Material CoR Analysis',
            'res_model': 'material.cor.analysis',
            'view_mode': 'tree',
            'context': dict(self.env.context, my_runtime_text=summary),
        }
    
    def getSummary(self):
        SQL= """
select COALESCE(sum(revenue),0) as s_revenue,
COALESCE(sum(rest_revenue),0) as s_rest_revenue,
COALESCE(sum(revenue),0)+COALESCE(sum(rest_revenue),0) as s_sub_tot_revenue,
COALESCE(sum(cost),0) as s_cost,
COALESCE(sum(rest_cost),0) as s_rest_cost,
COALESCE(sum(cost),0)+COALESCE(sum(rest_cost),0)+COALESCE(sum(landed_cost),0)+COALESCE(sum(other_cost),0) as s_sub_tot_cost,
COALESCE(sum(landed_cost),0) as s_landed_cost,
COALESCE(sum(other_cost),0) as s_other_cost
from %s
"""% self._table
        self._cr.execute(SQL)
        query_res = self._cr.fetchone()
        if query_res:
            return {
                's_revenue' :format( int(query_res[0]),','),
                's_rest_revenue' : format(  int(query_res[1]),','),
                's_sub_tot_revenue' : format(  int(query_res[2]),','),
                's_cost' :  format( int(query_res[3]),','),
                's_rest_cost' : format(  int(query_res[4]),','),
                's_sub_tot_cost' : format(  int(query_res[5]),','),
                's_landed_cost' : format(  int(query_res[6]),','),
                's_other_cost' :  format( int(query_res[7]),','),
            }
        else:
            return {
                's_revenue' : 0,
                's_rest_revenue' : 0,
                's_sub_tot_revenue' : 0,
                's_cost' : 0,
                's_rest_cost' : 0,
                's_sub_tot_cost' : 0,
                's_landed_cost' : 0,
                's_other_cost' : 0,
            }
        
    def getSummaryLine(self):
        SQL= """
select COALESCE(sum(revenue),0) as s_revenue,
COALESCE(sum(rest_revenue),0) as s_rest_revenue,
COALESCE(sum(revenue),0)+COALESCE(sum(rest_revenue),0) as s_sub_tot_revenue,
COALESCE(sum(cost),0) as s_cost,
COALESCE(sum(rest_cost),0) as s_rest_cost,
COALESCE(sum(cost),0)+COALESCE(sum(rest_cost),0)+COALESCE(sum(landed_cost),0)+COALESCE(sum(other_cost),0) as s_sub_tot_cost,
COALESCE(sum(landed_cost),0) as s_landed_cost,
COALESCE(sum(other_cost),0) as s_other_cost
from %s
"""% self._table
        self._cr.execute(SQL)
        query_res = self._cr.fetchone()
        summary = {
                's_revenue' : 0,
                's_rest_revenue' : 0,
                's_sub_tot_revenue' : 0,
                's_cost' : 0,
                's_rest_cost' : 0,
                's_sub_tot_cost' : 0,
                's_landed_cost' : 0,
                's_other_cost' : 0,
            }
        if query_res:
            summary= {
                's_revenue' : query_res[0],
                's_rest_revenue' : query_res[1],
                's_sub_tot_revenue' : query_res[2],
                's_cost' : query_res[3],
                's_rest_cost' : query_res[4],
                's_sub_tot_cost' : query_res[5],
                's_landed_cost' : query_res[6],
                's_other_cost' : query_res[7],
            }
        return f"T CI Revenue: {summary['s_revenue']} --- T Rest of Revenue: {summary['s_rest_revenue']} --- Grand SubT Revenue: {summary['s_sub_tot_revenue']} --- T Cost: {summary['s_cost']} --- T Rest of Cost: {summary['s_rest_cost']} --- T Landed Cost: {summary['s_landed_cost']} --- T Update Cost: {summary['s_other_cost']} --- Grand SubT Cost: {summary['s_sub_tot_cost']}"


        
    def getSummary2(self,domain):
        if (not domain):
            domain=[]
        result = self.env['material.cor.analysis'].read_group(domain, 
            ['revenue:sum', 'rest_revenue:sum', 'cost:sum', 'rest_cost:sum', 'landed_cost:sum', 'other_cost:sum'],[])
       
        s_revenue = '0'
        s_rest_revenue= '0'
        s_cost= '0'
        s_rest_cost= '0'
        s_landed_cost = '0'
        s_other_cost = '0'
        s_sub_tot_revenue='0'
        s_sub_tot_cost='0'
        if result:
            totals = result[0]
            s_revenue = format(int(totals.get('revenue', 0) or 0),',')
            s_rest_revenue= format(int(totals.get('rest_revenue', 0) or 0),',')
            s_cost= format(int(totals.get('cost', 0) or 0),',')
            s_rest_cost= format(int(totals.get('rest_cost', 0) or 0),',')
            s_landed_cost = format(int(totals.get('landed_cost', 0) or 0),',')
            s_other_cost = format(int( totals.get('other_cost', 0) or 0),',')
            s_sub_tot_revenue=format(int(totals.get('revenue', 0) or 0)+int(totals.get('rest_revenue', 0) or 0),',')
            s_sub_tot_cost=format(int(totals.get('cost', 0) or 0)+int(totals.get('rest_cost', 0) or 0)+int(totals.get('landed_cost', 0) or 0)+int(totals.get('other_cost', 0) or 0),',')
        return {
                's_revenue' : s_revenue,
                's_rest_revenue' : s_rest_revenue,
                's_sub_tot_revenue' : s_sub_tot_revenue,
                's_cost' : s_cost,
                's_rest_cost' : s_rest_cost,
                's_landed_cost' : s_landed_cost,
                's_other_cost' : s_other_cost,
                's_sub_tot_cost' : s_sub_tot_cost,
            }

                
