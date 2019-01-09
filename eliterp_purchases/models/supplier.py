# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models, _
from odoo.tools import float_is_zero
from datetime import datetime
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.multi
    def _purchase_invoice_count(self):
        """
        Método modificado
        :return: object
        """
        PurchaseOrder = self.env['purchase.order']
        Invoice = self.env['account.invoice']
        for partner in self:
            partner.purchase_order_count = PurchaseOrder.search_count([('partner_id', 'child_of', partner.id)])
            invoices = Invoice.search(
                [('partner_id', '=', partner.id), ('state', '!=', 'cancel'), ('type', '=', 'in_invoice')])
            partner.supplier_invoice_count = round(float(sum(line.amount_total for line in invoices)),
                                                   2)  # Total facturado
            partner.pending_balance = round(float(sum(line.residual for line in invoices)),
                                            2)  # Total de saldo pendiente

    @api.onchange('property_account_payable_id')
    def _onchange_property_account_payable(self):
        """
        No hacemos nada
        :return: self
        """
        return

    @api.multi
    def action_view_pending_balance(self):
        """
        Facturas con saldo pendiente de proveedor
        """
        if float_is_zero(self.pending_balance, precision_rounding=3):  # Si es 0 no se lleva a la acción
            return
        invoices = self.env['account.invoice'].search([
            ('partner_id', '=', self.id),
            ('state', '=', 'open'),
            ('type', '=', 'in_invoice')
        ])
        invoices = invoices.filtered(lambda invoice: not invoice.reconciled)
        action = self.env.ref('purchase.act_res_partner_2_supplier_invoices')
        result = action.read()[0]
        if len(invoices) > 1:
            result['domain'] = "[('id','in',%s)]" % (invoices.ids)
        elif len(invoices) == 1:
            res = self.env.ref('account.invoice_supplier_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = invoices.id
        return result

    pending_balance = fields.Float(compute='_purchase_invoice_count', string='Saldo')
    tradename = fields.Char('Nombre comercial')
    payment_conditions = fields.Selection([
        ('cash', 'Contado'),
        ('credit', 'Crédito'),
        ('credit_fees', 'Crédito cuotas')
    ], string='Condición de pago')
    way_to_pay = fields.Selection([('transfer', 'Transferencia'), ('check', 'Cheque'), ('cash', 'Efectivo')],
                                  string='Forma de pago')
    property_account_payable_id = fields.Many2one('account.account',
                                                  string='Cuenta a pagar',
                                                  domain=[('account_type', '=', 'movement')])

    # RISE
    @api.multi
    def _validate_rise(self, amount):
        journal = self.env['account.journal'].search([('name', '=', 'Notas de venta')])[0].id
        for partner in self:
            if not partner.rise_category_activity_id:
                raise ValidationError("Proveedor no tiene configurado RISE.")
            notes = self.env['account.invoice'].search([
                ('partner_id', '=', partner.id),
                ('journal_id', '=', journal),
                ('state', 'not in', ('draft', 'cancel'))
            ])
            notes_total = notes.filtered(
                lambda note: (datetime.strptime(note.date_invoice, "%Y-%m-%d")).year == datetime.today().date().year)
            total_notes = round(sum(nota.amount_total for nota in notes_total), 2)
            if (amount + total_notes) > (partner.max_amount * 12):
                raise ValidationError("Ha sobrepasado el monto máximo anual del RISE.")

    rise_category_id = fields.Many2one('eliterp.rise.category', 'Categoría')
    rise_activity_id = fields.Many2one('eliterp.rise.activity', 'Actividad')
    rise_category_activity_id = fields.Many2one('eliterp.rise.category.activity', 'Categoría/Actividad')
    max_amount = fields.Float('Monto máximo (Mensual)', related='rise_category_activity_id.max_amount', store=True)
