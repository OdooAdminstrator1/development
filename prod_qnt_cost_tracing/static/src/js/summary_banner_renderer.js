/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, useRef } from "@odoo/owl";

patch(ListRenderer.prototype,  {
    setup() {
        super.setup();
        this.rpc = useService("rpc");
        this.rootRef = useRef("root");

        onMounted(() => {
            this.custom_function();
        });

        // onPatched triggers after the component updates in the DOM
        // (e.g., after a search or filter refreshes the list)
        onPatched(() => {
            this.custom_function();
        });
    },

    async custom_function() {
        // Accessing the current props of the list
        const list = this.props.list;
        if (!list) return;

        const modelName = list.resModel;
        const domain = list.domain || []; // This now reflects the UI filters

        const config = {
            "material.cor.analysis": {
                method: 'getSummary2',
                dict: { 's_revenue': 'T CI Revenue', 's_rest_revenue': 'T Rest of Revenue', 's_sub_tot_revenue': 'Grand SubT Revenue', 's_cost': 'T CI Cost', 's_rest_cost': 'T Rest of Cost', 's_landed_cost': 'T Landed Cost', 's_other_cost': 'T Update Cost', 's_sub_tot_cost': 'Grand SubT Cost' }
            },
            "invoice.detailed.group": {
                method: 'getSummary',
                dict: { 's_revenue': 'Total CI Revenue', 's_cost': 'Total CI Cost' }
            },
            "trace.partner.ledger": {
                method: 'getSummary2',
                dict: { 'receivable': 'Total Receivable Balance', 'payable': 'Total Payable Balance' }
            },
            "clearance.acc.analysis": {
                method: 'getSummary2',
                dict: { 'stockin': 'Stock In Balance', 'difference': 'Total Difference', 'differencep': 'Total Price Difference' }
            },
            "clearance.stockout.sorder": {
                method: 'getSummary2',
                dict: { 'stockin': 'Stock Out Balance', 'difference': 'Total Difference', 'differencep': 'Total Price Difference' }
            },
            "clearance.stockin.landedcost": {
                method: 'getSummary2',
                dict: { 'difference': 'Total Difference' }
            },
            "clearance.stockin.manual": {
                method: 'getSummary2',
                dict: { 'difference': 'Total Balance' }
            },
            "clearance.stockout.manual": {
                method: 'getSummary2',
                dict: { 'difference': 'Total Balance' }
            },
            "clearance.stockin.manual.journal": {
                model: 'clearance.stockin.manual',
                method: 'getSummary2',
                dict: { 'difference': 'Total Balance' }
            }
        };

        const modelConfig = config[modelName];
        if (modelConfig) {
            const targetModel = modelConfig.model || modelName;
            
            try {
                const data = await this.rpc("/web/dataset/call_kw", {
                    model: targetModel,
                    method: modelConfig.method,
                    args: [domain],
                    kwargs: { context: list.context },
                });

                if (data) {
                    this.wi(data, modelConfig.dict);
                }
            } catch (error) {
                console.error("RPC Error:", error);
            }
        }
    },

    wi(data, ddic) {
        // Find existing banner within this specific component instance
        const root = this.rootRef.el;
        if (!root) return;

        const existingBanner = root.querySelector('.my-custom-list-banner');
        if (existingBanner) {
            existingBanner.remove();
        }

        const banner = document.createElement("div");
        banner.className = "my-custom-list-banner";
        const container = document.createElement("div");
        container.className = "json-line";

        if (typeof data !== 'object' || data === null) {
            const div = document.createElement("div");
            div.className = 'json-item';
            div.innerHTML = `<span class='json-key'>Sum:</span><span> ${data}</span>`;
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
        root.prepend(banner);
    }
});
