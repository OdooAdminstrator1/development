/** @odoo-module **/

    import { patch } from "@web/core/utils/patch";

    import Domain from "web.Domain";
    const ActionModel = require("web.ActionModel");
    import { FACET_ICONS } from "web.searchUtils";
    import { Model } from "web.Model";
    import { parseArch } from "web.viewUtils";
    import pyUtils from "web.py_utils";
    import Registry from "web.Registry";

    const { Component, hooks } = owl;
    const { useState } = hooks;
    patch(ActionModel.prototype, "my Action Component", {
       _getFacets() {
            if(this.state === undefined){
                this.state = useState({ and_pressed: false });

            }
            const types = this.config.searchMenuTypes || [];
            const isValidType = (type) => (
                !['groupBy', 'comparison'].includes(type) || types.includes(type)
            );
            const facets = [];
            for (const extension of this.extensions.flat()) {
                for (const facet of extension.get("facets") || []) {
                    if (!isValidType(facet.type)) {
                        continue;
                    }

                    if (event.key === 'Enter' && event.ctrlKey===true){
                        this.state.and_pressed = true;
                    }
                    if (event.key === 'Enter' && event.ctrlKey===false){
                        console.log(this.env.session.user_context);
                        this.state.and_pressed = false;
                    }
                    facet.separator = facet.type === 'groupBy' ? ">" : this.state.and_pressed? this.env._t("and"):this.env._t("or");
                    if (facet.type in FACET_ICONS) {
                        facet.icon = FACET_ICONS[facet.type];
                    }
                    facets.push(facet);
                }
            }
            return facets;
        },
    });