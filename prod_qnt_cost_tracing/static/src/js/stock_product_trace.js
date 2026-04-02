/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, onMounted, onWillUpdateProps } from "@odoo/owl";

export class SummaryBannerRenderer extends ListRenderer {
    setup() {
        super.setup();
        this.rpc = useService("rpc");
        this.rootRef = useRef("root");

        onMounted(() => {
            this.custom_function();
        });

        // Trigger when the view updates (e.g., filtering or searching)
        onWillUpdateProps(() => {
            this.custom_function();
        });
    }

    async custom_function() {
        const { model, context } = this.props.list;
        const domain = this.props.list.domain;
        const modelName = this.props.list.resModel;
         const resModel = modelName;

        let data = null;
        let ddic = null;





        // Logic for various analysis models
        const config = {
            "stock.product.trace": {
                method: 'getSummary',
                contextRequirement: 'stock.product.trace.wizard',
                dict: { 'default': 'Sum of SubTotal Value' }
            },
            "material.cor.analysis": {
                method: 'getSummary2',
                dict: { 's_revenue': 'T CI Revenue', 's_rest_revenue': 'T Rest of Revenue', 's_sub_tot_revenue': 'Grand SubT Revenue', 's_cost': 'T CI Cost', 's_rest_cost': 'T Rest of Cost', 's_landed_cost': 'T Landed Cost', 's_other_cost': 'T Update Cost', 's_sub_tot_cost': 'Grand SubT Cost' }
            },
            "invoice.detailed.group": {
                method: 'getSummary2',
                dict: { 's_revenue': 'Total CI Revenue', 's_cost': 'Total CI Cost' }
            },

        };

        if (config[modelName]) {

            const modelName = this.props.list.resModel;
            const modelConfig = config[modelName]; // Get the specific config for this model

            if (modelConfig && config[modelName].contextRequirement)
            {
                const targetModel = modelConfig.model || modelName;
                if (this.props.list.context.active_model !== config[modelName].contextRequirement) {
                    return;
                }
            }


            if (modelConfig) {
                const targetModel = modelConfig.model || modelName;
                const methodName = modelConfig.method;
                
                // Use the domain from props, or empty list if none
                const domain = this.props.list.domain || [];

                try {
                    // Use the service directly and pass params as an object
                    const data = await this.rpc("/web/dataset/call_kw", {
                        model: targetModel,
                        method: methodName,
                        args: [domain],
                        kwargs: {},
                    });

                    if (data) {
                        this.printBanner(data, modelConfig.dict);
                    }
                } catch (error) {
                    console.error("RPC Error:", error);
                }
            }
            ddic = config[modelName].dict;
        }

        if (data && ddic) {
            this.printBanner(data, ddic);
        }
    }

    printBanner(data, ddic) {
        // Remove existing banner if it exists
        const existingBanner = document.querySelector('.my-custom-list-banner');
        if (existingBanner) {
            existingBanner.remove();
        }

        const banner = document.createElement("div");
        banner.className = "my-custom-list-banner";
        const container = document.createElement("div");
        container.className = "json-line";

        // Handle both single value (data) and object (data)
        if (typeof data !== 'object') {
            const div = document.createElement("div");
            div.className = 'json-item';
            div.innerHTML = `<span class='json-key'>Sum of SubTotal Value:</span><span> ${data}</span>`;
            container.appendChild(div);
        } else {
            for (const [key, value] of Object.entries(data)) {
                if (ddic[key]) {
                    const div = document.createElement("div");
                    div.className = 'json-item';
                    div.innerHTML = `<span class='json-key'>${ddic[key]}:</span><span> ${value}</span>`;
                    container.appendChild(div);
                }
            }
        }

        banner.appendChild(container);
        const target = this.rootRef.el;
        
        // In Odoo 16 OWL, this.el refers to the component's root element
        if (target) {
            target.prepend(banner);
        } else {
            // Fallback: If for some reason the ref isn't ready, 
            // find the closest container in the DOM
            const listTable = document.querySelector('.o_list_renderer');
            if (listTable) {
                listTable.prepend(banner);
            }
        }
    }
}

export class StockTraceListController extends ListController {
    async onInventoryAtDate() {
        // This replaces the type="action" logic from Odoo 15
        this.actionService.doAction("prod_qnt_cost_tracing.action_stock_product_trace_wizard_form", {
            additionalContext: {
                active_model: 'stock.product.trace',
            },
        });
    }
}




registry.category("views").add("stock_product_trace_list", {
    ...listView,
    Controller: StockTraceListController,
    Renderer: SummaryBannerRenderer,
    buttonTemplate: "prod_qnt_cost_tracing.ListView.Buttons",
});
