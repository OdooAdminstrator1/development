/** @odoo-module **/

import { Component } from "@odoo/owl";


export class ProductFilterPanel extends Component {

    static template = "product_power_current.ProductFilterPanel";

    onChange(fieldName, ev) {
        this.props.onChange(fieldName, ev.target.value);
    }
}