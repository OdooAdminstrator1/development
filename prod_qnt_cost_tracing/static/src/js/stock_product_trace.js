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
                        self.do_action({
                        res_model: 'stock.product.trace.wizard',
                        views: [[false, 'form']],
                        target: 'new',
                        type: 'ir.actions.act_window',
                        context: context,
                    });
                    // self._rpc({
                    //     model: 'stock.product.trace',
                    //     method: 'open_date_filter',
                    //     args: [[self.getSelectedIds()]],
                    //     context: self.initialState.context,
                    // }).then(function (action) {
                    //     if (action) {
                    //         self.do_action(action);
                    //     }
                    // }).guardedCatch(function (error) {
                    //     self.displayNotification({
                    //         title: 'Error',
                    //         message: error.message || 'Failed to execute open_date_filter',
                    //         type: 'danger',
                    //     });
                    // });
                });
            } else if (this.modelName === 'stock.product.trace') {
                console.log('No buttons container found for stock.product.trace'); // Debug log
            }
        }
    });
});

/*
odoo.define('prod_qnt_cost_tracing.product_trace', function (require) {
    "use strict";

    var ListView = require('web.ListView');
    var core = require('web.core');

    ListView.include({
        render: function () {
            this._super.apply(this, arguments);
            console.log('ListView rendered'); // Debugging line
            this._addButton();
        },

        _addButton: function () {
            var self = this;

            console.log('Adding button'); // Debugging line
            var button = $('<button>')
                .addClass('btn btn-primary')
                .text('Last Accounting Date')
                .on('click', function () {
                    self._onButtonClick();
                });

            this.$('.o_list_buttons').append(button);
        },

        _onButtonClick: function () {
            // Implement your button click logic
            console.log('Button clicked!'); // Debugging line
        },
    });
});


odoo.define('prod_qnt_cost_tracing.trace_list_button', function (require) {
    "use strict";

    const ListController = require('web.ListController');
    const ListView = require('web.ListView');
    const viewRegistry = require('web.view_registry');
    const Dialog = require('web.Dialog');
    const core = require('web.core');
    const _t = core._t;

    const TraceListController = ListController.extend({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            if (this.$buttons) {
                const button = $('<button type="button" class="btn btn-primary o_list_button_add">')
                    .text(_t("Last Accounting Date"))
                    .on('click', this._onClickDateButton.bind(this));
                this.$buttons.append(button);
            }
        },

        _onClickDateButton: function () {
            const self = this;
            new Dialog(this, {
                title: _t("Pick a Date"),
                buttons: [
                    {text: _t("Cancel"), close: true},
                    {
                        text: _t("OK"), classes: 'btn-primary', close: true,
                        click: function () {
                            self.reload();
                        }
                    }
                ],
            }).open();
        },
    });

    const TraceListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: TraceListController,
        }),
    });

    // 👇 This line registers your view type globally
    viewRegistry.add('trace_list_view', TraceListView);
});
*/