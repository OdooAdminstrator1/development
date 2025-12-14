odoo.define('prod_qnt_cost_tracing.stock_product_trace_list', function (require) {
    "use strict";

    console.log('JavaScript file loaded for your_module_name'); // Debug log to confirm loading

    var ListController = require('web.ListController');

    ListController.include({
        init: function () {
            console.log('StockProductTraceList init called for model:', this.modelName); // Debug log
            this._super.apply(this, arguments);
            if (this.modelName === 'stock.product.trace') {
                this.buttons_template = 'StockProductTrace.Buttons';
                console.log('Applied custom buttons_template for stock.product.trace'); // Debug log
            }
        },
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (this.modelName === 'stock.product.trace' && this.$buttons) {
                console.log('Rendering custom buttons for stock.product.trace'); // Debug log
                var self = this;
                this.$buttons.find('.o_button_at_date').off('click').on('click', function (ev) {
                    ev.stopPropagation();
                    console.log('Custom button clicked!'); // Debug log
                    var context = {
                            active_model: this.modelName,
                        };
                    self.do_action('prod_qnt_cost_tracing.action_stock_product_trace_wizard_form',
                         { additional_context: context
                         });
                    //     self.do_action({
                    //     res_model: 'stock.product.trace.wizard',
                    //     views: [[false, 'form']],
                    //     target: 'new',
                    //     type: 'ir.actions.act_window',
                    //     context: context,
                    // });
                });
            } 
        }
    });
});

