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
        this.filterState.dimming = ev.target.value;
    }


    onApplicationChange(ev) {
        this.filterState.application = ev.target.value;
    }


    onMinCurrentChange(ev) {
        this.filterState.min_current = Number(ev.target.value);
    }


    onMaxCurrentChange(ev) {
        this.filterState.max_current =Number(ev.target.value);
    }

    onMinVoltageChange(ev) {
        this.filterState.min_voltage = Number(ev.target.value);
    }

    onMaxVoltageChange(ev) {
        this.filterState.max_voltage = Number(ev.target.value);
    }

    resetFilters() {
        const searchModel = this.env.searchModel;
    
        // Clear all active search/filter items from the search box
        searchModel.clearQuery();
    
        // Reset sidebar controls
        this.filterState.dimming = "";
        this.filterState.application = "all";
    
        this.filterState.min_current = 0;
        this.filterState.max_current = 0;
    
        this.filterState.min_voltage = 0;
        this.filterState.max_voltage = 0;
    
        // Forget the sidebar filter group IDs
        this.dimmingFilterGroupId = null;
        this.applicationFilterGroupId = null;
    
        this.minCurrentFilterGroupId = null;
        this.maxCurrentFilterGroupId = null;
    
        this.minVoltageFilterGroupId = null;
        this.maxVoltageFilterGroupId = null;
    }

    async onApplyFilters() {
        const searchModel = this.env.searchModel;
    
        // Remove previously created custom filters
        if (this.dimmingFilterGroupId) {
            searchModel.deactivateGroup(this.dimmingFilterGroupId);
            this.dimmingFilterGroupId = null;
        }
    
        if (this.applicationFilterGroupId) {
            searchModel.deactivateGroup(this.applicationFilterGroupId);
            this.applicationFilterGroupId = null;
        }
    
        if (this.minCurrentFilterGroupId) {
            searchModel.deactivateGroup(this.minCurrentFilterGroupId);
            this.minCurrentFilterGroupId = null;
        }
    
        if (this.maxCurrentFilterGroupId) {
            searchModel.deactivateGroup(this.maxCurrentFilterGroupId);
            this.maxCurrentFilterGroupId = null;
        }
    
        if (this.minVoltageFilterGroupId) {
            searchModel.deactivateGroup(this.minVoltageFilterGroupId);
            this.minVoltageFilterGroupId = null;
        }
    
        if (this.maxVoltageFilterGroupId) {
            searchModel.deactivateGroup(this.maxVoltageFilterGroupId);
            this.maxVoltageFilterGroupId = null;
        }
    
    
        // --------------------------------------------------
        // Dimming
        // --------------------------------------------------
    
        if (this.filterState.dimming) {
            this.dimmingFilterGroupId = searchModel.nextGroupId;
    
            searchModel.createNewFilters([
                {
                    type: "filter",
                    description: `Dimming: ${this.filterState.dimming}`,
                    domain: [
                        ["dimming", "=", this.filterState.dimming]
                    ],
                    invisible: "True",
                }
            ]);
        }
    
    
        // --------------------------------------------------
        // Application
        // --------------------------------------------------
    
        if (this.filterState.application !== "all") {
    
            let domain;
    
            if (this.filterState.application === "indoor") {
    
                domain = [
                    ["protection_numeric", "!=", false],
                    ["protection_numeric", "<=", 54],
                ];
    
            } else if (this.filterState.application === "outdoor") {
    
                domain = [
                    ["protection_numeric", "!=", false],
                    ["protection_numeric", ">", 54],
                ];
            }
    
            if (domain) {
                this.applicationFilterGroupId =
                    searchModel.nextGroupId;
    
                searchModel.createNewFilters([
                    {
                        type: "filter",
    
                        description:
                            this.filterState.application === "indoor"
                                ? "Application: Indoor"
                                : "Application: Outdoor",
    
                        domain: domain,
    
                        invisible: "True",
                    }
                ]);
            }
        }
    
    
        // --------------------------------------------------
        // Min Current
        // --------------------------------------------------
    
        if (this.filterState.min_current > 0) {
    
            this.minCurrentFilterGroupId =
                searchModel.nextGroupId;
    
            searchModel.createNewFilters([
                {
                    type: "filter",
    
                    description:
                        `Min Current: ${this.filterState.min_current}`,
    
                    domain: [
                        [
                            "min_current",
                            ">=",
                            this.filterState.min_current
                        ]
                    ],
    
                    invisible: "True",
                }
            ]);
        }
    
    
        // --------------------------------------------------
        // Max Current
        // --------------------------------------------------
    
        if (this.filterState.max_current > 0) {
    
            this.maxCurrentFilterGroupId =
                searchModel.nextGroupId;
    
            searchModel.createNewFilters([
                {
                    type: "filter",
    
                    description:
                        `Max Current: ${this.filterState.max_current}`,
    
                    domain: [
                        ["max_current", ">", 0],
                        ["max_current","<=",this.filterState.max_current]
                    ],
                    invisible: "True",
                }
            ]);
        }
    
    
        // --------------------------------------------------
        // Min Voltage
        // --------------------------------------------------
    
        if (this.filterState.min_voltage > 0) {
    
            this.minVoltageFilterGroupId =
                searchModel.nextGroupId;
    
            searchModel.createNewFilters([
                {
                    type: "filter",
    
                    description:
                        `Min Voltage: ${this.filterState.min_voltage}`,
    
                    domain: [
                        [
                            "min_voltage",
                            ">=",
                            this.filterState.min_voltage
                        ]
                    ],
    
                    invisible: "True",
                }
            ]);
        }
    
    
        // --------------------------------------------------
        // Max Voltage
        // --------------------------------------------------
    
        if (this.filterState.max_voltage > 0) {
    
            this.maxVoltageFilterGroupId =
                searchModel.nextGroupId;
    
            searchModel.createNewFilters([
                {
                    type: "filter",
    
                    description:
                        `Max Voltage: ${this.filterState.max_voltage}`,
    
                    domain: [
                        ["max_voltage",">",0],
                        ["max_voltage","<=",this.filterState.max_voltage]
                    ],
    
                    invisible: "True",
                }
            ]);
        }
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


