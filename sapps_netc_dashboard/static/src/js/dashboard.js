odoo.define('sapps_netc_dashboard.sapps_netc_dashboard_template', function (require) {
'use strict';
var core = require('web.core');
var Widget = require('web.Widget');
var Context = require('web.Context');
var AbstractAction = require('web.AbstractAction');
var datepicker = require('web.datepicker');
var session = require('web.session');
var fieldUtils = require('web.field_utils');
var rpc = require("web.rpc");
//var framework = require('web.framework');
var QWeb = core.qweb;
var _t = core._t;
var fromDatePicker;
var toDatePicker;
var fromDate = new Date(new Date().getFullYear(), 0, 1);
var toDate = new Date();
var report_data = [];
var cash_funding = [];
var currency;
var dashboardReportsWidget = AbstractAction.extend({
    //hasControlPanel: true,
    template : 'sapps_netc_dashboardtemplate',
//    events: {
           'click .filter_button': 'changeFilters',
//           'change #oilAccountingFromDatePicker': 'changeFilters',
//           'change #oilAccountingToDatePicker': 'changeFilters'
//    },
    init: function(parent, action) {
        return this._super.apply(this, arguments);
    },
    start: function() {
        return this._super();

        debugger;

    },
    on_attach_callback: function () {
        this._super.apply(this, arguments);
        debugger;
        var self = this;
        $(document).ready(function(){
            debugger;
            $('.o_action_manager'). css("overflow-y","scroll");
            fromDatePicker = new datepicker.DateWidget(self, {date: new Date(new Date().getFullYear(), 0, 1)});
            fromDatePicker.appendTo($("#oilAccountingFromDatePicker"));
            toDatePicker = new datepicker.DateWidget(self, {date: new Date()});
            toDatePicker.appendTo($("#oilAccountingToDatePicker"));
            var innerSelf = self;
            innerSelf.changeFilters();
            $(document).on('click', '.filter_button', function(e){
                innerSelf.changeFilters();
            });
            $(document).on('click', '.td_production_report', function (e) {
                var clickedElem = $(this);
                var product_id = Number(clickedElem.attr('myproductid'));
                var fromDate = fromDatePicker.getValue()?? new Date(new Date().getFullYear(), 0, 1);;
                var toDate = toDatePicker.getValue()?? new Date();
                innerSelf.do_action({
                    type: 'ir.actions.act_window',
                    res_model: 'finished.product.report',
                    views: [[false, 'list']],
                    view_mode: 'list',
                    target: 'new',
                    domain: [['product_id', '=', Number(product_id)],['cost_date', '>=', fromDate], ['cost_date', '<=', toDate]],
                    name: 'Finished Product Report',
                });
            });
            $(document).on('click', '.td_on_hand_report', function (e) {
                var clickedElem = $(this);
                var production_lots = clickedElem.attr('myproductid').split(',').map(Number);
                innerSelf.do_action({
                    type: 'ir.actions.act_window',
                    res_model: 'stock.production.lot',
                    views: [[false, 'list']],
                    view_mode: 'list',
                    target: 'new',
                    domain: [['id','in', production_lots]],
                    name: 'Product Lots',
                });
            });
            $(document).on('click', '.foldable_account_group', function(e){
                var clickedElem = $(this);
                var group_name = clickedElem.attr('data-id');
                if(clickedElem.hasClass('fa-caret-right'))
                {
                    clickedElem.removeClass('fa-caret-right');
                    clickedElem.addClass('fa-caret-down');
                    var lines = cash_funding.filter(obj => {
                                                  return obj.group_name === group_name
                                                });
                    var trr = clickedElem.closest('tr');
                    lines[0].items.forEach(function(l){
                        trr.after("<tr class='detailed_tr' data_id=detailed" + group_name + ">" + "<td class='detailed_td'>"+l['code']+l['name']+"</td>" + "<td class='text-right'>"+l['init']+ "</td>" + "<td class='text-right'>"+l['balance']+"</td>" + "<td class='text-right'>"+l['init_currency']+ ' ' + l['symbol'] +"</td>" + "<td class='text-right'>"+l['currecny']+' ' + l['symbol'] +"</td></tr>");
                    });

                }else{
                    clickedElem.addClass('fa-caret-right');
                    clickedElem.removeClass('fa-caret-down');
                    var dId = 'detailed'+group_name;
                    $('tr[data_id="'+dId+'"]').each(function(e){
                        $(this).remove()
                    });
                }
            });


        });
    },
    changeFilters: function () {
            $("#production_div_report_container").html('');
            $("#onhand_div_report_container").html('');
            $("#sold_div_report_container").html('');
            $("#partner_ledger_div_report_container").html('');
            $("#cash_report_report_container").html('');
            var self = this;

            fromDate = fromDatePicker.getValue();
            toDate = toDatePicker.getValue();

            self._rpc({
                model: 'account.account',
                method: 'get_base_currency',
                args: [1],
            }).then(function(e) {
                $('#currency_container').html(e);
            });
            self._rpc({
                model: 'account.account',
                method: 'get_finished_product_report',
                args: [1, fromDate, toDate],
            }).then(function(e) {
                var generatedHtml = QWeb.render("sapps_netc_dashboard_template_production_report",
                {res: e });
                var containerElem = $('#production_div_report_container')
                containerElem.append(generatedHtml);
            });
            self._rpc({
                model: 'account.account',
                method: 'get_onhand_quantity_group_by_location',
                args: [1, toDate],
            }).then(function(e) {
                var result = e['result'];
                var products = e['products'];
                var locs = e['locations'];
                var length_loc = locs.length;
                var generatedHtml = QWeb.render("sapps_netc_dashboard_template_onhand_report",
                {res: result, locations:locs , length_loc:length_loc});
                var containerElem = $('#onhand_div_report_container')
                containerElem.append(generatedHtml);

            });

            self._rpc({
                model: 'account.account',
                method: 'get_query_sold_quantity_price_cogs',
                args: [1, fromDate, toDate],
            }).then(function(e) {
                var result = e['res'];
                var total_q = e['total_sold'];
                var total_cogs = e['total_cogs'];
                var total_invoiced = e['total_invoiced']
                var generatedHtml = QWeb.render("sapps_netc_dashboard_template_sold_report",
                {res: result, total_sold:total_q, total_cogs: total_cogs, total_inv:total_invoiced });
                var containerElem = $('#sold_div_report_container')
                containerElem.append(generatedHtml);

            });


            self._rpc({
                model: 'account.account',
                method: 'get_partner_query_sums',
                args: [1, fromDate, toDate],
            }).then(function(e) {
                var generatedHtml = QWeb.render("sapps_netc_dashboard_template_partner_ledger_report",
                {res: e });
                var containerElem = $('#partner_ledger_div_report_container')
                containerElem.append(generatedHtml);

            });
            var innerSelf = self;
            self._rpc({
                model: 'account.account',
                method: 'get_cash_ending_balance',
                args: [1, fromDate, toDate],
            }).then(function(e) {
                var generatedHtml = QWeb.render("sapps_netc_dashboard_template_cash_report",
                {res: e });
                cash_funding = e;
                var containerElem = $('#cash_report_report_container')
                containerElem.append(generatedHtml);

            });


    },

});
core.action_registry.add('sapps_netc_dashboardtemplate', dashboardReportsWidget);

return dashboardReportsWidget;
});