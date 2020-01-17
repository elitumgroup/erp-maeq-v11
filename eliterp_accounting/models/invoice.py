# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo.tools import float_is_zero
from odoo import api, fields, models, _
from datetime import datetime, date
from odoo.exceptions import UserError
from odoo.addons import decimal_precision as dp

TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale',
    'in_refund': 'purchase',
}


class ReasonCancelInvoice(models.TransientModel):
    _name = 'eliterp.reason.cancel.invoice'

    _description = 'Razón para cancelar factura'

    description = fields.Text('Descripción', required=True)

    @api.multi
    def cancel_invoice(self):
        """
        Cancelamos factura
        :return: boolean
        """
        invoice = self.env['account.invoice'].browse(self._context['active_id'])
        invoice.action_cancel()
        invoice.move_id.write({'ref': self.description})
        if invoice.have_withhold:
            for line in invoice.withhold_id.lines_withhold:  # Borrramos las líneas de impuestos de la retención
                invoice_tax = self.env['account.invoice.tax'].search([
                    ('invoice_id', '=', invoice.id),
                    ('name', '=', line.tax_id.name),
                    ('tax_id', '=', line.tax_id.id),
                    ('account_id', '=', line.tax_id.account_id.id)
                ])
                invoice_tax.unlink()
            invoice.withhold_id.write({
                'withhold_number': invoice.withhold_number + ' anulada',
                'state': 'cancel'
            })
        invoice.write({
            'withhold_id': False,
            'have_withhold': False,
            'comment': 'Factura [%s]: anulada por %s' % (invoice.invoice_number, self.description),
        })
        if invoice.type == 'in_invoice':  # Colocamos No. Factura en False para no tener problemas al crear la misma
            invoice.write({'invoice_number': False})
        invoice._compute_amount()
        invoice._compute_residual()
        return True


class AccountInvoiceTax(models.Model):
    _inherit = 'account.invoice.tax'

    @api.model
    def create(self, values):
        if 'credit_note' in self._context:  # Si es nota de crédito se cambia impuestos a no manual
            values.update({'manual': False})
        return super(AccountInvoiceTax, self).create(values)


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        domain = {}
        if not self.invoice_id:
            return

        part = self.invoice_id.partner_id
        fpos = self.invoice_id.fiscal_position_id
        company = self.invoice_id.company_id
        currency = self.invoice_id.currency_id
        type = self.invoice_id.type

        if not part:
            warning = {
                'title': _('Warning!'),
                'message': _('You must first select a partner!'),
            }
            return {'warning': warning}

        if not self.product_id:
            if type not in ('in_invoice', 'in_refund'):
                self.price_unit = 0.0
            domain['uom_id'] = []
        else:
            if part.lang:
                product = self.product_id.with_context(lang=part.lang)
            else:
                product = self.product_id

            self.name = product.partner_ref
            account = self.get_invoice_line_account(type, product, fpos, company)
            if account:
                self.account_id = account.id
            self._set_taxes()

            if type in ('in_invoice', 'in_refund'):  # MARZ
                if product.description_purchase:
                    self.name = product.description_purchase
            else:
                if product.description_sale:
                    self.name = product.description_sale

            if not self.uom_id or product.uom_id.category_id.id != self.uom_id.category_id.id:
                self.uom_id = product.uom_id.id
            domain['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]

            if company and currency:
                if company.currency_id != currency:
                    self.price_unit = self.price_unit * currency.with_context(
                        dict(self._context or {}, date=self.invoice_id.date_invoice)).rate

                if self.uom_id and self.uom_id.id != product.uom_id.id:
                    self.price_unit = product.uom_id._compute_price(self.price_unit, self.uom_id)
        return {'domain': domain}

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_ids', 'quantity',
                 'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
                 'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None
        if self.invoice_id.type in ['in_refund', 'in_invoice']:
            price = self.price_unit - self.discount or 0.0
        else:
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        taxes = False
        if self.invoice_line_tax_ids:
            taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id,
                                                          partner=self.invoice_id.partner_id)
        self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
        self.price_total = taxes['total_included'] if taxes else self.price_subtotal
        if self.invoice_id.currency_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
            price_subtotal_signed = self.invoice_id.currency_id.with_context(
                date=self.invoice_id._get_currency_rate_date()).compute(price_subtotal_signed,
                                                                        self.invoice_id.company_id.currency_id)
        sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
        self.price_subtotal_signed = price_subtotal_signed * sign

    discount = fields.Float(string='Descuento', digits=dp.get_precision('Discount'),
                            default=0.0)  # CM


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def copy(self, default=None):
        """
        Al duplicar eliminamos impuestos de retención de la antigua
        :param default:
        :return:
        """
        record = super(AccountInvoice, self).copy(default=default)
        for tax in record.tax_line_ids.filtered(lambda x: x.tax_id.tax_type == 'retention'):
            tax.unlink()
        return record

    @api.multi
    def get_taxes_values(self):
        tax_grouped = {}
        for line in self.invoice_line_ids:
            if self.type in ['in_refund', 'in_invoice']:
                price_unit = line.price_unit - line.discount or 0.0
            else:
                price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.invoice_line_tax_ids.compute_all(price_unit, self.currency_id, line.quantity, line.product_id,
                                                          self.partner_id)['taxes']
            for tax in taxes:
                val = self._prepare_tax_line_vals(line, tax)
                key = self.env['account.tax'].browse(tax['id']).get_grouping_key(val)

                if key not in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
        return tax_grouped

    @api.multi
    def action_cancel(self):
        """
        MM: Cancelamos la factura si no tiene pagos/cobros realizados
        """
        moves = self.env['account.move']
        for inv in self:
            if inv.move_id:
                moves += inv.move_id
            if inv.payment_move_line_ids:
                raise UserError(_(
                    'You cannot cancel an invoice which is partially paid. You need to '
                    'unreconcile related payment entries first.'))
        if moves:
            moves.with_context(from_invoice=True).reverse_moves(self.date_invoice, self.journal_id or False)
            moves.write({'state': 'cancel'})
        invoice_reference = self.reference if self.reference else "/"
        self.write({
            'state': 'cancel',
            'reference': "%s anulada" % invoice_reference
        })
        return True

    @api.multi
    def name_get(self):
        """
        Cambiamos el nombre del registro para mostrar
        """
        types = {
            'out_invoice': 'Factura de cliente',
            'in_invoice': 'Factura de proveedor',
            'out_refund': 'Nota de crédito cliente',
            'in_refund': 'Nota de crédito proveedor'
        }
        result = []
        for invoice in self:
            if not invoice.is_sale_note:
                result.append((invoice.id, "%s [%s]" % (types[invoice.type], invoice.invoice_number or '/')))
            else:
                result.append((invoice.id, "Nota de venta [%s]" % invoice.invoice_number or '/'))
        return result

    @api.multi
    def open_reason_cancel_invoice(self):
        """
        Abrimos ventana emergente para cancelar factura
        :return: dict
        """
        context = dict(self._context or {})
        return {
            'name': "Explique la razón",
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.reason.cancel.invoice',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context,
        }

    @api.multi
    def action_invoice_open(self):
        """
        MM: Validamos la factura
        :return: object
        """
        # Notas de crédito
        if self.type in ('in_refund', 'out_refund'):
            notes_credit = self.env['account.invoice'].search(
                [('invoice_reference', '=', self.invoice_reference.id), ('state', '=', 'open')])
            amount_notes = self.invoice_reference.amount_untaxed - sum(note.amount_total for note in notes_credit)
            if self.amount_untaxed > amount_notes:
                raise UserError("Excede de la base imponible de la referencia [%s]." %
                                self.invoice_reference.invoice_number)
            res = super(AccountInvoice, self).action_invoice_open()
            self.write({'state_notes': 'posted'})
            return res
        # Facturas de proveedor
        if self.type == 'in_invoice':
            if self.takes_hold and not self.is_sale_note:
                if not self.have_withhold:
                    raise UserError("Debe ingresar la retención correspondiente a la factura.")
                else:
                    res = super(AccountInvoice, self).action_invoice_open()
                    self.withhold_id.write({
                        'state': 'confirm',
                        'name': self.withhold_id.journal_id.sequence_id.next_by_id()
                    })
            # Validamos RISE
            if self.is_sale_note:
                self.partner_id._validate_rise(self.amount_total)
        else:
            res = super(AccountInvoice, self).action_invoice_open()
        # Facturas de cliente y notas de crédito
        if self.type in ['out_invoice', 'out_refund'] and not self.is_electronic:
            self.action_number()
        return super(AccountInvoice, self).action_invoice_open()

    @api.model
    def _default_journal(self):
        if self._context.get('default_journal_id', False):
            return self.env['account.journal'].browse(self._context.get('default_journal_id'))
        if self._context.get('default_is_sale_note', False):  # Nota de venta
            return self.env['account.journal'].search([('name', '=', 'Notas de venta')])[0].id
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', [TYPE2JOURNAL[ty] for ty in inv_types if ty in TYPE2JOURNAL]),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice')
    def _compute_amount(self):
        """
        MM: Calculamos el total de la factura
        """
        round_curr = self.currency_id.round
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        # Cambiamos los valores de impuestos (Retención)
        total_tax = 0.00
        amount_retention = 0.00
        for line in self.tax_line_ids:
            if line.amount >= 0:
                total_tax += line.amount
            else:
                amount_retention += line.amount
        self.amount_tax = round_curr(total_tax)
        self.amount_retention = round_curr(-1 * amount_retention)
        self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign
        # Cargar base cero IVA y base gravada
        total_base_taxed = 0.00
        total_base_zero_iva = 0.00
        for line in self.invoice_line_ids:
            if not line.invoice_line_tax_ids:  # NO IMPUESTOS BASE 0
                total_base_zero_iva += line.price_subtotal
                continue
            for tax in line.invoice_line_tax_ids:
                if tax.amount > 0:
                    total_base_taxed += line.price_subtotal
                else:
                    total_base_zero_iva += line.price_subtotal
        self.base_zero_iva = total_base_zero_iva
        self.base_taxed = total_base_taxed
        self.amount_without_discount = round_curr(self.amount_untaxed + self.amount_discount)

    @api.one
    @api.depends(
        'state', 'currency_id', 'invoice_line_ids.price_subtotal',
        'move_id.line_ids.amount_residual',
        'move_id.line_ids.currency_id')
    def _compute_residual(self):
        """
        MM: Calculamos el valor pendiente de pago/cobro
        :return: self
        """
        residual = 0.0
        residual_company_signed = 0.0
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        for line in self.sudo().move_id.line_ids:
            if line.account_id.internal_type in (
                    'receivable', 'payable'):  # TODO: Si la cuenta no es de este tipo la pondrá como pagada
                residual_company_signed += line.amount_residual
                if line.currency_id == self.currency_id:
                    residual += line.amount_residual_currency if line.currency_id else line.amount_residual
                else:
                    from_currency = (line.currency_id and line.currency_id.with_context(
                        date=line.date)) or line.company_id.currency_id.with_context(date=line.date)
                    residual += from_currency.compute(line.amount_residual, self.currency_id)
        self.residual_company_signed = abs(residual_company_signed) * sign
        self.residual_signed = abs(residual) * sign
        self.residual = abs(residual)
        digits_rounding_precision = self.currency_id.rounding
        if float_is_zero(self.residual, precision_rounding=digits_rounding_precision):
            self.reconciled = True
        else:
            self.reconciled = False
        # Calcular nuevamente base cero IVA y base gravada
        total_base_taxed = 0.00
        total_base_zero_iva = 0.00
        for line in self.invoice_line_ids:
            for tax in line.invoice_line_tax_ids:
                if tax.amount > 0:
                    total_base_taxed += line.price_subtotal
                else:
                    total_base_zero_iva += line.price_subtotal
        self.base_zero_iva = total_base_zero_iva
        self.base_taxed = total_base_taxed

    @api.model
    def create(self, values):
        if not values.get('date_invoice'):
            values['date_invoice'] = date.today().strftime('%Y-%m-%d')
        self.env['eliterp.global.functions'].valid_period(
            values['date_invoice'])  # Validar período contable sea correcto
        return super(AccountInvoice, self).create(values)

    @api.multi
    def print_invoice(self):
        """
        Imprimimos factura
        """
        self.ensure_one()
        if self.type == 'out_invoice':  # TODO: Cliente
            pass
        else:  # Proveedor
            return self.env.ref('eliterp_accounting.eliterp_action_report_invoice_supplier').report_action(self)

    def _default_new_currency(self):
        """
        TODO: Obtenemos la moneda (USD), si no se ha configurado en datos de compañía
        """
        return self.env['res.currency'].search([('name', '=', 'USD')])[0].id

    @api.depends('date_invoice')
    @api.one
    def _get_accounting_period(self):
        """
        Obtenemos el período contable con la fecha de factura
        """
        if not self.date_invoice:
            self.period = False
        else:
            date = datetime.strptime(self.date_invoice, "%Y-%m-%d")
            period = self.env['eliterp.account.period'].search([('year_accounting', '=', date.year)])
            if len(period) == 0:
                self.period = False  # Cambiar por testeo en ODOO.sh
            accounting_period = period.lines_period.filtered(lambda x: x.code == date.month)
            self.period = accounting_period.id

    takes_hold = fields.Boolean('Lleva retención?', default=True, readonly=True,
                                states={'draft': [('readonly', False)]})
    # CM
    date_invoice = fields.Date('Fecha emisión',
                               readonly=True, states={'draft': [('readonly', False)]}, index=True,
                               help="Keep empty to use the current date", copy=False, default=fields.Date.context_today,
                               required=True)
    # CM
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  required=True, readonly=True, states={'draft': [('readonly', False)]},
                                  default=_default_new_currency, track_visibility='onchange')
    period = fields.Many2one('eliterp.lines.account.period', string='Período', store=True, readonly=True,
                             compute='_get_accounting_period')

    @api.one
    @api.depends('invoice_line_ids.price_subtotal')
    def _compute_amount_discount(self):
        if not self.invoice_line_ids:
            return 0.00
        else:
            total = 0.00
            for line in self.invoice_line_ids:
                subtotal = round(line.price_unit * line.quantity * (line.discount / 100), 3)
                total += subtotal
            self.amount_discount = total

    amount_without_discount = fields.Float('Subtotal sin Descuento', currency_field='currency_id',
                                           compute='_compute_amount',
                                           store=True)
    amount_discount = fields.Float('Descuento', currency_field='currency_id', compute='_compute_amount_discount',
                                   store=True)
    amount_retention = fields.Monetary('Total a retener', store=True,
                                       currency_field='currency_id', readonly=True, compute='_compute_amount')
    base_zero_iva = fields.Float('Subotal Base cero', currency_field='currency_id', compute='_compute_amount',
                                 store=True)
    base_taxed = fields.Float('Subtotal IVA', currency_field='currency_id', compute='_compute_amount',
                              store=True)
    is_sale_note = fields.Boolean('Es nota de venta?', default=False)
    journal_id = fields.Many2one('account.journal', string='Journal',
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 default=_default_journal,
                                 domain="[('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['sale'], "
                                        "'in_refund': ['purchase'], 'in_invoice': ['purchase']}.get(type, [])), "
                                        "('company_id', '=', company_id)]")
    # Campos cambiados por trazabilidad
    type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Vendor Bill'),
        ('out_refund', 'Customer Credit Note'),
        ('in_refund', 'Vendor Credit Note'),
    ], readonly=True, index=True, change_default=True,
        default=lambda self: self._context.get('type', 'out_invoice'),
        track_visibility='onchange')
