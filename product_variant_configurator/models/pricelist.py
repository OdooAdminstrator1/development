from odoo import models

class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def _compute_price_rule(self, *args, **kwargs):
        """
        Universal signature to handle Odoo 16 core AND custom 
        module signatures (like product_variant_configurator).
        """
        # 1. Safely extract products_qty_partner for your template logic
        # It's usually the first positional argument (args[0]) 
        # or passed as a keyword.
        products_qty_partner = kwargs.get('products_qty_partner')
        if not products_qty_partner and args:
            products_qty_partner = args[0]

        # 2. Extract uom_id for your template logic
        uom_id = kwargs.get('uom_id')
        if not uom_id and len(args) > 2:
            uom_id = args[2] # In Odoo standard: (products, date, uom_id)

        # 3. Perform your custom Product Template logic
        if products_qty_partner and isinstance(products_qty_partner, list) and products_qty_partner[0][0]._name == "product.template":
            pricelist_obj = self
            
            # Context handling for UoM
            if not uom_id and pricelist_obj.env.context.get("uom"):
                uom_id = pricelist_obj.env.context.get("uom")
                pricelist_obj = pricelist_obj.with_context(uom=None) # Clean context

            if uom_id:
                tmpl_ids = [item[0].id for item in products_qty_partner]
                tmpls = self.env["product.template"].with_context(uom=uom_id).browse(tmpl_ids)
                # Rebuild the list with the context-aware templates
                products_qty_partner = [
                    (tmpls[index], data_struct[1], data_struct[2])
                    for index, data_struct in enumerate(products_qty_partner)
                ]
                
                # Update the arguments for the super call
                if kwargs.get('products_qty_partner'):
                    kwargs['products_qty_partner'] = products_qty_partner
                elif args:
                    # Replace the first argument in the list
                    args = list(args)
                    args[0] = products_qty_partner
            
            # Call super using the context-isolated pricelist object
            return super(ProductPricelist, pricelist_obj)._compute_price_rule(*args, **kwargs)

        # 4. Standard super call: Pass everything exactly as it came in
        return super(ProductPricelist, self)._compute_price_rule(*args, **kwargs)
    

    # UPDATED: Odoo 16 renamed price_rule_get_multi to _compute_price_rule
    def template_price_rule_get(self, prod_id, qty, partner=None):
        product = self.env["product.template"].browse([prod_id])
        return self._compute_price_rule(
            products_qty_partner=[(product, qty, partner)]
        )[prod_id]

    def template_price_get(self, prod_id, qty, partner=None):
        res = self.template_price_rule_get(prod_id, qty, partner=partner)
        return {key: price[0] for key, price in res.items()}
