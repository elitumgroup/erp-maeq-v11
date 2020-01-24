odoo.define('eliterp_sri_electronic_voucher', function (require) {
"use strict";

var core = require('web.core');
var framework = require('web.framework');
var session = require('web.session');
var Widget = require('web.Widget');

var QWeb = core.qweb;
var _t = core._t;

var DashboardElectronicVoucherMain = Widget.extend({
    template: 'DashboardElectronicVoucherMain',

    init: function(){
        this.all_dashboards = ['summary', 'certificate'];
        return this._super.apply(this, arguments);
    },

    start: function(){
        return this.load(this.all_dashboards);
    },

    load: function(dashboards){
        var self = this;
        var loading_done = new $.Deferred();
        this._rpc({route: '/eliterp_sri_electronic_voucher/data'})
            .then(function (data) {
                // Para cada tablero
                var all_dashboards_defs = [];
                _.each(dashboards, function(dashboard) {
                    var dashboard_def = self['load_' + dashboard](data);
                    if (dashboard_def) {
                        all_dashboards_defs.push(dashboard_def);
                    }
                });

                // Se resuelve la carga cuando se resuelven todas las definiciones de los paneles.
                $.when.apply($, all_dashboards_defs).then(function() {
                    loading_done.resolve();
                });
            });
        return loading_done;
    },

    load_summary: function(data){
        return  new DashboardElectronicVoucherSummary(this, data.summary).replace(this.$('.o_sri_electronic_voucher_dashboard_summary'));
    },
    load_certificate: function(data){
        return  new DashboardElectronicVoucherCertificate(this, data.certificate).replace(this.$('.o_sri_electronic_voucher_dashboard_certificate'));
    },
});

var DashboardElectronicVoucherSummary = Widget.extend({

    template: 'DashboardElectronicVoucherSummary',

    events: {
        'click .o_vouchers_authorized': 'on_vouchers_authorized_clicked',
        'click .o_vouchers_not_authorized': 'on_vouchers_not_authorized_clicked',
        'click .o_vouchers_others': 'on_vouchers_others_clicked'
    },

    init: function(parent, data){
        this.data = data;
        this.parent = parent;
        return this._super.apply(this, arguments);
    },
    start: function() {
        this._super.apply(this, arguments);
    },
    reload:function(){
        return this.parent.load(['summary']);
    },
    on_vouchers_authorized_clicked: function (e) {
        var self = this;
        e.preventDefault();
        this.do_action("eliterp_sri_electronic_voucher.action_electronic_voucher_authorized", {
            additional_context: {
                search_default_last_thirty_days: 1
            },
            on_reverse_breadcrumb: function(){ return self.reload();}
        });
    },
    on_vouchers_not_authorized_clicked: function (e) {
        var self = this;
        e.preventDefault();
        this.do_action("eliterp_sri_electronic_voucher.action_electronic_voucher_not_authorized", {
            additional_context: {
                search_default_last_thirty_days: 1
            },
            on_reverse_breadcrumb: function(){ return self.reload();}
        });
    },
    on_vouchers_others_clicked: function (e) {
        var self = this;
        e.preventDefault();
        this.do_action("eliterp_sri_electronic_voucher.action_electronic_voucher_others", {
            additional_context: {
                search_default_last_thirty_days: 1
            },
            on_reverse_breadcrumb: function(){ return self.reload();}
        });
    },
});

var DashboardElectronicVoucherCertificate = Widget.extend({

    template: 'DashboardElectronicVoucherCertificate',

    events: {
        'click .o_vouchers_new_certificate': 'on_vouchers_new_certificate_clicked'
    },

    init: function(parent, data){
        this.data = data;
        this.parent = parent;
        return this._super.apply(this, arguments);
    },
    start: function() {
        this._super.apply(this, arguments);
    },
    reload:function(){
        return this.parent.load(['certificate']);
    },
    on_vouchers_new_certificate_clicked: function (e) {
        var self = this;
        e.preventDefault();
        this.do_action("eliterp_sri_electronic_voucher.action_digital_certificate", {
            on_reverse_breadcrumb: function(){ return self.reload();}
        });
    },
});

core.action_registry.add('electronic_voucher_dashboard.main', DashboardElectronicVoucherMain);

return {
    DashboardElectronicVoucherMain: DashboardElectronicVoucherMain,
    DashboardElectronicVoucherSummary: DashboardElectronicVoucherSummary,
    DashboardElectronicVoucherCertificate: DashboardElectronicVoucherCertificate
};

});
