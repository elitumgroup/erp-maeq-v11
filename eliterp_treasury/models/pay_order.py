# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models, _
from odoo.tools import float_is_zero
import json
import base64
from odoo.exceptions import ValidationError, UserError
from io import StringIO
import csv


class PayWizard(models.TransientModel):
    _name = 'eliterp.pay.wizard'

    _description = 'Ventana para generar pago'

    @api.one
    @api.constrains('amount')
    def _check_amount(self):
        """
        Verificamos el monto
        """
        if self.amount > self.default_amount:
            raise ValidationError(
                "Monto mayor al del total del saldo del documento.")

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        """
        Al cambiar el tipo de pago actualizamos monto
        """
        if self.payment_type == 'total':
            self.amount = self.default_amount

    @api.multi
    def confirm_payment(self):
        """
        Generamos OP
        """
        object_pay_order = self.env['eliterp.pay.order']
        name = self.env['ir.sequence'].next_by_code('pay.order')
        vals = {
            'name': name,
            'amount': self.amount,
            'type': self.type,
            'date': self.date,
            'type_egress': self.type_egress,
            'bank_id': self.bank_id.id,
            'comment': self.comment,
            'project_id': self.project_id.id if self.project_id else False
        }
        # Dependiendo del modelo activo
        if self._context['active_model'] == 'account.invoice':
            inv = self.env['account.invoice'].browse(self._context['active_id'])
            vals.update({
                'origin': inv.number,
                'invoice_id': inv.id,
                'beneficiary': inv.partner_id.name
            })
        if self._context['active_model'] == 'purchase.order':
            po = self.env['purchase.order'].browse(self._context['active_id'])
            vals.update({
                'origin': po.name,
                'purchase_order_id': po.id,
                'beneficiary': po.partner_id.name
            })
        if self._context['active_model'] == 'eliterp.advance.payment':
            adq = self.env['eliterp.advance.payment'].browse(self._context['active_id'])
            # Colocamos los seleccionados en bandera True
            employees = []
            for line in adq.lines_advance:
                if line.selected and not line.flag:
                    employees.append([0, 0, {'employee_id': line.employee_id.id,
                                             'amount': line.amount_payable,
                                             'pay_order_line_id': line.id,
                                             'is_check': True if self.type_egress == 'bank' else False}])
                    line.update({'selected': False, 'amount_payable': 0})  # Le quitamos la selección
            vals.update({
                'origin': adq.name,
                'advance_payment_id': adq.id,
                'general_check': False if self.type_egress == 'bank' else True,
                'lines_employee': employees
            })
            adq.update({'select_all': False})
        if self._context['active_model'] == 'hr.payslip.run':
            rc = self.env['hr.payslip.run'].browse(self._context['active_id'])
            # Colocamos los seleccionados en bandera True
            employees = []
            for line in rc.lines_payslip_run:
                if line.selected and not line.flag:
                    employees.append([0, 0, {'employee_id': line.role_id.employee_id.id,
                                             'amount': line.amount_payable,
                                             'pay_order_line_id_rc': line.id,
                                             'is_check': True if self.type_egress == 'bank' else False}])
                    line.update({'selected': False, 'amount_payable': 0})
            vals.update({
                'origin': rc.move_id.name,
                'payslip_run_id': rc.id,
                'general_check': False if self.type_egress == 'bank' else True,
                'lines_employee': employees
            })
            rc.update({'select_all': False})
        if self._context['active_model'] == 'eliterp.replacement.small.box':
            cajc = self.env['eliterp.replacement.small.box'].browse(self._context['active_id'])
            vals.update({
                'origin': cajc.name,
                'replacement_small_box_id': cajc.id
            })
        if self._context['active_model'] == 'eliterp.payment.request':
            pr = self.env['eliterp.payment.request'].browse(self._context['active_id'])
            vals.update({
                'origin': pr.name,
                'payment_request_id': pr.id,
                'beneficiary': pr.beneficiary
            })
        if self._context['active_model'] == 'eliterp.travel.allowance.request':
            svi = self.env['eliterp.travel.allowance.request'].browse(self._context['active_id'])
            vals.update({
                'origin': svi.name,
                'viaticum_id': svi.id
            })
        # Liquidación de viáticos
        if self._context['active_model'] == 'eliterp.liquidation.settlement':
            lvi = self.env['eliterp.liquidation.settlement'].browse(self._context['active_id'])
            vals.update({
                'origin': lvi.name,
                'liquidation_settlement_id': lvi.id
            })
        object_pay_order.create(vals)

    date = fields.Date('Fecha programada', default=fields.Date.context_today, required=True)
    payment_type = fields.Selection([('total', 'Total'), ('partial', 'Parcial')],
                                    string="Tipo de pago", required=True, default='total')
    type = fields.Char('Tipo')  # Selección para ver el tipo
    amount = fields.Float('Monto', required=True)
    default_amount = fields.Float('Monto ficticio')
    default_date = fields.Date('Fecha ficticia')
    type_egress = fields.Selection([
        ('bank', 'Cheque'),
        ('payment_various', 'Pagos varios'),
        ('transfer', 'Transferencia')
    ], string='Forma de pago', required=True, default='bank')
    bank_id = fields.Many2one('res.bank', string="Banco")
    comment = fields.Text('Notas y comentarios')


class AccountVoucher(models.Model):
    _inherit = 'account.voucher'

    @api.multi
    def print_sat(self):
        """
        Generamos archivo para banco
        \t TAB
        \r\n ENTER
        """
        content = ""
        order = self.pay_order_id
        employees = order.lines_employee.sorted(key=lambda x: x.employee_id.name)
        if self.bank_id.name == 'Banco Bolivariano 0005285XXX':
            count = 1
            name = 'MAEQ_%s%s%s_1221.biz' % (self.check_date[:4], self.check_date[5:7], self.check_date[8:])
            for line in employees:
                content += "BZDET%s%s\t\tC%s\t\t%s\t\t%s001%s04%s\t\t1%s%s\t\t%s\t\tRPA\t\t07685007685\r\n" % (
                    str(count).zfill(6), line.employee_id.identification_id,
                    line.employee_id.identification_id,
                    line.employee_id.name,
                    'COB' if line.employee_id.bank_id.code != '34' else 'CUE', line.employee_id.bank_id.code,
                    line.employee_id.bank_account,
                    ("{0:.2f}".format(line.amount).replace('.', '')).zfill(15), self.concept,
                    ''.zfill(65),
                )
                count += 1
            return self.write({
                'sat_filename': name,
                'sat_binary': base64.b64encode(bytes(content, 'utf-8'))
            })
        elif self.bank_id.name == 'Banco Pichincha 2100164XXX':
            file = StringIO()
            name = 'MAEQ_%s.csv' % self.concept
            writer = csv.writer(file, delimiter=';')
            for line in employees:
                row = []
                row.append("PA")
                row.append(line.employee_id.identification_id)
                row.append(order.currency_id.name)
                row.append("{0:.2f}".format(line.amount).replace('.', ''))
                row.append("CTA")
                row.append("AHO")
                row.append(line.employee_id.bank_account)
                row.append(self.concept)
                row.append("C")
                row.append(line.employee_id.identification_id)
                row.append(line.employee_id.name)
                row.append(line.employee_id.bank_id.code)
                writer.writerow(row)
            return self.write({
                'sat_filename': name,
                'sat_binary': base64.b64encode(bytes(file.getvalue(), 'latin-1'))
            })
        else:
            return

    @api.multi
    @api.returns('self')
    def _voucher(self, record):
        """
        Creamos un nuevo voucher a partir de OP o Empleados por cheque
        :param record:
        :return: self
        """
        values = {}
        if record._name == 'eliterp.pay.order':
            if float_is_zero(record.amount, precision_rounding=record.currency_id.rounding):
                return
            values['voucher_type'] = 'purchase'
            values['pay_order_id'] = record.id
            values['type_egress'] = record.type_egress if record.type_egress != 'payment_various' else 'cash'
            values['bank_id'] = record.bank_id.id if record.bank_id else False
            values['check_date'] = record.date if record.type_egress != 'payment_various' else False

            if record.type_egress == 'bank':
                sequence = record.bank_id.check_sequence_id.number_next_actual
                values['check_number'] = str(sequence).zfill(record.bank_id.padding)
            amount = record.amount - sum(l.amount if l.voucher_id else 0.00 for l in record.lines_employee)
            values['amount_cancel'] = amount
            lines_account = []
            # Factura
            if record.type == 'fap':
                invoice = record.invoice_id or record.invoice_ids[0]
                # Líneas de cuentas
                lines_account.append([0, 0, {'account_id': invoice.account_id.id,
                                             'amount': amount,
                                             'project_id': record.project_id.id if record.project_id else False,
                                             'account_analytic_id': invoice.account_analytic_id.id if invoice.account_analytic_id else False,
                                             }])
                values['lines_account'] = lines_account
                if record.invoice_ids:
                    concept = ', '.join(
                        i.establishment + "-" + i.emission_point + "-" + i.reference for i in
                        record.invoice_ids)
                    values['concept'] = 'Pago de facturas: ' + concept
                else:
                    m = ''
                    if invoice.is_sale_note:
                        m = "Pago de nota de venta "
                    else:
                        m = "Pago de factura "
                    values['invoice_id'] = invoice.id
                    values['concept'] = m + "No. " + '%s-%s-%s' % (
                        invoice.establishment, invoice.emission_point, invoice.reference)
            # OC
            if record.type == 'oc':
                oc = record.purchase_order_id
                values['purchase_order_id'] = oc.id
                values['concept'] = 'Orden de compra %s' % oc.name
                lines_account.append([0, 0, {
                    'account_id': oc.partner_id.property_account_payable_id.id,
                    'amount': amount,
                    'project_id': record.project_id.id if record.project_id else False,
                    'account_analytic_id': oc.account_analytic_id.id if oc.account_analytic_id else False,
                }])
                values['lines_account'] = lines_account
            # ADQ
            if record.type == 'adq':
                adq = record.advance_payment_id
                account = adq.journal_id.default_credit_account_id.id
                # Líneas de cuentas
                lines_account = []
                lines_account.append([0, 0, {'account_id': account,
                                             'amount': amount,
                                             'project_id': record.project_id.id if record.project_id else False
                                             }])
                values['lines_account'] = lines_account
                values['concept'] = 'ADQ del mes de %s' % adq.period
            # RC
            if record.type == 'rc':
                rc = record.payslip_run_id
                account = self.env['account.account'].search([('name', '=', 'NÓMINA POR PAGAR')], limit=1)
                # Líneas de cuentas
                lines_account = []
                lines_account.append([0, 0, {'account_id': account.id,
                                             'amount': amount,
                                             'project_id': record.project_id.id if record.project_id else False
                                             }])
                values['lines_account'] = lines_account
                values['concept'] = 'Nómina de empleados %s' % rc.name
            # Caja chica
            if record.type == 'cajc':
                cjc = record.replacement_small_box_id.custodian_id
                values['custodian_id'] = cjc.id
                values['concept'] = 'Reposición de caja %s' % record.replacement_small_box_id.name
            # RP
            if record.type == 'rp':
                rp = record.payment_request_id
                values['payment_request_id'] = rp.id
                values['concept'] = rp.comments or '/'
                lines_account.append([0, 0, {
                    'amount': amount,
                    'project_id': record.project_id.id if record.project_id else False
                }])
                values['lines_account'] = lines_account
            # SV
            if record.type == 'svi':
                svi = record.viaticum_id
                values['viaticum_id'] = svi.id
                values['concept'] = svi.reason or '/'
            # LV
            if record.type == 'lvi':
                lvi = record.liquidation_settlement_id
                values['liquidation_settlement_id'] = lvi.id
                values['beneficiary'] = lvi.beneficiary.name
                values['concept'] = "Liquidación de viático por: " + (lvi.comment or '/')
                lines_account.append([0, 0, {
                    'account_id': self.env.ref('eliterp_accounting.1_eliterp_account_2163').id,
                    'amount': amount,
                    'project_id': record.project_id.id if record.project_id else False,
                    'account_analytic_id': lvi.account_analytic_id.id if lvi.account_analytic_id else False
                }])
                values['lines_account'] = lines_account
        else:
            values['date'] = record.pay_order_id.date
            values['voucher_type'] = 'purchase'
            values['pay_order_id'] = record.pay_order_id.id
            values['amount_cancel'] = record.amount
            values['type_egress'] = record.pay_order_id.type_egress
            values['bank_id'] = record.pay_order_id.bank_id.id
            sequence = record.pay_order_id.check_sequence_id.number_next_actual
            values['check_number'] = str(sequence).zfill(record.pay_order_id.bank_id.padding)
            values['beneficiary'] = record.employee_id.name
            values['line_employee_id'] = record.id
            if record.pay_order_id.type == 'adq':
                adq = record.pay_order_id.advance_payment_id
                account = adq.journal_id.default_credit_account_id.id
                # Líneas de cuentas
                lines_account = []
                lines_account.append([0, 0, {'account_id': account,
                                             'amount': record.amount,
                                             'project_id': record.pay_order_id.project_id.id if record.pay_order_id.project_id else False
                                             }])
                values['lines_account'] = lines_account
                values['concept'] = 'ADQ %s %s' % (record.employee_id.name, adq.period)
            else:
                rc = record.pay_order_id.payslip_run_id
                account = self.env['account.account'].search([('name', '=', 'NÓMINA POR PAGAR')], limit=1)
                # Líneas de cuentas
                lines_account = []
                lines_account.append([0, 0, {'account_id': account.id,
                                             'amount': record.amount,
                                             'project_id': record.pay_order_id.project_id.id if record.pay_order_id.project_id else False
                                             }])
                values['lines_account'] = lines_account
                values['concept'] = 'FDM %s de %s' % (record.employee_id.name, rc.name)
        voucher_invoice = self.create(values)
        if 'bank_id' in values:
            voucher_invoice._onchange_bank_id()  # Para colocar cuenta de banco
        voucher_invoice._onchange_pay_order_id()  # Cambiamos
        return voucher_invoice

    sat_filename = fields.Char('Nombre de archivo')
    sat_binary = fields.Binary('Archivo', readonly=True)


class ListEmployeesOrder(models.Model):
    _name = 'eliterp.list.employees.order'

    _description = 'Lista de empleados orden de pago'

    @api.multi
    def generate_check(self):
        """
        Creamos cheque de empleado
        """
        self.ensure_one()
        new_voucher = self.env['account.voucher'].with_context({'voucher_type': 'purchase'})._voucher(self)
        action = self.env.ref('eliterp_treasury.eliterp_action_voucher_purchase')
        result = action.read()[0]
        res = self.env.ref('eliterp_treasury.eliterp_view_form_voucher_purchase', False)
        result['views'] = [(res and res.id or False, 'form')]
        result['res_id'] = new_voucher.id
        return result

    voucher_id = fields.Many2one('account.voucher', 'Comprobante')
    generated = fields.Boolean('Generado?', default=False)
    employee_id = fields.Many2one('hr.employee', 'Nombre de empleado')
    amount = fields.Float('Monto')
    pay_order_id = fields.Many2one('eliterp.pay.order', 'Orden de pago', ondelete="cascade")
    is_check = fields.Boolean('Es cheque?')
    pay_order_line_id = fields.Many2one('eliterp.lines.advance.payment', 'Línea de empleado', ondelete="cascade",
                                        index=True,
                                        readonly=True)
    pay_order_line_id_rc = fields.Many2one('eliterp.lines.payslip.run', 'Línea de rol', ondelete="cascade",
                                           index=True,
                                           readonly=True)


class PayOrder(models.Model):
    _name = 'eliterp.pay.order'
    _inherit = ['mail.thread']
    _description = 'Orden de pago'

    @api.multi
    def pay(self):
        """
        Creamos pago
        """
        new_voucher = self.env['account.voucher'].with_context({'voucher_type': 'purchase'})._voucher(self)
        action = self.env.ref('eliterp_treasury.eliterp_action_voucher_purchase')
        result = action.read()[0]
        res = self.env.ref('eliterp_treasury.eliterp_view_form_voucher_purchase', False)
        result['views'] = [(res and res.id or False, 'form')]
        result['res_id'] = new_voucher.id
        return result

    def _default_currency(self):
        """
        Moneda
        """
        return self.env['res.currency'].search([('name', '=', 'USD')])[0].id

    @api.multi
    def unlink(self):
        # base64.b64encode(bytes(content, 'utf-8'))
        voucher_object = self.env['account.voucher']
        for pay in self:
            if voucher_object.search([('pay_order_id', '=', pay.id), ('state', '!=', 'draft')]):
                raise ValidationError('No se puede eliminar una OP con un pago contabilizado o anulada.')
        return super(PayOrder, self).unlink()

    @api.onchange('general_check')
    def _onchange_general_check(self):
        """
        Al cambiar cheque general si es así colocamos para generar desde lista
        :return:
        """
        if self.type in ['adq', 'rc'] and self.type_egress == 'bank':
            for line in self.lines_employee:
                line.update({'generated': self.general_check if not line.voucher_id else False})

    @api.multi
    def print_hr(self):
        """
        Imprimimos reporte de pagos a empleados
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_pay_order_hr').report_action(self)

    name = fields.Char('No. Orden de pago')
    origin = fields.Char('Origen', required=True, readonly=True, states={'draft': [('readonly', False)]})
    amount = fields.Float('Monto total', required=True, readonly=True, states={'draft': [('readonly', False)]})
    date = fields.Date('Fecha', required=True, readonly=True, states={'draft': [('readonly', False)]},
                       track_visibility='onchange')
    # Dependiendo del origen
    type = fields.Selection([
        ('fap', 'Factura de proveedor'),
        ('oc', 'Orden de compra/servicio'),
        ('adq', 'Anticipo de quincena'),
        ('rc', 'Rol consolidado'),
        ('cajc', 'Caja chica'),
        ('rp', 'RPG Aprobadas'),
        ('svi', 'Solicitud de viático'),
        ('lvi', 'Liquidación de viático'),
    ], string="Tipo de origen", required=True, readonly=True, states={'draft': [('readonly', False)]})
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('paid', 'Pagado'),
        ('cancel', 'Anulado'),
    ], default='draft', string="Estado", readonly=True, copy=False, track_visibility='onchange')
    currency_id = fields.Many2one('res.currency', string='Moneda', default=_default_currency)
    # Campos para traer los diferentes documentos para la OP
    # Factura
    invoice_id = fields.Many2one('account.invoice', 'Factura')
    # Varias facturas
    invoice_ids = fields.Many2many('account.invoice', 'relation_invoice_pay_order', 'pay_order_id',
                                   'invoice_id',
                                   string='Facturas', copy=False)
    # OC
    purchase_order_id = fields.Many2one('purchase.order', 'Orden de compra')
    # ADQ
    type_egress = fields.Selection([
        ('bank', 'Cheque'),
        ('payment_various', 'Pagos varios'),
        ('transfer', 'Transferencia')
    ], string='Forma de pago', required=True, readonly=True, states={'draft': [('readonly', False)]},
        track_visibility='onchange')
    bank_id = fields.Many2one('res.bank', string="Banco", domain=[('type_use', '=', 'payments')], readonly=True,
                              states={'draft': [('readonly', False)]})
    advance_payment_id = fields.Many2one('eliterp.advance.payment', 'ADQ')
    # RC
    payslip_run_id = fields.Many2one('hr.payslip.run', 'Rol consolidado')
    # Reposición caja chica
    replacement_small_box_id = fields.Many2one('eliterp.replacement.small.box', 'Reposición caja chica')
    # Requerimiento de pago
    payment_request_id = fields.Many2one('eliterp.payment.request', "Requerimiento de pago")
    # Viáticos
    viaticum_id = fields.Many2one('eliterp.travel.allowance.request', "Solicitud viático")
    # Liquidación de Viáticos
    liquidation_settlement_id = fields.Many2one('eliterp.liquidation.settlement', "Liquidación de viático")
    lines_employee = fields.One2many('eliterp.list.employees.order', 'pay_order_id', string='Empleados', readonly=True,
                                     states={'draft': [('readonly', False)]})
    beneficiary = fields.Char('Beneficiario', readonly=True, states={'draft': [('readonly', False)]})
    general_check = fields.Boolean('Cheque general', readonly=True, states={'draft': [('readonly', False)]},
                                   default=True)
    comment = fields.Text('Notas y comentarios', readonly=True, states={'draft': [('readonly', False)]})
    voucher_id = fields.Many2one('account.voucher', string='Comprobante', readonly=True)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    is_advanced = fields.Boolean('Es anticipo?', default=False, copy=False)  # Campo para anticipo de proveedores


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def _get_pays_purchase_order(self):
        args = [
            ('company_id', '=', self.company_id.id),
            ('name', '=', self.origin)
        ]
        purchase_order = self.env['purchase.order'].search(args)
        pays = []
        for line in purchase_order.lines_pay_order.filtered(lambda x: x.state == 'paid'):
            for move_line in line.voucher_id.move_id.line_ids.filtered(lambda x: x.account_id == self.account_id):
                pays.append(move_line)
        return pays

    @api.multi
    def action_invoice_open(self):
        """
        MM: Validamos el voucher de factura para caja chica
        :return: object
        """

        res = super(AccountInvoice, self).action_invoice_open()
        pays = self._get_pays_purchase_order()
        line_move_invoice = self.move_id.line_ids.filtered(
            lambda x: x.account_id == self.account_id)
        for line_pay in pays:
            (line_move_invoice + line_pay).reconcile()
        return res

    @api.one
    def _get_outstanding_info_JSON(self):
        self.outstanding_credits_debits_widget = json.dumps(False)
        if self.state == 'open':
            type_payment = 'Anticipos/Cruces'
            domain = [('account_id', '=', self.account_id.id),
                      ('partner_id', '=', self.env['res.partner']._find_accounting_partner(self.partner_id).id),
                      ('reconciled', '=', False), '|', ('amount_residual', '!=', 0.0),
                      ]
            if self.type in ('out_invoice', 'in_refund'):
                domain.extend([('amount_residual_currency', '!=', 0.0), ('credit', '>', 0), ('debit', '=', 0)])
            else:
                domain.extend(
                    ['|', ('is_advanced', '=', True), ('credit', '=', 0),
                     ('debit', '>', 0)])  # Anticipo/Cruces de proveedor
            info = {'title': '', 'outstanding': True, 'content': [], 'invoice_id': self.id}
            lines = self.env['account.move.line'].search(domain)
            currency_id = self.currency_id
            if len(lines) != 0:
                for line in lines:
                    # get the outstanding residual value in invoice currency
                    if line.currency_id and line.currency_id == self.currency_id:
                        amount_to_show = abs(line.amount_residual_currency)
                    else:
                        amount_to_show = line.company_id.currency_id.with_context(date=line.date).compute(
                            abs(line.amount_residual), self.currency_id)
                    if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                        continue
                    info['content'].append({
                        'journal_name': line.ref or line.move_id.name,
                        'amount': amount_to_show,
                        'currency': currency_id.symbol,
                        'id': line.id,
                        'position': currency_id.position,
                        'digits': [69, self.currency_id.decimal_places],
                    })
                info['title'] = type_payment
                self.outstanding_credits_debits_widget = json.dumps(info)
                self.has_outstanding = True

    @api.multi
    def generate_request(self):
        """
        Abrimos ventana para añadir pago
        :return: dict
        """
        self.flag_change = True
        view = self.env.ref('eliterp_treasury.eliterp_view_form_pay_wizard')
        context = {
            'default_default_date': self.date_invoice,
            'default_type': 'fap',
            'default_default_amount': self.residual_pay_order,
            'default_amount': self.residual_pay_order,
            'default_project_id': self.project_id.id
        }
        return {
            'name': "Crear orden de pago",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.pay.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.one
    @api.depends('flag_change', 'state', 'lines_pay_order.state')
    def _get_customize_amount(self):
        """
        Obtenemos estado de ADQ pra OP
        """
        pays = self.lines_pay_order.filtered(lambda x: x.state == 'paid')
        if not pays:
            self.state_pay_order = 'generated'
            self.residual_pay_order = self.residual
        else:
            total = 0.00
            for pay in pays:  # Soló contabilizadas
                total += round(pay.amount, 2)
            self.improved_pay_order = total
            payments = self.residual + total
            self.residual_pay_order = round(payments - self.improved_pay_order, 2)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01) or self.reconciled:
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    @api.one
    def _compute_pay_orders(self):
        orders = self.env['eliterp.pay.order'].search(['|',
                                                       ('invoice_id', '=', self.id),
                                                       ('invoice_ids', 'in', self.id)
                                                       ])
        self.lines_pay_order = orders
        self.pay_orders_count = len(orders)

    state_pay_order = fields.Selection([
        ('generated', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], default='generated', string="Estado de pago", compute='_get_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado OP', compute='_get_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo OP', compute='_get_customize_amount', store=True)
    lines_pay_order = fields.Many2many('eliterp.pay.order', compute='_compute_pay_orders', string='Órdenes de pago')
    flag_change = fields.Boolean('Bandera de cambio?')

    def open_pay_orders(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.eliterp_action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.lines_pay_order) > 1:
            result['domain'] = "[('id','in',%s)]" % self.lines_pay_order.ids
        elif len(self.lines_pay_order) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.lines_pay_order.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    pay_orders_count = fields.Integer('No. OP', compute='_compute_pay_orders')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.multi
    def generate_request(self):
        """
        Abrimos ventana para añadir pago
        :return: dict
        """
        self.flag_change = True
        view = self.env.ref('eliterp_treasury.eliterp_view_form_pay_wizard')
        context = {
            'default_default_date': self.date_order,
            'default_type': 'oc',
            'default_default_amount': self.residual_pay_order,
            'default_project_id': self.project_id.id if self.project_id else False,
            'default_amount': self.residual_pay_order
        }
        return {
            'name': "Crear orden de pago",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.pay.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.one
    @api.depends('flag_change', 'invoice_ids', 'invoice_status', 'lines_pay_order')
    def _get_customize_amount(self):
        """
        Obtenemos estado de ADQ pra OP
        """
        pays = self.lines_pay_order.filtered(lambda x: not x.state == 'cancel')
        total_invoices = 0.00
        for inv in self.invoice_ids:  # Facturas ingresadas
            if inv and inv.state not in ('cancel', 'draft'):
                total_invoices += inv.residual
        _total = round(self.amount_total - total_invoices, 2)
        if self.invoice_status == 'invoiced':
            self.state_pay_order = 'paid'
        else:
            if not pays:
                self.state_pay_order = 'generated'
                self.residual_pay_order = _total
            else:
                total = 0.00
                for pay in pays:  # Soló contabilizadas
                    total += round(pay.amount, 2)
                self.improved_pay_order = total
                self.residual_pay_order = round(_total - self.improved_pay_order, 2)
                if float_is_zero(self.residual_pay_order,
                                 precision_rounding=0.01) or self.invoice_status == 'invoiced':
                    self.state_pay_order = 'paid'
                else:
                    self.state_pay_order = 'partial_payment'

    state_pay_order = fields.Selection([
        ('generated', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], default='generated', string="Estado de pago", compute='_get_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado OP', compute='_get_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo OP', compute='_get_customize_amount', store=True)
    lines_pay_order = fields.One2many('eliterp.pay.order', 'purchase_order_id', string='Órdenes de pago')
    flag_change = fields.Boolean('Bandera de cambio?')

    @api.multi
    def _compute_pay_orders_count(self):
        for record in self:
            record.pay_orders_count = len(record.lines_pay_order)

    @api.multi
    def open_pay_orders(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.eliterp_action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.lines_pay_order) > 1:
            result['domain'] = "[('id','in',%s)]" % self.lines_pay_order.ids
        elif len(self.lines_pay_order) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.lines_pay_order.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    pay_orders_count = fields.Integer('No. OP', compute='_compute_pay_orders_count')


class LinesAdvancePayment(models.Model):
    _inherit = 'eliterp.lines.advance.payment'

    @api.depends('pay_lines.pay_order_id.state', 'pay_lines.amount', 'amount_total', 'pay_lines.voucher_id')
    def _compute_amount(self):
        """
        Calculamos los pagos del empleado asignado en las ordenes
        :return:
        """
        for record in self:
            paid = 0.00
            for line in record.pay_lines:
                if line.pay_order_id.state == 'paid' or line.voucher_id:
                    paid += line.amount
            record.paid_amount = paid
            record.residual = record.amount_total - record.paid_amount
            if float_is_zero(record.residual, precision_rounding=0.01):
                record.flag = True
            else:
                record.flag = False

    @api.constrains('amount_payable')
    @api.one
    def _check_amount_payable(self):
        """
        Verificamos monto a pagar no sea mayor al  total menos el residuo
        :return:
        """
        if self.amount_payable > self.residual:
            raise ValidationError("Monto a pagar (%.2f) mayor al saldo (%.2f) para %s." % (
                self.amount_payable, self.residual, self.employee_id.name
            ))

    selected = fields.Boolean('Seleccionar?', default=False)
    flag = fields.Boolean('Conciliado', compute="_compute_amount", store=True)
    paid_amount = fields.Float('Pagado', compute='_compute_amount', store=True)
    residual = fields.Float('Saldo', compute='_compute_amount', store=True)
    amount_payable = fields.Float('A pagar')
    pay_lines = fields.One2many('eliterp.list.employees.order', 'pay_order_line_id', string="Líneas de ordenes de pago",
                                readonly=True,
                                copy=False)


class AdvancePayment(models.Model):
    _inherit = 'eliterp.advance.payment'

    @api.multi
    def posted_advance(self):
        """
        Acualizamos el monto a pagar
        :return:
        """
        for line in self.lines_advance:
            line.update({'amount_payable': line.amount_total})
        return super(AdvancePayment, self).posted_advance()

    @api.multi
    def generate_request(self):
        """
        Abrimos ventana para añadir pago
        :return: dict
        """
        if float_is_zero(self.total_pay_order, 0.01):
            raise ValidationError("No hay líneas seleccionadas para orden de pago.")
        self.flag_change = True
        view = self.env.ref('eliterp_treasury.eliterp_view_form_pay_wizard')
        context = {
            'default_default_date': self.date,
            'default_type': 'adq',
            'default_default_amount': self.total_pay_order,
            'default_amount': self.total_pay_order,
            'default_project_id': self.project_id.id
        }
        return {
            'name': "Crear orden de pago",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.pay.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.one
    @api.depends('flag_change', 'lines_advance.selected', 'lines_pay_order.state')
    def _get_customize_amount(self):
        """
        Obtenemos estado de OP
        """
        pays = self.lines_pay_order.filtered(lambda x: x.state == 'paid')
        if not pays:
            self.state_pay_order = 'generated'
        else:
            total = 0.00
            for pay in pays:
                total += round(pay.amount, 2)
            self.improved_pay_order = total
            self.residual_pay_order = round(self.total - total, 2)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01):
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    @api.one
    @api.depends('lines_advance.selected')
    def _get_total_pay_order(self):
        """
        Valor de OP seleccionado los empleados (MAEQ) y el monto a pagar
        """
        total = 0.00
        for line in self.lines_advance:
            if line.selected and not line.flag:
                total += line.amount_payable
        self.total_pay_order = round(total, 2)

    @api.onchange('select_all')
    def _onchange_select_all(self):
        """
        Seleccionamos o no todos los registros si la bandera es falsa
        :return:
        """
        for line in self.lines_advance:
            if not line.flag:
                line.update({'selected': self.select_all})

    state_pay_order = fields.Selection([
        ('generated', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], default='generated', string="Estado de pago", compute='_get_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado OP', compute='_get_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo OP', compute='_get_customize_amount', store=True)
    lines_pay_order = fields.One2many('eliterp.pay.order', 'advance_payment_id', string='Órdenes de pago')
    flag_change = fields.Boolean('Bandera de cambio?')
    total_pay_order = fields.Float('Total a pagar', compute='_get_total_pay_order', track_visibility='onchange')
    select_all = fields.Boolean('Seleccionar todos?', default=False)

    @api.multi
    def _compute_pay_orders_count(self):
        """
        Cantidad de órdenes de pago
        :return:
        """
        for record in self:
            record.pay_orders_count = len(record.lines_pay_order)

    @api.multi
    def open_pay_orders(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.eliterp_action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.lines_pay_order) > 1:
            result['domain'] = "[('id','in',%s)]" % self.lines_pay_order.ids
        elif len(self.lines_pay_order) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.lines_pay_order.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    pay_orders_count = fields.Integer('No. OP', compute='_compute_pay_orders_count')


class LinesPayslipRun(models.Model):
    _inherit = 'eliterp.lines.payslip.run'

    @api.depends('pay_lines.pay_order_id.state', 'pay_lines.amount', 'pay_lines.voucher_id')
    def _compute_amount(self):
        """
        Calculamos los pagos del empleado asignado en las ordenes
        :return:
        """
        for record in self:
            paid = 0.00
            for line in record.pay_lines:
                if line.pay_order_id.state == 'paid' or line.voucher_id:
                    paid += line.amount
            record.paid_amount = paid
            record.residual = record.net_receive - record.paid_amount
            if float_is_zero(record.residual, precision_rounding=0.01):
                record.flag = True
            else:
                record.flag = False

    @api.constrains('amount_payable')
    @api.one
    def _check_amount_payable(self):
        """
        Verificamos monto a pagar no sea mayor al  total menos el residuo
        :return:
        """
        if round(self.amount_payable, 2) > round(self.residual, 2):
            raise ValidationError("Monto a pagar (%.2f) mayor al saldo a recibir (%.2f) para %s." % (
                self.amount_payable, self.residual, self.role_id.employee_id.name
            ))

    @api.onchange('selected')
    def _onchange_selected(self):
        """
        Cambiamos monto a pagar
        :return:
        """
        for line in self:
            line.update({'amount_payable': line.residual})

    selected = fields.Boolean('Seleccionar?', default=False)
    flag = fields.Boolean('Conciliado', compute="_compute_amount", store=True)
    paid_amount = fields.Float('Pagado', compute='_compute_amount', store=True)
    residual = fields.Float('Saldo', compute='_compute_amount', store=True)
    amount_payable = fields.Float('A pagar')
    pay_lines = fields.One2many('eliterp.list.employees.order', 'pay_order_line_id_rc',
                                string="Líneas de ordenes de pago",
                                readonly=True,
                                copy=False)


class PayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    @api.multi
    def confirm_payslip_run(self):
        """
        Acualizamos el monto a pagar
        :return:
        """
        for line in self.lines_payslip_run:
            line.update({'amount_payable': line.net_receive})
        return super(PayslipRun, self).confirm_payslip_run()

    @api.multi
    def generate_request(self):
        """
        Abrimos ventana para añadir pago
        :return: dict
        """
        if float_is_zero(self.total_pay_order, 0.01):
            raise ValidationError("No hay líneas seleccionadas para orden de pago.")
        self.flag_change = True
        view = self.env.ref('eliterp_treasury.eliterp_view_form_pay_wizard')
        context = {
            'default_default_date': self.date_end,
            'default_type': 'rc',
            'default_default_amount': self.total_pay_order,
            'default_amount': self.total_pay_order,
            'default_project_id': self.project_id.id
        }
        return {
            'name': "Crear orden de pago",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.pay.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.one
    @api.depends('flag_change', 'lines_payslip_run.selected', 'lines_pay_order.state')
    def _get_customize_amount(self):
        """
        Obtenemos estado de OP
        """
        pays = self.lines_pay_order.filtered(lambda x: x.state == 'paid')
        if not pays:
            self.state_pay_order = 'generated'
        else:
            total = 0.00
            for pay in pays:
                total += round(pay.amount, 2)
            self.improved_pay_order = total
            self.residual_pay_order = round(self.total - total, 2)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01):
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    @api.depends('lines_payslip_run.selected')
    @api.one
    def _get_total_pay_order(self):
        """
        Valor de OP seleccionado los empleados (MAEQ)
        """
        total = 0.00
        for line in self.lines_payslip_run:
            if line.selected and not line.flag:
                total += line.amount_payable
        self.total_pay_order = round(total, 2)

    @api.onchange('select_all')
    def _onchange_select_all(self):
        for line in self.lines_payslip_run:
            if not line.flag:
                line.update({'selected': self.select_all})

    state_pay_order = fields.Selection([
        ('generated', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], default='generated', string="Estado de pago", compute='_get_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado OP', compute='_get_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo OP', compute='_get_customize_amount', store=True)
    lines_pay_order = fields.One2many('eliterp.pay.order', 'payslip_run_id', string='Órdenes de pago')
    flag_change = fields.Boolean('Bandera de cambio?')
    total_pay_order = fields.Float('Total de pago', compute='_get_total_pay_order')
    select_all = fields.Boolean('Seleccionar todos?', default=False)

    @api.multi
    def _compute_pay_orders_count(self):
        for record in self:
            record.pay_orders_count = len(record.lines_pay_order)

    @api.multi
    def open_pay_orders(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.eliterp_action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.lines_pay_order) > 1:
            result['domain'] = "[('id','in',%s)]" % self.lines_pay_order.ids
        elif len(self.lines_pay_order) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.lines_pay_order.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    pay_orders_count = fields.Integer('No. OP', compute='_compute_pay_orders_count')


class ReplacementSmallBox(models.Model):
    _inherit = 'eliterp.replacement.small.box'

    @api.multi
    def generate_request(self):
        """
        Abrimos ventana para añadir pago
        :return: dict
        """
        self.flag_change = True
        view = self.env.ref('eliterp_treasury.eliterp_view_form_pay_wizard')
        context = {
            'default_default_date': self.opening_date,
            'default_type': 'cajc',
            'default_default_amount': self.residual_pay_order,
            'default_amount': self.residual_pay_order
        }
        return {
            'name': "Crear orden de pago",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.pay.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.one
    @api.depends('flag_change', 'lines_pay_order')
    def _get_customize_amount(self):
        """
        Obtenemos estado de ADQ pra OP
        """
        pays = self.lines_pay_order.filtered(lambda x: not x.state == 'cancel')
        if not pays:
            self.state_pay_order = 'generated'
            self.residual_pay_order = self.total_vouchers
        else:
            total = 0.00
            for pay in pays:  # Soló contabilizadas
                total += round(pay.amount, 2)
            self.improved_pay_order = total
            self.residual_pay_order = round(self.total_vouchers - self.improved_pay_order, 2)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01):
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    state_pay_order = fields.Selection([
        ('generated', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], default='generated', string="Estado de pago", compute='_get_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado OP', compute='_get_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo OP', compute='_get_customize_amount', store=True)
    lines_pay_order = fields.One2many('eliterp.pay.order', 'replacement_small_box_id', string='Órdenes de pago')
    flag_change = fields.Boolean('Bandera de cambio?')

    @api.multi
    def _compute_pay_orders_count(self):
        for record in self:
            record.pay_orders_count = len(record.lines_pay_order)

    @api.multi
    def open_pay_orders(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.eliterp_action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.lines_pay_order) > 1:
            result['domain'] = "[('id','in',%s)]" % self.lines_pay_order.ids
        elif len(self.lines_pay_order) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.lines_pay_order.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    pay_orders_count = fields.Integer('No. OP', compute='_compute_pay_orders_count')


class PaymentRequest(models.Model):
    _inherit = 'eliterp.payment.request'

    @api.multi
    def generate_request(self):
        """
        Abrimos ventana para añadir pago
        :return: dict
        """
        self.flag_change = True
        view = self.env.ref('eliterp_treasury.eliterp_view_form_pay_wizard')
        context = {
            'default_default_date': self.application_date,
            'default_type': 'rp',
            'default_default_amount': self.residual_pay_order,
            'default_amount': self.residual_pay_order,
            'default_project_id': self.project_id.id if self.project_id else False
        }
        return {
            'name': "Crear orden de pago",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.pay.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.one
    @api.depends('flag_change', 'lines_pay_order')
    def _get_customize_amount(self):
        """
        Obtenemos estado de ADQ pra OP
        """
        pays = self.lines_pay_order.filtered(lambda x: not x.state == 'cancel')
        if not pays:
            self.state_pay_order = 'generated'
            self.residual_pay_order = self.total
        else:
            total = 0.00
            for pay in pays:  # Soló contabilizadas
                total += round(pay.amount, 2)
            self.improved_pay_order = total
            self.residual_pay_order = round(self.total - self.improved_pay_order, 2)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01):
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    state_pay_order = fields.Selection([
        ('generated', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], default='generated', string="Estado de pago", compute='_get_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado OP', compute='_get_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo OP', compute='_get_customize_amount', store=True)
    lines_pay_order = fields.One2many('eliterp.pay.order', 'payment_request_id', string='Órdenes de pago')
    flag_change = fields.Boolean('Bandera de cambio?')

    @api.multi
    def _compute_pay_orders_count(self):
        for record in self:
            record.pay_orders_count = len(record.lines_pay_order)

    @api.multi
    def open_pay_orders(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.eliterp_action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.lines_pay_order) > 1:
            result['domain'] = "[('id','in',%s)]" % self.lines_pay_order.ids
        elif len(self.lines_pay_order) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.lines_pay_order.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    @api.multi
    def cancel(self):
        if any(po.state != 'draft' for po in self.lines_pay_order):
            raise UserError("No se puede cancelar, RPG si tiene ordenes cerradas o anuladas.")
        self.write({'state': 'deny'})

    pay_orders_count = fields.Integer('No. OP', compute='_compute_pay_orders_count')


class LiquidationSettlement(models.Model):
    _inherit = 'eliterp.liquidation.settlement'

    @api.multi
    def generate_request(self):
        """
        Abrimos ventana para añadir pago
        :return: dict
        """
        self.flag_change = True
        view = self.env.ref('eliterp_treasury.eliterp_view_form_pay_wizard')
        context = {
            'default_default_date': self.application_date,
            'default_type': 'lvi',
            'default_default_amount': self.residual_pay_order,
            'default_amount': self.residual_pay_order,
            'default_project_id': self.project_id.id
        }
        return {
            'name': "Crear orden de pago",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.pay.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.one
    @api.depends('flag_change', 'lines_pay_order.state')
    def _get_customize_amount(self):
        """
        Obtenemos estado de ADQ pra OP
        """
        amount = sum(line.amount_total for line in
                     self.document_lines_without.filtered(lambda x: x.type_validation_without == "reimburse"))
        pays = self.lines_pay_order.filtered(lambda x: x.state == 'paid')
        if not pays:
            self.state_pay_order = 'generated'
            self.residual_pay_order = amount
        else:
            total = 0.00
            for pay in pays:  # Soló contabilizadas
                total += round(pay.amount, 2)
            self.improved_pay_order = total
            self.residual_pay_order = round(amount - self.improved_pay_order, 2)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01):
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    @api.one
    @api.depends('travel_allowance_request_id', 'difference')
    def _compute_is_zero(self):
        """
        Conciliado
        :return:
        """
        if self.travel_allowance_request_id:
            if float_is_zero(self.difference,
                             precision_rounding=0.01) and self.travel_allowance_request_id.state_pay_order == 'paid':
                self.reconciled = True
            else:
                self.reconciled = False

    state_pay_order = fields.Selection([
        ('generated', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], default='generated', string="Estado de pago", compute='_get_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado OP', compute='_get_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo OP', compute='_get_customize_amount', store=True)
    lines_pay_order = fields.One2many('eliterp.pay.order', 'liquidation_settlement_id', string='Órdenes de pago')
    flag_change = fields.Boolean('Bandera de cambio?')
    reconciled = fields.Boolean(compute='_compute_is_zero', store=True)

    @api.multi
    def _compute_pay_orders_count(self):
        for record in self:
            record.pay_orders_count = len(record.lines_pay_order)

    @api.multi
    def open_pay_orders(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.eliterp_action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.lines_pay_order) > 1:
            result['domain'] = "[('id','in',%s)]" % self.lines_pay_order.ids
        elif len(self.lines_pay_order) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.lines_pay_order.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    pay_orders_count = fields.Integer('No. OP', compute='_compute_pay_orders_count')
