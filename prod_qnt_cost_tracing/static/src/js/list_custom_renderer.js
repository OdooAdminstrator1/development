odoo.define('prod_qnt_cost_tracing.ListCustomRenderer', function (require) {
    "use strict";
    const ListRenderer = require('web.ListRenderer');
    // Use `include` to patch the ListRenderer prototype (safe and common pattern in v15)
    ListRenderer.include({
        /**
         * Patch _renderView to run *after* the standard rendering is complete.
         * We add console.logs so you can see when it's executed.
         */
        _renderView:  function () {

            const result = this._super.apply(this, arguments);
            // result may be a promise - handle both promise and sync
            if (result && result.then) {
                return result.then(() => {
                    try { 
                        this.custom_function();
                    } catch (err) {
                    }
                });
            }
        },
    custom_function: async function()
    {
        var state = this.state;
        var context = state.getContext();
        if (state.model==="stock.product.trace" && context.active_model==="stock.product.trace.wizard" )
        {
            var data=0
            await this._rpc({
                model: 'stock.product.trace',
                method: 'getSummary',
                args: [[],state.domain],           // empty recordset
            }).then(function(runtimeText) {
                data=runtimeText;
                });
           // const value=context.Total;    
            const banner = document.createElement("div");
            banner.className = "my-custom-list-banner";

            const container = document.createElement("div");
            container.className="json-line"
            const div = document.createElement("div");
            div.className = 'json-item';
            div.innerHTML = `<span class='json-key'>Sum of SubTotal Value:</span><span> ${data}</span>`;
            container.appendChild(div);
            if ( this.$el && data) {
                const bannerbar=this.$el.find('.my-custom-list-banner');
                if (bannerbar.length === 0) {
                        banner.appendChild(container);
                        this.$el.prepend(banner);
                }
                else
                {
                    bannerbar[0].innerHTML=container; 
                }  
            }
        }
        var data={};
        if (state.model==="material.cor.analysis")
        {
            await this._rpc({
                model: 'material.cor.analysis',
                method: 'getSummary2',
                args: [[],state.domain],           // empty recordset
            }).then(function(runtimeText) {
                data=runtimeText;
                });  
            const ddic={ 's_revenue' : 'T CI Revenue','s_rest_revenue' : 'T Rest of Revenue','s_sub_tot_revenue' : 'Grand SubT Revenue','s_cost' : 'T CI Cost','s_rest_cost' : 'T Rest of Cost','s_landed_cost' : 'T Landed Cost','s_other_cost' : 'T Update Cost','s_sub_tot_cost' : 'Grand SubT Cost'};
            this.printBanner(data,ddic);
        }
        if (state.model==="invoice.detailed.group")
        {
            await this._rpc({
                model: 'invoice.detailed.group',
                method: 'getSummary2',
                args: [[],state.domain],           // empty recordset
            }).then(function(runtimeText) {
                data=runtimeText;
                });  
            const ddic={ 's_revenue' : 'Total CI Revenue','s_cost' : 'Total CI Cost'};
            this.printBanner(data,ddic);
        }
        if (state.model==="trace.partner.ledger")
        {
            await this._rpc({
                model: 'trace.partner.ledger',
                method: 'getSummary2',
                args: [[],state.domain],           // empty recordset
            }).then(function(runtimeText) {
                data=runtimeText;
                });  
            const ddic={ 'receivable' : 'Total Receivable Balance','payable' : 'Total Payable Balance'};
            this.printBanner(data,ddic);
        }
        if (state.model==="clearance.acc.analysis")
        {
            await this._rpc({
                model: 'clearance.acc.analysis',
                method: 'getSummary2',
                args: [[]],           // empty recordset
            }).then(function(runtimeText) {
                data=runtimeText;
                });  
            const ddic={ 'stockin' : 'Stock In Balance','difference' : 'Total Difference'};
            this.printBanner(data,ddic);
        }
    },

    printBanner: function(data,ddic)
    {
                const banner = document.createElement("div");
                banner.className = "my-custom-list-banner";

                const container = document.createElement("div");
                container.className="json-line"
               
                for (const [key, value] of Object.entries(data)) {
                        const div = document.createElement("div");
                        div.className = 'json-item';
                        div.innerHTML = `<span class='json-key'>${ddic[key]}:</span><span> ${value}</span>`;
                        container.appendChild(div);
                    }   
                if (this.$el && data) {
                    const bannerbar=this.$el.find('.my-custom-list-banner');
                    if (bannerbar.length === 0) {
                            banner.appendChild(container);
                            this.$el.prepend(banner);
                    }
                    else
                    {
                       bannerbar[0].innerHTML=container; 
                    }  
                }
        },

    });

});
