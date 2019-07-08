# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError


class QuotaLineInvoice(models.Model):
    _name = 'eliterp.quota.line.invoice'

    _description = 'Línea de cuotas en factura de proveedor'

    number = fields.Integer('No.', required=True)
    amount = fields.Float('Monto de cuota', required=True)
    expiration_fee = fields.Date('Fecha vencimiento cuota', required=True)
    invoice_id = fields.Many2one('account.invoice', string='Factura')


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.onchange('payment_conditions')
    def _onchange_payment_conditions(self):
        if self.payment_conditions:
            if self.payment_conditions != 'credit':
                self.payment_term_id = False
                self.date_due = self.date_invoice

    @api.onchange('partner_id', 'is_sale_note')
    def _onchange_partner_id(self):
        """
        Obtenemos Condiciones de pago de Proveedor si existen
        :return: object
        """
        res = super(AccountInvoice, self)._onchange_partner_id()
        self.payment_conditions = self.partner_id.payment_conditions
        if self.partner_id.payment_conditions == 'credit':
            self.payment_term_id = self.partner_id.property_supplier_payment_term_id.id
        if self.is_sale_note:  # Nota de venta
            self.journal_id = self.env['account.journal'].search([('name', '=', 'Notas de venta')])[0].id
        return res

    def _prepare_invoice_line_from_po_line(self, line):
        """
        Agregamos el proyecto y CC de la OC a las líneas de factura
        :param line:
        :return:
        """
        data = super(AccountInvoice, self)._prepare_invoice_line_from_po_line(line)
        order = line.order_id
        data.update({
            'account_analytic_id': order.account_analytic_id.id,
            'project_id': order.project_id.id
        })
        return data

    # Load all unsold PO lines
    @api.onchange('purchase_id')
    def purchase_order_change(self):
        """
        MM: Agregamos los centro de costo y proyecto desde la Orde de compra, también la cuenta del proveedor
        si es que existe
        """
        if not self.purchase_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.purchase_id.partner_id.id

        new_lines = self.env['account.invoice.line']
        for line in self.purchase_id.order_line - self.invoice_line_ids.mapped('purchase_line_id'):
            data = self._prepare_invoice_line_from_po_line(line)
            new_line = new_lines.new(data)
            new_line._set_additional_fields(self)
            new_lines += new_line

        self.invoice_line_ids += new_lines
        self.date_invoice = self.purchase_id.date_order # MARZ
        self.payment_term_id = self.purchase_id.payment_term_id
        self.account_analytic_id = self.purchase_id.account_analytic_id.id  # MARZ
        self.project_id = self.purchase_id.project_id.id  # MARZ
        self.account_id = self.partner_id.property_account_payable_id  # MARZ
        self.env.context = dict(self.env.context, from_purchase_order_change=True)
        self.purchase_id = False
        return {}

    @api.multi
    def load_fees(self):
        """
        Creamos línea de cuotas
        """
        if not self.date_invoice or not self.date_due:
            raise UserError('Necesita la fecha de factura y vencimiento.')
        if self.amount_of_fees <= 1:
            raise UserError('Número de cuotas debe ser mayor a 1.')
        quota_line = []
        self.quota_line_invoice.unlink()  # Borramos líneas anteriores
        for x in range(1, self.amount_of_fees):
            start_date = datetime.strptime(self.date_invoice, "%Y-%m-%d")
            carry, new_month = divmod(start_date.month + x, 12)
            if new_month == 0:
                new_month = 12
            date = start_date.replace(year=start_date.year + carry, month=new_month)
            quota_line.append([0, 0, {
                'number': x,
                'amount': 0,
                'expiration_fee': date,
            }])
        return self.update({'quota_line_invoice': quota_line})

    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string='Centro de costo', readonly=True,
                                          states={'draft': [('readonly', False)]})
    attach_invoice = fields.Binary('Adjuntar factura', attachment=True)
    attached_name = fields.Char('Nombre de adjunto')
    concept = fields.Char('Concepto', readonly=True,
                          states={'draft': [('readonly', False)]})
    payment_conditions = fields.Selection([
        ('cash', 'Contado'),
        ('credit', 'Crédito'),
        ('credit_fees', 'Crédito cuotas')
    ], string='Condición de pago', readonly=True, states={'draft': [('readonly', False)]})
    amount_of_fees = fields.Integer('Cantidad de cuotas', readonly=True, states={'draft': [('readonly', False)]},
                                    default=1)
    quota_line_invoice = fields.One2many('eliterp.quota.line.invoice', 'invoice_id', string='Línea de cuotas',
                                         readonly=True,
                                         states={'draft': [('readonly', False)]})
