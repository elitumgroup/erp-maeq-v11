# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class BalanceVoucherPayment(models.Model):
    _name = 'eliterp.balance.voucher.payment'
    _description = 'Saldo en cobro'

    def confirm_balance(self):
        voucher = self.env['account.voucher'].browse(self._context['active_id'])
        voucher.write({
            'balance_account': self.balance_account.id,
            'balance': self.balance,
            'show_account': True,
            'flag': True
        })
        voucher.validate_voucher()
        return True

    balance = fields.Float('Saldo')
    balance_account = fields.Many2one('account.account', string='Cuenta saldo',
                                      domain=[('account_type', '=', 'movement')])


class LinesPayment(models.Model):
    _name = "eliterp.lines.payment"

    _description = 'Líneas de cobro'

    @api.constrains('amount')
    def _check_amount(self):
        """
        Validamos monto
        """
        if self.amount <= 0:
            raise ValidationError("Monto no puede ser menor o igual a 0.")

    @api.one
    @api.constrains('date_issue')
    def _check_date(self):
        """
        Verificamos la fechas
        """
        if self.date_due < self.date_issue:
            raise ValidationError('La fecha de vencimiento no puede ser menor a la de emisión.')

    @api.onchange('drawer')
    def _onchange_drawer(self):
        self.is_beneficiary = True

    @api.onchange('date_issue')
    def _onchange_date_issue(self):
        if self.date_issue:
            self.date_due = self.date_issue

    type_payment = fields.Selection([
        ('bank', 'Cheque'),
        ('cash', 'Efectivo'),
        ('deposit', 'Depósito'),
        ('transfer', 'Transferencia')
    ], string='Tipo de cobro')
    drawer = fields.Char('Girador')
    account_number = fields.Char('No. Cuenta')
    check_number = fields.Char('No. Cheque')
    bank_id = fields.Many2one('res.bank', 'Banco')
    account_id = fields.Many2one('account.account', string='Cuenta', domain=[('account_type', '=', 'movement')])
    amount = fields.Float('Monto')
    voucher_id = fields.Many2one('account.voucher', 'Cobro')
    check_type = fields.Selection([('current', 'Corriente'), ('to_date', 'A la fecha')], string='Tipo de cheque')
    date_issue = fields.Date('Fecha de emisión', default=fields.Date.context_today)
    date_due = fields.Date('Fecha vencimiento', default=fields.Date.context_today)
    is_beneficiary = fields.Boolean('Es beneficiario?', default=False)
    move_id = fields.Many2one('account.move', string='Asiento contable')


class LinesCreditNotes(models.Model):
    _name = 'eliterp.lines.credit.notes'

    _description = 'Lineas de nota de crédito'

    invoice_id = fields.Many2one('account.invoice', string='Nota de crédito')
    name = fields.Char('No. Factura', related="invoice_id.invoice_number")
    journal_id = fields.Many2one('account.journal', string='Diario',
                                 domain=[('type', 'in', ('bank', 'cash'))])
    date_due_invoice = fields.Date('Fecha vencimiento')
    amount_note = fields.Float('Total de nota')
    apply = fields.Boolean('Aplicar?', default=False)  # ?
    invoices_affect = fields.Many2one('eliterp.lines.invoice', string='Facturas a aplicar')
    voucher_id = fields.Many2one('account.voucher', 'Comprobante')


class LinesInvoice(models.Model):
    _name = 'eliterp.lines.invoice'

    _description = 'Líneas de Factura'

    invoice_id = fields.Many2one('account.invoice', 'Factura')
    name = fields.Char('No. Factura', related="invoice_id.invoice_number")
    journal_id = fields.Many2one('account.journal', string="Diario",
                                 domain=[('type', 'in', ('bank', 'cash'))])
    date_due_invoice = fields.Date('Fecha vencimiento')
    amount_invoice = fields.Float('Total de factura')
    amount_payable = fields.Float('Monto a cobrar/pagar')
    amount_total = fields.Float('Total adeudado')
    voucher_id = fields.Many2one('account.voucher', 'Comprobante')


class LinesAccount(models.Model):
    _name = 'eliterp.lines.account'

    _description = 'Líneas de cuenta'

    account_id = fields.Many2one('account.account', string="Cuenta", domain=[('account_type', '=', 'movement')])
    amount = fields.Float('Monto')
    voucher_id = fields.Many2one('account.voucher', string='Comprobante')


class VoucherCancelReason(models.TransientModel):
    _name = 'eliterp.voucher.cancel.reason'

    _description = 'Razón para cancelar recibo'

    description = fields.Text('Descripción', required=True, default="Anulado")

    def _remove_collection_line(self, voucher):
        """
        Reversamos movimietos contables de líneas de recaudo
        :return:
        """
        for line in voucher.lines_payment:
            move = line.move_id
            move.reverse_moves(move.date, move.journal_id or False)
            move.write({
                'state': 'cancel',
                'ref': self.description
            })
        return

    @api.multi
    def cancel_voucher(self):
        """
        Cancelamos el voucher
        """
        voucher = self.env['account.voucher'].browse(self._context['active_id'])
        if voucher.voucher_type == 'purchase':
            if voucher.reconcile:
                raise ValidationError(_("No se pueden anular egresos conciliados."))
            
            move_id = voucher.move_id
            for line in move_id.line_ids:
                if line.full_reconcile_id:
                    line.remove_move_reconcile()
            move_id.with_context(from_voucher=True, voucher_id=voucher.id).reverse_moves(voucher.date,
                                                                                         voucher.journal_id or False)

            if voucher.type_egress == 'bank':
                check = self.env['eliterp.checks'].search([('voucher_id', '=', voucher.id)])
                if check:
                    check.update({'state': 'protested'})
            pay = voucher.pay_order_id
            if voucher.line_employee_id:
                voucher.line_employee_id.update({'voucher_id': False, 'generated': False})
            else:
                pay.update({'state': 'cancel'})
            if pay.type in ['adq', 'rc']:  # TODO: Soló para RC y ADQ, no sirve
                if not voucher.line_employee_id:
                    lines = []
                    for l in pay.lines_employee:
                        lines.append(l.employee_id.id)
                    if pay.type == 'adq':
                        lines = pay.advance_payment_id.lines_advance.filtered(lambda x: x.employee_id.id in lines)
                    else:
                        lines = pay.payslip_run_id.lines_payslip_run.filtered(
                            lambda x: x.role_id.employee_id.id in lines)
            else:
                object_ = pay.invoice_id or pay.purchase_order_id or pay.payment_request_id
                object_._get_customize_amount()
            move_id.write({'state': 'cancel', 'ref': self.description + ": " + move_id.ref})
        else:
            self._remove_collection_line(voucher)
        voucher.write({'state': 'cancel', 'reason_cancel': self.description})
        return


class AccountVoucher(models.Model):
    _inherit = "account.voucher"

    @api.multi
    def name_get(self):
        res = []
        for data in self:
            if data.pay_order_id:
                res.append((data.id, "%s [%s]" % (data.name, data.pay_order_id.origin)))
            else:
                res.append((data.id, "%s" % data.name))
        return res

    @api.multi
    def print_voucher(self):
        """
        Imprimimos comprobante
        """
        self.ensure_one()
        if self.voucher_type == 'purchase':
            return self.env.ref('eliterp_treasury.eliterp_action_report_account_voucher_purchase').report_action(self)
        else:
            return self.env.ref('eliterp_treasury.eliterp_action_report_account_voucher_sale').report_action(self)

    @api.multi
    def open_voucher_cancel_reason(self):
        if self.reconcile:
            raise UserError("No se puede anular un egreso conciliado, primero anule la conciliación!")
        context = dict(self._context or {})
        if 'voucher_type' not in context:
            del context['form_view_ref']
            context['voucher_type'] = 'purchase'
            context['default_voucher_type'] = 'purchase'
            context['params']['action'] = 517
        return {
            'name': "Explique la razón",
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.voucher.cancel.reason',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context,
        }

    @api.depends('lines_payment')
    @api.multi
    def _get_total_payments(self):
        """
        Total de las líneas de cobro/pago
        :return:
        """
        for voucher in self:
            total = 0.00
            for line in voucher.lines_payment:
                total += line.amount
            voucher.total_payments = total

    @api.depends('lines_invoice_sales')
    @api.multi
    def _get_total_invoices(self):
        """
        VENTAS: Total de las líneas de factura
        """
        for voucher in self:
            total = 0.00
            for line in voucher.lines_invoice_sales:
                total += line.amount_invoice
            voucher.total_invoices = total

    def move_voucher_sale(self, name, voucher, credit, debit, account_credit, account_debit, balance):
        """
        VENTAS: Creamos movmiento para comprobante de ingreso
        :param name:
        :param voucher:
        :param credit:
        :param debit:
        :param account_credit:
        :param account_debit:
        :param balance:
        :return: object
        """
        move_id = self.env['account.move'].create({
            'journal_id': voucher.journal_id.id,
            'date': voucher.date,
            'ref': voucher.concept if self.is_advance else '/'
        })
        if not self.is_advance:
            if balance > 0:
                self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'name': name,
                    'journal_id': voucher.journal_id.id,
                    'partner_id': voucher.partner_id.id,
                    'account_id': account_debit,
                    'move_id': move_id.id,
                    'credit': balance,
                    'debit': 0.0,
                    'date': voucher.date,
                })
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': voucher.partner_id.name,
                'journal_id': voucher.journal_id.id,
                'partner_id': voucher.partner_id.id,
                'account_id': account_credit,
                'move_id': move_id.id,
                'credit': (credit - balance) if balance > 0 else credit,
                'debit': 0.0,
                'date': voucher.date,
            })
            self.env['account.move.line'].with_context(check_move_validity=True).create({
                'name': voucher.partner_id.name,
                'journal_id': voucher.journal_id.id,
                'partner_id': voucher.partner_id.id,
                'account_id': account_debit,
                'move_id': move_id.id,
                'credit': 0.0,
                'debit': debit,
                'date': voucher.date,
            })
        else:
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': voucher.partner_id.name,
                'journal_id': voucher.journal_id.id,
                'partner_id': voucher.partner_id.id,
                'account_id': account_credit,
                'move_id': move_id.id,
                'credit': balance,
                'debit': 0.0,
                'date': voucher.date,
            })
            self.env['account.move.line'].with_context(check_move_validity=True).create({
                'name': voucher.concept,
                'journal_id': voucher.journal_id.id,
                'partner_id': voucher.partner_id.id,
                'account_id': account_debit,
                'move_id': move_id.id,
                'credit': 0.0,
                'debit': balance,
                'date': voucher.date,
            })

        return move_id

    def _get_move_name(self):
        """
        COMPRAS: Obtenemos el nombre del asiento según nuevas especificaciones
        :param type:
        :param data:
        """
        string = "CE-MQ-"
        if self.type_egress in ['cash', 'credit_card']:
            year = self.date[:4]
        else:
            year = self.check_date[:4]
            code = self.bank_id.exit_code
        if self.type_egress == 'cash':
            sequence = self.env['ir.sequence'].next_by_code('account.voucher.purchase.cash')
            move_name = string + "EFC-" + year + "-" + sequence
        elif self.type_egress == 'credit_card':
            sequence = self.env['ir.sequence'].next_by_code('account.voucher.purchase.credit.card')
            move_name = string + "TAR-" + year + "-" + sequence
        else:
            move_name = string + code + "-" + year + "-" + self.bank_id.transfer_sequence_id.next_by_id()
        return move_name

    @staticmethod
    def _get_names(type_pay, move):
        """
        COMPRAS: Obtenemos el nombre del asiento y del registro
        :param type:
        :param move:
        """
        if type_pay == 'bank':
            move_name = 'Egreso/Cheque No. ' + move
        elif type_pay == 'cash':
            move_name = 'Egreso/Efectivo No. ' + move
        elif type_pay == 'credit_card':
            move_name = 'Egreso/T. Crédito No. ' + move
        else:
            move_name = 'Egreso/Transferencia No. ' + move
        return move_name

    @api.multi
    def validate_voucher(self):
        # Validar comprobante de egreso
        if self.voucher_type == 'purchase':
            for line in self.lines_account:
                if not line.amount > 0:
                    raise ValidationError("Debe eliminar las líneas con monto menor a 0")
            if not self.line_employee_id:
                self._check_pay_order_id()
            move_id = self.env['account.move'].create({
                'journal_id': self.journal_id.id,
                'date': self.date
            })
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': self.concept,
                'journal_id': self.journal_id.id,
                'partner_id': self.partner_id.id if self.type_pay in ('fap', 'oc') else False,
                'account_id': self.account_id.id,
                'move_id': move_id.id,
                'debit': 0.0,
                'credit': self.amount_cancel,
                'date': self.date
            })
            count = len(self.lines_account)
            count_ = len(self.lines_invoice_purchases)
            if count_ > 1:
                account_partner = self.lines_invoice_purchases[0].invoice_id.account_id.id
                for line in self.lines_account.filtered(lambda x: not x.account_id.id == account_partner):
                    self.env['account.move.line'].with_context(check_move_validity=False).create({
                        'name': '/',
                        'journal_id': self.journal_id.id,
                        'partner_id': False,
                        'account_id': line.account_id.id,
                        'move_id': move_id.id,
                        'credit': 0.0,
                        'debit': line.amount,
                        'date': self.date,
                        'project_id': line.project_id.id,
                        'analytic_account_id': line.account_analytic_id.id
                    })
                for line in self.lines_invoice_purchases:
                    count_ -= 1
                    if count_ == 0:
                        self.env['account.move.line'].with_context(check_move_validity=True).create({
                            'name': "Pago de factura: " + line.name,
                            'journal_id': self.journal_id.id,
                            'partner_id': self.partner_id.id,
                            'account_id': account_partner,
                            'move_id': move_id.id,
                            'credit': 0.0,
                            'debit': line.amount_payable,
                            'date': self.date,
                            'invoice_id': line.invoice_id.id
                        })
                    else:
                        self.env['account.move.line'].with_context(check_move_validity=False).create({
                            'name': "Pago de factura: " + line.name,
                            'journal_id': self.journal_id.id,
                            'partner_id': self.partner_id.id,
                            'account_id': account_partner,
                            'move_id': move_id.id,
                            'credit': 0.0,
                            'debit': line.amount_payable,
                            'date': self.date,
                            'invoice_id': line.invoice_id.id
                        })

            else:
                for line in self.lines_account:
                    count -= 1
                    if count == 0:
                        self.env['account.move.line'].with_context(check_move_validity=True).create({
                            'name': self.concept,
                            'journal_id': self.journal_id.id,
                            'partner_id': self.partner_id.id if self.type_pay in ('fap', 'oc') else False,
                            'account_id': line.account_id.id,
                            'move_id': move_id.id,
                            'credit': 0.0,
                            'debit': line.amount,
                            'date': self.date,
                            'project_id': line.project_id.id,
                            'analytic_account_id': line.account_analytic_id.id
                        })
                    else:
                        self.env['account.move.line'].with_context(check_move_validity=False).create({
                            'name': self.concept,
                            'journal_id': self.journal_id.id,
                            'partner_id': self.partner_id.id if self.type_pay in ('fap', 'oc') else False,
                            'account_id': line.account_id.id,
                            'move_id': move_id.id,
                            'credit': 0.0,
                            'debit': line.amount,
                            'date': self.date,
                            'project_id': line.project_id.id,
                            'analytic_account_id': line.account_analytic_id.id
                        })
            # Factura
            if self.type_pay == 'fap':
                account = self.lines_invoice_purchases[0].invoice_id.account_id
                # Notas de crédito
                for line_note_credit in self.lines_note_credit:
                    line_move_invoice = line_note_credit.invoices_affect.invoice_id.move_id.line_ids.filtered(
                        lambda x: x.account_id == account)
                    line_move_note_credit = line_note_credit.invoice_id.move_id.line_ids.filtered(
                        lambda x: x.account_id == account)
                    (line_move_invoice + line_move_note_credit).reconcile()
                if len(self.lines_invoice_purchases) > 1:
                    for line_invoice in self.lines_invoice_purchases:
                        line_move_voucher = move_id.line_ids.filtered(
                            lambda x: x.account_id == account and x.invoice_id.id == line_invoice.invoice_id.id)
                        line_move_invoice = line_invoice.invoice_id.move_id.line_ids.filtered(
                            lambda x: x.account_id == account)
                        (line_move_invoice + line_move_voucher).reconcile()

                else:
                    line_move_voucher = move_id.line_ids.filtered(lambda x: x.account_id == account)
                    for line_invoice in self.lines_invoice_purchases:
                        line_move_invoice = line_invoice.invoice_id.move_id.line_ids.filtered(
                            lambda x: x.account_id == account)
                        (line_move_invoice + line_move_voucher).reconcile()
            # Caja chica
            if self.type_pay == 'cajc':
                for line in self.custodian_id.replacement_small_box_id.lines_voucher:
                    if line.check_reposition:
                        line.update({'state_reposition': 'paid'})
                self.custodian_id.replacement_small_box_id.update({'replacement_date': self.date})
            new_name = self._get_move_name()
            move_id.with_context(eliterp_moves=True, move_name=new_name).post()
            if self.type_egress == 'bank':
                reference = self.check_number
            else:
                reference = new_name[15:]
            move_name = self._get_names(self.type_egress, reference)
            move_id.write({'ref': move_name})
            # OC
            if self.type_pay == 'oc':
                pass
                # self.movement_voucher()  Generamos Asiento diario por anticipo
            if not self.pay_order_id.type_egress == 'bank' or self.pay_order_id.general_check:
                self.pay_order_id.update(
                    {'state': 'paid'})  # Cambiamos estado de la OP para todos menos para cheques de Nóminas
            if not self.line_employee_id:
                self.pay_order_id.update({'voucher_id': self.id})
            else:
                self.line_employee_id.update({'voucher_id': self.id})
            if self.type_egress == 'bank':  # Soló con cheques y generamos el consecutivo
                if self.bank_id.check_sequence_id:
                    self.bank_id.check_sequence_id.next_by_id()
                self._check_check_number()  # Verificamos cheque
                self.env['eliterp.checks'].create({
                    'partner_id': self.partner_id.id if self.partner_id else False,
                    'name': self.check_number,
                    'recipient': self.beneficiary,
                    'type': 'issued',
                    'date': self.date,
                    'check_date': self.check_date,
                    'bank_id': self.bank_id.id,
                    'check_type': 'current',
                    'state': 'issued',
                    'amount': self.amount_cancel,
                    'voucher_id': self.id
                })
            return self.write({
                'state': 'posted',
                'name': new_name,
                'move_id': move_id.id
            })
        # Validar comprobante de ingreso
        else:
            voucher_moves = []
            voucher = self
            balance = self.total_payments - self.total_invoices
            # Verificamos en líneas de cobro por tipo
            if not self.lines_invoice_sales and not self.is_advance:
                raise UserError("Debe marcar cómo anticipo si no tiene líneas de facturas.")
            if len(self.lines_payment) > 1 and not self.is_advance:
                raise UserError("No puede tener dos líneas de recaudación para cobro de facturas.")
            for payment in self.lines_payment:
                # Banco
                if payment.type_payment == 'bank':
                    # Creamos cheque del cobro
                    self.env['eliterp.checks'].create({
                        'partner_id': self.partner_id.id,
                        'name': payment.check_number,
                        'recipient': payment.drawer,
                        'type': 'receipts',
                        'date': payment.date_issue,
                        'check_date': payment.date_due,
                        'bank_id': payment.bank_id.id,
                        'bank_account': payment.account_number,
                        'account_id': payment.account_id.id,
                        'check_type': payment.check_type,
                        'state': 'received',
                        'amount': payment.amount,
                        'voucher_id': self.id
                    })
                    move_id = self.move_voucher_sale(
                        self.concept,
                        voucher,
                        payment.amount,
                        payment.amount,
                        self.partner_id.property_account_receivable_id.id,
                        payment.account_id.id,
                        balance,
                    )
                    move_id.with_context(eliterp_moves=True, internal_voucher=True).post()
                    payment.write({'move_id': move_id.id})
                    if not self.is_advance:
                        line_move_bank = move_id.line_ids.filtered(
                            lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                        for line in self.lines_invoice_sales:
                            line_move_invoice = line.invoice_id.move_id.line_ids.filtered(
                                lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                            (line_move_bank + line_move_invoice).reconcile()
                            voucher_moves.append(move_id)
                # Efectivo y depósito
                if payment.type_payment in ['cash', 'deposit']:
                    move_id = self.move_voucher_sale(
                        self.concept,
                        voucher,
                        payment.amount,
                        payment.amount,
                        self.partner_id.property_account_receivable_id.id,
                        payment.account_id.id,
                        balance,
                    )
                    move_id.with_context(eliterp_moves=True, internal_voucher=True).post()
                    payment.write({'move_id': move_id.id})
                    if not self.is_advance:
                        line_move_cash = move_id.line_ids.filtered(
                            lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                        for line in self.lines_invoice_sales:
                            line_move_invoice = line.invoice_id.move_id.line_ids.filtered(
                                lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                            (line_move_cash + line_move_invoice).reconcile()
                            voucher_moves.append(move_id)
                # Transferencia
                if payment.type_payment == 'transfer':
                    move_id = self.move_voucher_sale(
                        self.concept,
                        voucher,
                        payment.amount,
                        payment.amount,
                        self.partner_id.property_account_receivable_id.id,
                        payment.account_id.id,
                        balance,
                    )
                    move_id.with_context(eliterp_moves=True, internal_voucher=True).post()
                    payment.write({'move_id': move_id.id})
                    if not self.is_advance:
                        line_move_transfer = move_id.line_ids.filtered(
                            lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                        for line in self.lines_invoice_sales:
                            line_move_invoice = line.invoice_id.move_id.line_ids.filtered(
                                lambda x: x.account_id == self.partner_id.property_account_receivable_id)
                            (line_move_transfer + line_move_invoice).reconcile()
                        voucher_moves.append(move_id)
            new_name = self.journal_id.sequence_id.next_by_id()
            for move in voucher_moves:
                move.write({'ref': new_name})
            return self.write({
                'state': 'posted',
                'name': new_name,
                'move_id': move_id.id
            })

    def apply_amount(self):
        """
        Aplicamos la suma de las líneas de cuenta
        """
        self.amount_cancel = sum(line.amount for line in self.lines_account)

    def load_amount(self):
        journal_id = self.env['account.journal'].search(
            [('name', '=', 'Efectivo')]).id  # El diario del pago/cobro siempre en efectivo
        # Cargar montos de comprobante de ingreso
        if self.voucher_type == 'sale':
            if not self.lines_invoice_sales:
                raise UserError("Necesita cargar líneas de factura")
            if not self.lines_payment:
                raise UserError("No tiene ninguna líneas de tipo de pago")
            else:
                total = 0.00
                for payment in self.lines_payment:
                    total += payment.amount
            for invoice in self.lines_invoice_sales:
                if total == 0.00:
                    continue
                if invoice.amount_total <= total:
                    invoice.update({
                        'amount_payable': invoice.amount_total,
                        'journal_id': journal_id
                    })
                    total = total - invoice.amount_total
                else:
                    invoice.update({
                        'amount_payable': total,
                        'journal_id': journal_id
                    })
                    total = 0.00
        else:  # Soló cargamos el Diario
            if len(self.lines_invoice_purchases) > 1:
                total = self.amount_cancel
                for invoice in self.lines_invoice_sales:
                    if total == 0.00:
                        continue
                    if invoice.amount_total <= total:
                        invoice.update({
                            'amount_payable': invoice.amount_total,
                            'journal_id': journal_id
                        })
                        total = total - invoice.amount_total
                    else:
                        invoice.update({
                            'amount_payable': total,
                            'journal_id': journal_id
                        })
                        total = 0.00
            else:
                for invoice in self.lines_invoice_purchases:
                    invoice.update({'journal_id': journal_id})

        return

    def apply_notes(self):
        """
        Aplicamos notas de crédito en facturas seleccionadas
        """
        for line in self.lines_note_credit:
            line_invoice = self.lines_invoice_purchases.filtered(lambda x: x.id == line.invoices_affect.id)
            line_invoice.write({'amount_total': line_invoice.amount_total + line.amount_note})
        return True

    def load_data(self):
        """
        Cargamos la información necesaria (Soló para ventas)
        """
        if not self.partner_id:
            if self.voucher_type == 'sale':
                raise UserError("Necesita seleccionar al Cliente.")
        else:
            if self.voucher_type == 'sale':
                self.lines_invoice_sales.unlink()  # Limpiamos líneas anteriores
                invoices_list = self.env['account.invoice'].search([
                    ('partner_id', '=', self.partner_id.id), ('state', '=', 'open'),
                    ('type', '=', 'out_invoice')
                ])
            else:
                # Cargamos factura de proveedor
                invoices_list = self.invoice_id | self.pay_order_id.invoice_ids
                # TODO: Cargamos notas de crédito
                notes_list = self.env['account.invoice'].search([
                    ('partner_id', '=', self.partner_id.id),
                    ('state', '=', 'open'),
                    ('type', '=', 'in_refund')
                ])
            list_invoices = []
            total = self.amount_cancel
            for invoice in invoices_list.sorted(key=lambda r: r.residual):
                list_invoices.append([0, 0, {
                    'invoice_id': invoice.id,
                    'amount_invoice': invoice.amount_total,
                    'amount_total': invoice.residual,
                    'amount_payable': 0 if len(invoices_list) > 1 else total
                }])
            list_notes = []
            if self.voucher_type == 'purchase':
                self.lines_note_credit.unlink()
                if notes_list:
                    list_notes = []
                    for note in notes_list:
                        list_notes.append([0, 0, {
                            'invoice_id': note.id,
                            'date_due_invoice': note.date_due,
                            'amount_note': -1 * note.amount_total
                        }])
                return self.update({
                    'lines_invoice_purchases': list_invoices,
                    'lines_note_credit': list_notes
                })
            return self.update({'lines_invoice_sales': list_invoices})

    @api.multi
    def unlink(self):
        for voucher in self:
            if voucher.state != 'draft':
                raise ValidationError('No se puede eliminar comprobantes distintos de borrador.')
        return super(AccountVoucher, self).unlink()

    @api.onchange('partner_id', 'pay_now')
    def _onchange_partner_id(self):
        """
        MM: Para que sirve esto?
        """
        if self.pay_now == 'pay_now':
            liq_journal = self.env['account.journal'].search([('type', 'in', ('bank', 'cash'))], limit=1)
            self.account_id = liq_journal.default_debit_account_id \
                if self.voucher_type == 'sale' else liq_journal.default_credit_account_id
        else:
            if self.partner_id:
                if self.voucher_type == 'sale':
                    self.account_id = self.partner_id.property_account_receivable_id
            else:
                self.account_id = self.journal_id.default_debit_account_id \
                    if self.voucher_type == 'sale' else self.journal_id.default_credit_account_id

    @api.model
    def _default_journal(self):
        """
        Método modificado: Obtenemos nuevo diario por defecto
        """
        if self._context['voucher_type'] == 'sale':
            return self.env['account.journal'].search([('name', '=', 'Comprobante de ingreso')])[0].id
        else:
            return self.env['account.journal'].search([('name', '=', 'Comprobante de egreso')])[0].id

    @api.onchange('balance_account')
    def _onchange_balance_account(self):
        """
        Al cambiar la cuenta saldo si es diferente de 0 la mostramos
        """
        if len(self.balance_account) != 0:
            self.show_account = True

    @api.onchange('bank_id', 'type_egress')
    def _onchange_bank_id(self):
        """
        Número del siguiente cheque según secuencia, caso contrario colocamos en falso
        """
        if self.type_egress == 'credit_card':  # Colocamos cuenta por defecto en TC
            account = self.env['account.account'].search([('code', '=', '2.1.2.4')])[0]
            self.account_id = account if account else False
        if self.bank_id:
            self.account_id = self.bank_id.account_id
            if not self.type_egress == 'bank':
                self.check_number = False
            else:
                number = str(self.bank_id.check_next_number).zfill(self.bank_id.padding)
                self.check_number = number or False
        else:
            self.check_number = False

    @api.onchange('check_number')
    def onchange_check_number(self):
        """
        Rellenamos con 0 el número de cheque
        """
        if self.check_number:
            number = self.bank_id.padding
            self.check_number = self.check_number.zfill(number)

    def _check_check_number(self):
        """
        Validamos número sea correcto y no exista otro igual (Cualquier estado)
        """
        if self.check_number:
            # TODO: Revisar
            if int(self.check_number) < int(self.bank_id.start):
                raise ValidationError(
                    "Cheque %s menor al configurado en banco (%s)." % (self.check_number, self.bank_id.start))
            check = self.env['eliterp.checks'].search([
                ('bank_id', '=', self.bank_id.id),
                ('name', '=', self.check_number)
            ])
            if check:
                raise ValidationError("Ya existe un cheque "
                                      "registrado para el banco %s con ese número (%s)." % (
                                          self.bank_id.name, self.check_number))

    def load_small_box(self):
        """
        Cargamos montos de caja chica
        """
        if self.custodian_id.replacement_small_box_id.state == 'liquidated':
            line = []
            line.append([0, 0, {'amount': self.custodian_id.replacement_small_box_id.total_vouchers,
                                'account_id': self.custodian_id.account_id.id}])
            self.update({'lines_account': line})
        else:
            return True

    def load_viaticum(self):
        """
        Cargamos datos de viáticos
        """
        line = []
        line.append([0, 0, {'amount': self.amount_cancel,
                            'account_analytic_id': self.viaticum_id.account_analytic_id,
                            'project_id': self.viaticum_id.project_id}])
        self.update({'lines_account': line})

    @api.onchange('pay_order_id')
    def _onchange_pay_order_id(self):
        """
        Al cambiar la OP
        """
        if self.invoice_id:
            self.beneficiary = self.invoice_id.partner_id.name
            self.partner_id = self.invoice_id.partner_id.id
            self.load_data()
            self.load_amount()  # Soló para el diario
        if self.pay_order_id.invoice_ids:
            self.beneficiary = self.pay_order_id.invoice_ids[0].partner_id.name
            self.partner_id = self.pay_order_id.invoice_ids[0].partner_id.id
            self.load_data()
            self.load_amount()  # Soló para el diario
        if self.purchase_order_id:
            self.beneficiary = self.purchase_order_id.partner_id.name
            self.partner_id = self.purchase_order_id.partner_id.id
        if self.custodian_id:
            self.beneficiary = self.custodian_id.name
            self.load_small_box()
        if self.payment_request_id:
            self.beneficiary = self.payment_request_id.beneficiary
        if self.viaticum_id:
            self.beneficiary = self.viaticum_id.beneficiary.name
            self.load_viaticum()

    @api.multi
    def movement_voucher(self):
        """
        Generamos asiento de cuadre para proveedor
        """
        journal = self.env['account.journal'].search(
            [('name', '=', 'Anticipos de proveedor')]).id
        date = fields.Date.to_string(datetime.today().date())
        move_id = self.env['account.move'].create({'journal_id': journal,
                                                   'date': date,
                                                   })
        self.env['account.move.line'].with_context(check_move_validity=False).create({
            'name': self.concept,
            'journal_id': journal,
            'partner_id': self.partner_id.id,
            'account_id': self.partner_id.property_account_advance_id.id,
            'move_id': move_id.id,
            'debit': 0.0,
            'credit': self.amount_cancel,
            'date': date
        })
        self.env['account.move.line'].with_context(check_move_validity=True).create({
            'name': self.concept,
            'journal_id': journal,
            'partner_id': self.partner_id.id,
            'account_id': self.partner_id.property_account_payable_id.id,
            'move_id': move_id.id,
            'debit': self.amount_cancel,
            'credit': 0.00,
            'date': date,
            'is_advanced': True
        })
        move_id.post()
        move_id.write({'ref': 'De: %s' % self.purchase_order_id.name})

    lines_invoice_purchases = fields.One2many('eliterp.lines.invoice', 'voucher_id',
                                              string='Líneas de factura en compras')
    lines_note_credit = fields.One2many('eliterp.lines.credit.notes', 'voucher_id',
                                        string='Líneas de nota de crédito')
    lines_account = fields.One2many('eliterp.lines.account', 'voucher_id', string='Líneas de cuenta', readonly=True,
                                    states={'draft': [('readonly', False)]})
    # CM
    journal_id = fields.Many2one('account.journal', 'Journal',
                                 required=True, readonly=True, states={'draft': [('readonly', False)]},
                                 default=_default_journal)

    type_egress = fields.Selection([
        ('cash', 'Efectivo'),
        ('bank', 'Cheque'),
        ('transfer', 'Transferencia'),
        ('credit_card', 'Tarjeta de crédito')
    ], string='Forma de pago', default='cash', required=True, track_visibility='onchange', readonly=True,
        states={'draft': [('readonly', False)]})
    beneficiary = fields.Char('Beneficiario', readonly=True, states={'draft': [('readonly', False)]},
                              track_visibility='onchange')
    check_date = fields.Date('Fecha Che./Tra.', readonly=True, states={'draft': [('readonly', False)]},
                             track_visibility='onchange')
    bank_id = fields.Many2one('res.bank', string="Banco", readonly=True, states={'draft': [('readonly', False)]},
                              track_visibility='onchange')
    amount_cancel = fields.Float('Monto a cancelar', readonly=True, states={'draft': [('readonly', False)]},
                                 track_visibility='onchange')
    total_payments = fields.Monetary('Total de cobros', compute='_get_total_payments', track_visibility='onchange')
    total_invoices = fields.Monetary('Total facturas', compute='_get_total_invoices')
    # CM
    account_id = fields.Many2one('account.account', string='Cuenta',
                                 domain=[('deprecated', '=', False), ('account_type', '=', 'movement')], required=False)
    concept = fields.Char('Concepto', required=True, readonly=True, states={'draft': [('readonly', False)]})
    balance = fields.Float('Saldo')
    # Factura
    invoice_id = fields.Many2one('account.invoice', 'Factura')
    # OC
    purchase_order_id = fields.Many2one('purchase.order', 'Orden de compra')
    # Caja chica
    custodian_id = fields.Many2one('eliterp.custodian.small.box', 'Custodio caja chica')
    # Viático
    viaticum_id = fields.Many2one('eliterp.travel.allowance.request', string="Solicitud viático")
    expenses_pay = fields.Many2one('account.account', string="Cuenta contable")  # TODO: Cuenta de viáticos
    # Requerimiento de pago
    payment_request_id = fields.Many2one('eliterp.payment.request', string="Requerimiento de pago")
    liquidation_settlement_id = fields.Many2one('eliterp.liquidation.settlement', "Liquidación de viático")
    # Orden de pago
    pay_order_id = fields.Many2one('eliterp.pay.order', string='Orden de pago', readonly=True,
                                   domain=[('type', 'in', ('adq', 'rc'))],
                                   states={'draft': [('readonly', False)]})
    movement = fields.Boolean('Cruce?', default=False)
    type_pay = fields.Selection(related='pay_order_id.type', string="Tipo", store=True)
    # Comprobantes de ventas
    lines_invoice_sales = fields.One2many('eliterp.lines.invoice', 'voucher_id',
                                          string='Líneas de factura en ventas')
    lines_payment = fields.One2many('eliterp.lines.payment', 'voucher_id', string='Líneas de cobro')
    flag = fields.Boolean('Ya no hay saldo?', default=False)
    show_account = fields.Boolean('Se muestra la cuenta?', default=False)
    balance_account = fields.Many2one('account.account', string="Cuenta saldo",
                                      domain=[('account_type', '=', 'movement')])
    is_advance = fields.Boolean('Es anticipo?', default=False, readonly=True, states={'draft': [('readonly', False)]})

    def _check_pay_order_id(self):
        new_object = self.search([
            ('pay_order_id', '=', self.pay_order_id.id),
            ('state', '=', 'posted')
        ])
        if new_object:
            raise ValidationError("Ya existe una Orden de pago contabilizada de la misma.")
        else:
            return

    line_employee_id = fields.Many2one('eliterp.list.employees.order', 'Línea de orden')

    transfer_code = fields.Char('Código de transferencia')
    _sql_constraints = [
        ('transfer_code_uniq', 'unique (bank_id, transfer_code, state)',
         'El Código de transferencia debe ser única por banco.')
    ]
