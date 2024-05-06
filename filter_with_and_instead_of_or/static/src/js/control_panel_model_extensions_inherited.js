odoo.define("filter_with_and_instead_of_or/static/src/js/control_panel/control_panel_model_extension.js", function (require) {
    "use strict";

    const { Component } = owl;
    const ActionModel = require("web.ActionModel");
    const Domain = require('web.Domain');
    const pyUtils = require('web.py_utils');
    const ControlPanel = require('web.ControlPanel');

    class MyControlPanel extends ActionModel.registry.map.ControlPanel{
        _getAutoCompletionFilterDomain(filter, filterQueryElements) {
            const domains = filterQueryElements.map(({ label, value, operator }) => {
                let domain;
                if (filter.filterDomain) {
                    domain = Domain.prototype.stringToArray(
                        filter.filterDomain,
                        {
                            self: label,
                            raw_value: value,
                        }
                    );
                } else {
                    // Create new domain
                    domain = [[filter.fieldName, operator, value]];
                }
                return Domain.prototype.arrayToString(domain);
            });
            return pyUtils.assembleDomains(domains, (event.key === 'Enter' && event.ctrlKey===true)?'AND': 'OR');
        }
    }
    ActionModel.registry.add("ControlPanel", MyControlPanel, 100);
    return MyControlPanel;
});