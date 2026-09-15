/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useState } from "@odoo/owl";


export class ProductFilterController extends ListController {

    static template = "product_power_current.ProductFilterListView";

    setup() {
        super.setup();

        this.orm = useService("orm");

        this.filterValues = useState({
            dimming: [],
        });


        this.filterRanges = useState({
            min_current: 0,
            max_current: 0,
            min_voltage: 0,
            max_voltage: 0,
        });

        this.filterState = useState({
            dimming: "",
            application: "all",
            min_current: 0,
            max_current: 0,
            min_voltage: 0,
            max_voltage: 0,
        });

        this.dimmingFilterGroupId = null;
        this.applicationFilterGroupId = null;
        this.minCurrentFilterGroupId = null;
        this.maxCurrentFilterGroupId = null;
        this.minVoltageFilterGroupId = null;
        this.maxVoltageFilterGroupId = null;

        onWillStart(async () => {
            await this.loadFilterValues();
            await this.loadFilterRanges();
        });
    }


    async loadFilterValues() {
        this.filterValues.dimming = await this.orm.call(
            "product.product",
            "get_filter_values",
            ["dimming"]
        );
    }


    async loadFilterRanges() {
        const result = await this.orm.call(
            "product.product",
            "get_filter_range_maxes",
            []
        );

        this.filterRanges.min_current =
            result.min_current || 0;

        this.filterRanges.max_current =
            result.max_current || 0;


        this.filterRanges.min_voltage =
            result.min_voltage || 0;
    
        this.filterRanges.max_voltage =
            result.max_voltage || 0;

    }


    async onDimmingChange(ev) {
        const value = ev.target.value;

        this.filterState.dimming = value;

        const searchModel = this.env.searchModel;

        if (this.dimmingFilterGroupId) {
            searchModel.deactivateGroup(
                this.dimmingFilterGroupId
            );

            this.dimmingFilterGroupId = null;
        }

        if (!value) {
            return;
        }

        this.dimmingFilterGroupId = searchModel.nextGroupId;

        searchModel.createNewFilters([
            {
                type: "filter",

                description: `Dimming: ${value}`,

                domain: [
                    ["dimming", "=", value]
                ],

                invisible: "True",
            }
        ]);
    }


    onApplicationChange(ev) {
        const value = ev.target.value;

        this.filterState.application = value;

        const searchModel = this.env.searchModel;

        if (this.applicationFilterGroupId) {
            searchModel.deactivateGroup(
                this.applicationFilterGroupId
            );

            this.applicationFilterGroupId = null;
        }

        if (value === "all") {
            return;
        }

        let domain;

        if (value === "indoor") {

            domain = [
                ["protection_numeric", "!=", false],
                ["protection_numeric", "<=", 54],
            ];

        } else if (value === "outdoor") {

            domain = [
                ["protection_numeric", "!=", false],
                ["protection_numeric", ">", 54],
            ];

        } else {
            return;
        }

        this.applicationFilterGroupId =
            searchModel.nextGroupId;

        searchModel.createNewFilters([
            {
                type: "filter",

                description:
                    value === "indoor"
                        ? "Application: Indoor"
                        : "Application: Outdoor",

                domain: domain,

                invisible: "True",
            }
        ]);
    }


    onMinCurrentChange(ev) {
        const value = Number(ev.target.value);

        this.filterState.min_current = value;

        const searchModel = this.env.searchModel;

        if (this.minCurrentFilterGroupId) {
            searchModel.deactivateGroup(
                this.minCurrentFilterGroupId
            );

            this.minCurrentFilterGroupId = null;
        }

        // 0 means no filter
        if (value === 0) {
            return;
        }

        this.minCurrentFilterGroupId =
            searchModel.nextGroupId;

        searchModel.createNewFilters([
            {
                type: "filter",

                description:
                    `Min Current: ${value}`,

                domain: [
                    ["min_current", ">=", value]
                ],

                invisible: "True",
            }
        ]);
    }


    onMaxCurrentChange(ev) {
        const value = Number(ev.target.value);

        this.filterState.max_current = value;

        const searchModel = this.env.searchModel;

        if (this.maxCurrentFilterGroupId) {
            searchModel.deactivateGroup(
                this.maxCurrentFilterGroupId
            );

            this.maxCurrentFilterGroupId = null;
        }

        // 0 means no filter
        if (value === 0) {
            return;
        }

        this.maxCurrentFilterGroupId =
            searchModel.nextGroupId;

        searchModel.createNewFilters([
            {
                type: "filter",

                description:
                    `Max Current: ${value}`,

                domain: [
                    ["max_current", ">=", value]
                ],

                invisible: "True",
            }
        ]);
    }

    onMinVoltageChange(ev) {
        const value = Number(ev.target.value);
    
        this.filterState.min_voltage = value;
    
        const searchModel = this.env.searchModel;
    
        if (this.minVoltageFilterGroupId) {
            searchModel.deactivateGroup(
                this.minVoltageFilterGroupId
            );
    
            this.minVoltageFilterGroupId = null;
        }
    
        // 0 = no filter
        if (value === 0) {
            return;
        }
    
        this.minVoltageFilterGroupId =
            searchModel.nextGroupId;
    
        searchModel.createNewFilters([
            {
                type: "filter",
    
                description:
                    `Min Voltage: ${value}`,
    
                domain: [
                    ["min_voltage", ">=", value]
                ],
    
                invisible: "True",
            }
        ]);
    }

    onMaxVoltageChange(ev) {
        const value = Number(ev.target.value);
    
        this.filterState.max_voltage = value;
    
        const searchModel = this.env.searchModel;
    
        if (this.maxVoltageFilterGroupId) {
            searchModel.deactivateGroup(
                this.maxVoltageFilterGroupId
            );
    
            this.maxVoltageFilterGroupId = null;
        }
    
        // 0 = no filter
        if (value === 0) {
            return;
        }
    
        this.maxVoltageFilterGroupId =
            searchModel.nextGroupId;
    
        searchModel.createNewFilters([
            {
                type: "filter",
    
                description:
                    `Max Voltage: ${value}`,
    
                domain: [
                    ["max_voltage", ">=", value]
                ],
    
                invisible: "True",
            }
        ]);
    }

}


export const productFilterListView = {
    ...listView,
    Controller: ProductFilterController,
};


registry.category("views").add(
    "product_power_filter_list",
    productFilterListView
);





// /** @odoo-module **/

// import { ListController } from "@web/views/list/list_controller";
// import { listView } from "@web/views/list/list_view";
// import { registry } from "@web/core/registry";
// import { useService } from "@web/core/utils/hooks";
// import { onWillStart, useState } from "@odoo/owl";


// export class ProductFilterController extends ListController {

//     static template = "product_power_current.ProductFilterListView";

//     setup() {
//         super.setup();

//         this.orm = useService("orm");

//         this.filterValues = useState({
//             dimming: [],
//         });

//         this.filterState = useState({
//             dimming: "",
//             application: "all",
//         });

//         this.dimmingFilterGroupId = null;
//         this.applicationFilterGroupId = null;

//         onWillStart(async () => {
//             await this.loadFilterValues();
//         });
//     }


//     async loadFilterValues() {
//         this.filterValues.dimming = await this.orm.call(
//             "product.product",
//             "get_filter_values",
//             ["dimming"]
//         );
//     }


//     async onDimmingChange(ev) {
//         const value = ev.target.value;

//         this.filterState.dimming = value;

//         const searchModel = this.env.searchModel;

//         // Remove previous dimming filter
//         if (this.dimmingFilterGroupId) {
//             searchModel.deactivateGroup(
//                 this.dimmingFilterGroupId
//             );

//             this.dimmingFilterGroupId = null;
//         }

//         // "All"
//         if (!value) {
//             return;
//         }

//         this.dimmingFilterGroupId = searchModel.nextGroupId;

//         searchModel.createNewFilters([
//             {
//                 type: "filter",

//                 description: `Dimming: ${value}`,

//                 domain: [
//                     ["dimming", "=", value]
//                 ],

//                 invisible: "True",
//             }
//         ]);
//     }


//     onApplicationChange(ev) {
//         const value = ev.target.value;

//         this.filterState.application = value;

//         const searchModel = this.env.searchModel;

//         // Remove previous application filter
//         if (this.applicationFilterGroupId) {
//             searchModel.deactivateGroup(
//                 this.applicationFilterGroupId
//             );

//             this.applicationFilterGroupId = null;
//         }

//         // "All" = no application filter
//         if (value === "all") {
//             return;
//         }

//         let domain;

//         if (value === "indoor") {
//             domain = [
//                 ["protection_numeric", "!=", false],
//                 ["protection_numeric", ">", 0],
//                 ["protection_numeric", "<=", 54],
//             ];
//         } else if (value === "outdoor") {
//             domain = [
//                 ["protection_numeric", "!=", false],
//                 ["protection_numeric", ">", 54],
//             ];
//         } else {
//             return;
//         }

//         this.applicationFilterGroupId = searchModel.nextGroupId;

//         searchModel.createNewFilters([
//             {
//                 type: "filter",

//                 description:
//                     value === "indoor"
//                         ? "Application: Indoor"
//                         : "Application: Outdoor",

//                 domain: domain,

//                 invisible: "True",
//             }
//         ]);
//     }
// }


// export const productFilterListView = {
//     ...listView,
//     Controller: ProductFilterController,
// };


// registry.category("views").add(
//     "product_power_filter_list",
//     productFilterListView
// );
