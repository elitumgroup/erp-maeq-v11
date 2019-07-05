# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).


from datetime import datetime
from odoo import api, fields, models


class AccountBalanceReportPDF(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_account_balance'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        vouchers = self.env['account.voucher'].search([
            ('bank_id', '=', doc.bank_id.id),
            ('state', '=', 'posted'),
            ('voucher_type', '=', 'purchase'),
            ('type_egress', 'in', ['bank', 'transfer']),
            ('reconcile', '=', False)
        ])
        total = doc.amount
        for voucher in sorted(vouchers, key=lambda x: x.check_date):
            data.append({
                'date': voucher.check_date,
                'type': 'CHEQUE' if voucher.type_egress == 'bank' else 'TRANSFERENCIA',
                'document': voucher.check_number or voucher.transfer_code or '-',
                'reference': voucher.concept,
                'amount': -1 * voucher.amount_cancel,
                'balance': round(total - voucher.amount_cancel, 2)
            })
            total = total - voucher.amount_cancel
        if data:
            TOTAL.append({'total': data[::-1][0]['balance']})
        return data

    @staticmethod
    def _get_total():
        return TOTAL[0]['total']

    @api.model
    def get_report_values(self, docids, data=None):
        global TOTAL
        TOTAL = []
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.account.balance.report',
            'docs': self.env['eliterp.account.balance.report'].browse(docids),
            'get_lines': self._get_lines,
            'today': fields.Date.today(),
            'total': self._get_total,
            'data': data,
        }


class AccountBalanceReport(models.TransientModel):
    _name = 'eliterp.account.balance.report'

    _description = "Ventana para reporte de saldo bancario"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_account_balance_report').report_action(self)

    bank_id = fields.Many2one('res.bank', 'Banco', domain="[('type_use', '=', 'payments')]", required=True)
    account_number = fields.Char(related='bank_id.account_number', string='No. Cuenta')
    amount = fields.Float('Saldo bancario', required=True)


class AccountsReceivableReportPDF(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_accounts_receivable'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = []
        if doc['customer_type'] != 'todos':
            arg.append(('partner_id', '=', doc['partner'].id))
        if doc['estado'] != 'todas':
            arg.append(('date_due', '<=', fields.date.today()))
        arg.append(('date_invoice', '>=', doc['start_date']))
        arg.append(('date_invoice', '<=', doc['end_date']))
        arg.append(('viaticum', '=', False))
        arg.append(('state', '=', 'open'))
        arg.append(('type', '=', 'out_invoice'))
        facturas = self.env['account.invoice'].search(arg)
        count = 0
        for factura in facturas:
            count += 1
            expiration_date = datetime.strptime(factura.date_due, "%Y-%m-%d").date()
            delinquency = doc['delinquency']
            days_expire = 0
            defeated = False
            overcome = False
            if factura.residual != 0.00:
                if fields.date.today() > expiration_date:
                    delinquency = (fields.date.today() - expiration_date).days
                    defeated = True
            if factura.residual != 0.00:
                if expiration_date < fields.date.today():
                    overcome = True
                    days_expire = (expiration_date - fields.date.today()).days
            amount = factura.amount_total_signed
            data.append({
                'partner': factura.partner_id.name,
                'number': factura.invoice_number,
                'amount': amount,
                'outstanding_balance': factura.residual,
                'expedition_date': factura.date_invoice,
                'expiration_date': factura.date_due,
                'delinquency': delinquency,
            })
            if doc['report_type'] == 'completo':
                data[-1].update(
                    {'overcome_30': amount if overcome == True and (days_expire >= 1 and days_expire <= 30) else float(
                        0.00),
                     'overcome_90': amount if overcome == True and (days_expire >= 31 and days_expire <= 90) else 0.00,
                     'overcome_180': amount if overcome == True and (
                             days_expire >= 91 and days_expire <= 180) else 0.00,
                     'overcome_360': amount if overcome == True and (
                             days_expire >= 181 and days_expire <= 360) else 0.00,
                     'overcome_mayor': amount if overcome == True and (days_expire > 360) else 0.00,
                     'defeated_30': amount if defeated == True and (delinquency >= 1 and delinquency <= 30) else 0.00,
                     'defeated_90': amount if defeated == True and (delinquency >= 31 and delinquency <= 90) else 0.00,
                     'defeated_180': amount if defeated == True and (
                             delinquency >= 91 and delinquency <= 180) else 0.00,
                     'defeated_360': amount if defeated == True and (
                             delinquency >= 181 and delinquency <= 360) else 0.00,
                     'defeated_mayor': amount if defeated == True and (delinquency > 360) else 0.00, })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.accounts.receivable.report',
            'docs': self.env['eliterp.accounts.receivable.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class AccountsReceivableReport(models.TransientModel):
    _name = 'eliterp.accounts.receivable.report'

    _description = "Ventana para reporte de cuentas por cobrar"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_accounts_receivable_report').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en EXCEL
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_report_accounts_receivable_xlsx').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    report_type = fields.Selection([('completo', 'Completo'), ('resumido', 'Resumido')], default='completo',
                                   string='Tipo reporte')
    estado = fields.Selection([('todas', 'Todas'), ('vencidas', 'Vencidas')], default='todas')
    delinquency = fields.Integer('Morosidad')
    customer_type = fields.Selection([('todos', 'Todos'), ('partner', 'Individual')], 'Tipo de Cliente',
                                     default='todos')
    partner = fields.Many2one('res.partner', 'Cliente')


class AccountsReceivableReportExcel(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_accounts_receivable_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_treasury.eliterp_report_accounts_receivable']._get_lines(context)
        sheet = workbook.add_worksheet('Cuentas por cobrar')
        # Formatos
        center_format = workbook.add_format({'align': 'center'})
        _right_format = workbook.add_format({'align': 'right', 'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
        # Columnas
        sheet.set_column("A:A", 37)
        sheet.set_column("B:B", 17.29)
        sheet.set_column("C:C", 9)
        sheet.set_column("D:D", 16.5)
        sheet.set_column("E:E", 14.25)
        sheet.set_column("F:F", 14.24)
        sheet.set_column("G:G", 11.6)
        sheet.set_column("H:H", 8.6)
        sheet.set_column("I:I", 8.6)
        sheet.set_column("J:J", 8.6)
        sheet.set_column("K:K", 8.6)
        sheet.set_column("K:K", 8.6)
        sheet.set_column("L:L", 8.6)
        sheet.set_column("M:M", 8.6)
        sheet.set_column("N:N", 8.6)
        sheet.set_column("O:O", 8.6)
        sheet.set_column("P:P", 8.6)
        sheet.set_column("Q:Q", 8.6)

        # Filas
        sheet.set_default_row(15)
        # Datos
        sheet.merge_range('A1:Q2', 'Cuentas por cobrar', title)
        sheet.merge_range(2, 7, 2, 11, "VALORES POR VENCER", center_format)
        sheet.merge_range(2, 12, 2, 16, "VALORES VENCIDOS", center_format)
        sheet.merge_range(3, 7, 3, 11, "ANTIGÜEDAD DE CARTERA (DÍAS)", center_format)
        sheet.merge_range(3, 12, 3, 16, "ANTIGÜEDAD DE CARTERA (DÍAS)", center_format)
        sheet.write(4, 0, "CLIENTE")
        sheet.write(4, 1, "NO. FACTURA")
        sheet.write(4, 2, "VALOR")
        sheet.write(4, 3, "SALDO PENDIENTE")
        sheet.write(4, 4, "FECHA EMISION")
        sheet.write(4, 5, "FECHA VENCIMIENTO")
        sheet.write(4, 6, "MOROSIDAD")
        sheet.write(4, 7, "1-30")
        sheet.write(4, 8, "31-90")
        sheet.write(4, 9, "91-180")
        sheet.write(4, 10, "181-360")
        sheet.write(4, 11, "MAYOR A")
        sheet.write(4, 12, "1-30")
        sheet.write(4, 13, "31-90")
        sheet.write(4, 14, "91-180")
        sheet.write(4, 15, "181-360")
        sheet.write(4, 16, "MAYOR A")
        row = 5
        for r in data:
            sheet.write(row, 0, r['partner'])
            sheet.write(row, 1, r['number'])
            sheet.write(row, 2, r['amount'], _right_format)
            sheet.write(row, 3, r['outstanding_balance'], _right_format)
            sheet.write(row, 4, r['expedition_date'], date_format)
            sheet.write(row, 5, r['expiration_date'], date_format)
            sheet.write(row, 6, r['delinquency'], _right_format)
            sheet.write(row, 7, r['overcome_30'], _right_format)
            sheet.write(row, 8, r['overcome_90'], _right_format)
            sheet.write(row, 9, r['overcome_180'], _right_format)
            sheet.write(row, 10, r['overcome_360'], _right_format)
            sheet.write(row, 11, r['overcome_mayor'], _right_format)
            sheet.write(row, 12, r['defeated_30'], _right_format)
            sheet.write(row, 13, r['defeated_90'], _right_format)
            sheet.write(row, 14, r['defeated_180'], _right_format)
            sheet.write(row, 15, r['defeated_360'], _right_format)
            sheet.write(row, 16, r['defeated_mayor'], _right_format)
            row += 1


class AccountsToPayReportPDF(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_accounts_to_pay'

    def _get_payments(self, invoice, start, end):
        payments = invoice._get_payments_vals()
        amount = 0.00
        for payment in filter(lambda x: start <= x['date'] <= end, payments):
            amount += payment['amount']
        return amount

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
         :param doc:
         :return: list
        """
        data = []
        arg = []
        if doc['provider_type'] != 'todos':
            arg.append(('partner_id', '=', doc['provider'].id))
        if doc['estado'] != 'todas':
            arg.append(('date_due', '<=', fields.date.today()))
        arg.append(('date_invoice', '>=', doc['start_date']))
        arg.append(('date_invoice', '<=', doc['end_date']))
        arg.append(('state', 'in', ('open', 'paid')))
        arg.append(('type', '=', 'in_invoice'))
        facturas = self.env['account.invoice'].search(arg)
        count = 0
        for factura in facturas:
            if factura.residual == 0.00:
                continue
            count += 1
            expiration_date = datetime.strptime(factura.date_due, "%Y-%m-%d").date()
            nota_credito = self.env['account.invoice'].search([('invoice_number', '=', factura.id)])
            delinquency = doc['delinquency']
            days_expire = 0
            defeated = False
            overcome = False
            if factura.residual != 0.00:
                if fields.date.today() > expiration_date:
                    delinquency = (fields.date.today() - expiration_date).days
                    defeated = True
            if factura.residual != 0.00:
                if expiration_date < fields.date.today():
                    overcome = True
                    days_expire = (expiration_date - fields.date.today()).days
            amount = factura.amount_total
            saldo_p = factura.residual
            if expiration_date > fields.date.today():
                delinquency = fields.date.today() - expiration_date
            data.append({
                'provider': factura.partner_id.name,
                'number': factura.invoice_number,
                'subtotal': factura.amount_untaxed,
                'iva': factura.amount_tax,
                'amount': amount,
                'amount_credit_note': nota_credito.amount_untaxed if len(nota_credito) > 0 else 0.00,
                'amount_retention': factura.amount_retention if factura.have_withhold else 0.00,
                'pays': self._get_payments(factura, doc['start_date'], doc['end_date']),
                'outstanding_balance': factura.residual,
                'broadcast_date': factura.date_invoice,
                'expiration_date': factura.date_due,
                'delinquency': delinquency,
            })
            if doc['report_type'] == 'completo':
                data[-1].update(
                    {
                        'overcome_30': saldo_p if overcome and (days_expire >= 1 and days_expire <= 30) else float(
                            0.00),
                        'overcome_90': saldo_p if overcome and (days_expire >= 31 and days_expire <= 90) else 0.00,
                        'overcome_180': saldo_p if overcome and (days_expire >= 91 and days_expire <= 180) else 0.00,
                        'overcome_360': saldo_p if overcome and (days_expire >= 181 and days_expire <= 360) else 0.00,
                        'overcome_mayor': saldo_p if overcome and (days_expire > 360) else 0.00,
                        'defeated_30': saldo_p if defeated and (delinquency >= 1 and delinquency <= 30) else 0.00,
                        'defeated_90': saldo_p if defeated and (delinquency >= 31 and delinquency <= 90) else 0.00,
                        'defeated_180': saldo_p if defeated and (delinquency >= 91 and delinquency <= 180) else 0.00,
                        'defeated_360': saldo_p if defeated and (delinquency >= 181 and delinquency <= 360) else 0.00,
                        'defeated_mayor': saldo_p if defeated and (delinquency > 360) else 0.00,
                    })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.accounts.to.pay.report',
            'docs': self.env['eliterp.accounts.to.pay.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class AccountsToPayReport(models.TransientModel):
    _name = 'eliterp.accounts.to.pay.report'

    _description = "Ventana para reporte de cuentas por pagar"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_accounts_to_pay').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en EXCEL
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_accounts_to_pay_xlsx').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    report_type = fields.Selection([('completo', 'Completo'), ('resumido', 'Resumido')], default='completo')
    estado = fields.Selection([('todas', 'Todas'), ('vencidas', 'Vencidas')], default='todas')
    delinquency = fields.Integer('Morosidad')
    provider_type = fields.Selection([('todos', 'Todos'), ('provider', 'Individual')], 'Tipo de Proveedor',
                                     default='todos')
    provider = fields.Many2one('res.partner', 'Proveedor')


class AccountsToPayReportExcel(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_action_accounts_to_pay_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_treasury.eliterp_report_accounts_to_pay']._get_lines(context)
        sheet = workbook.add_worksheet('CUENTAS POR PAGAR')
        # Formatos
        center_format = workbook.add_format({'align': 'center'})
        _right_format = workbook.add_format({'align': 'right', 'num_format': '#,##0.00'})
        _right_format_p = workbook.add_format({
            'align': 'right',
            'num_format': '#,##0.00',
            'color': 'red'
        })
        _right_format_r = workbook.add_format({
            'align': 'right',
            'num_format': '#,##0.00',
            'bold': True,
            'font_size': 12,
            'bg_color': '#D3D3D3'
        })
        date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
        # Columnas
        sheet.set_column("A:A", 50)
        sheet.set_column("B:B", 20)
        sheet.set_column("C:C", 10)
        sheet.set_column("D:D", 7.5)
        sheet.set_column("E:E", 12.5)
        sheet.set_column("F:F", 10)
        sheet.set_column("G:G", 10)
        sheet.set_column("H:H", 15)
        sheet.set_column("I:I", 20)
        sheet.set_column("J:J", 15)
        sheet.set_column("K:K", 15)
        sheet.set_column("L:L", 15)
        sheet.set_column("M:M", 8.6)
        sheet.set_column("N:N", 8.6)
        sheet.set_column("O:O", 8.6)
        sheet.set_column("P:P", 8.6)
        sheet.set_column("Q:Q", 8.6)
        sheet.set_column("R:R", 8.6)
        sheet.set_column("S:S", 8.6)
        sheet.set_column("T:T", 8.6)
        sheet.set_column("U:U", 8.6)
        sheet.set_column("V:V", 8.6)

        # Filas
        sheet.set_default_row(15)
        # Datos
        sheet.merge_range('A1:V2', 'Cuentas por pagar', title)
        sheet.merge_range(2, 12, 2, 16, "VALORES POR VENCER", center_format)
        sheet.merge_range(2, 17, 2, 21, "VALORES VENCIDOS", center_format)
        sheet.merge_range(3, 12, 3, 16, "ANTIGÜEDAD DE CARTERA (DÍAS)", center_format)
        sheet.merge_range(3, 17, 3, 21, "ANTIGÜEDAD DE CARTERA (DÍAS)", center_format)
        sheet.write(4, 0, "PROVEEDOR")
        sheet.write(4, 1, "NO. FACTURA")
        sheet.write(4, 2, "SUBTOTAL")
        sheet.write(4, 3, "IVA")
        sheet.write(4, 4, "TOTAL")
        sheet.write(4, 5, "N.C")
        sheet.write(4, 6, "RETENIDO")
        sheet.write(4, 7, "PAGOS")
        sheet.write(4, 8, "SALDO PENDIENTE")
        sheet.write(4, 9, "FECHA EMISIÓN")
        sheet.write(4, 10, "VENCIMIENTO")
        sheet.write(4, 11, "MOROSIDAD")
        sheet.write(4, 12, "1-30")
        sheet.write(4, 13, "31-90")
        sheet.write(4, 14, "91-180")
        sheet.write(4, 15, "181-360")
        sheet.write(4, 16, "MAYOR A")
        sheet.write(4, 17, "1-30")
        sheet.write(4, 18, "31-90")
        sheet.write(4, 19, "91-180")
        sheet.write(4, 20, "181-360")
        sheet.write(4, 21, "MAYOR A")
        row = 5
        for r in data:
            sheet.write(row, 0, r['provider'])
            sheet.write(row, 1, r['number'])
            sheet.write(row, 2, r['subtotal'], _right_format)
            sheet.write(row, 3, r['iva'], _right_format)
            sheet.write(row, 4, r['amount'], _right_format)

            # Pagado
            sheet.write(row, 5, r['amount_credit_note'], _right_format_p)
            sheet.write(row, 6, r['amount_retention'], _right_format_p)
            sheet.write(row, 7, r['pays'], _right_format_p)

            sheet.write(row, 8, r['outstanding_balance'], _right_format_r)

            sheet.write(row, 9, r['broadcast_date'], date_format)
            sheet.write(row, 10, r['expiration_date'], date_format)
            sheet.write(row, 11, r['delinquency'], _right_format)
            sheet.write(row, 12, r['overcome_30'], _right_format)
            sheet.write(row, 13, r['overcome_90'], _right_format)
            sheet.write(row, 14, r['overcome_180'], _right_format)
            sheet.write(row, 15, r['overcome_360'], _right_format)
            sheet.write(row, 16, r['overcome_mayor'], _right_format)
            sheet.write(row, 17, r['defeated_30'], _right_format)
            sheet.write(row, 18, r['defeated_90'], _right_format)
            sheet.write(row, 19, r['defeated_180'], _right_format)
            sheet.write(row, 20, r['defeated_360'], _right_format)
            sheet.write(row, 21, r['defeated_mayor'], _right_format)
            row += 1


class ChecksReceivedReportPDF(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_checks_received_report'

    def get_facturas(self, facturas):
        bill_number = ""
        count = 0
        for f in facturas:
            if count == 0:
                bill_number = bill_number + f.name[-5:]
                count = count + 1
            else:
                bill_number = bill_number + "-" + f.name[-5:]
        return bill_number

    def _get_lines(self, doc):
        data = []
        arg = []
        if doc['customer_type'] != 'todos':
            arg.append(('partner_id', '=', doc['partner'].id))
        arg.append(('voucher_type', '=', 'sale'))
        vouchers = self.env['account.voucher'].search(arg)
        for voucher in vouchers:
            facturas = self.get_facturas(voucher.lines_invoice_sales)
            for line in voucher.lines_payment:
                if line.type_payment == 'bank':
                    if line.check_type == 'current':
                        datev = voucher.date
                    else:
                        datev = line.create_date
                    if doc['start_date'] <= datev <= doc['end_date']:
                        data.append({
                            'date_received': voucher.date,
                            'document_date': voucher.date if line.check_type == 'corriente' else line.create_date,
                            'credit_date': voucher.date if line.check_type == 'corriente' else line.date_due,
                            'partner': voucher.partner_id.name,
                            'facturas': facturas,
                            'issuing_bank': line.bank_id.name,
                            'number_check': line.check_number,
                            'amount': line.amount,
                        })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.checks.received.report',
            'docs': self.env['eliterp.checks.received.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class ChecksReceivedReport(models.TransientModel):
    _name = 'eliterp.checks.received.report'

    _description = "Ventana para reporte de cheques recibidos"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_checks_received_report').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    customer_type = fields.Selection([('todos', 'Todos'), ('partner', 'Individual')], 'Tipo de Cliente',
                                     default='todos')
    partner = fields.Many2one('res.partner', 'Cliente')
    bank_type = fields.Selection([('todos', 'Todos'), ('bank', 'Individual')], 'Tipo de Asesor', default='todos')
    bank = fields.Many2one('res.bank', 'Banco')


class ChecksIssuedReportPDF(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_checks_issued_report'

    def _get_state(self, state):
        """
        Obtenemos el estado del cheque
        :param voucher:
        :return:
        """
        if state == 'issued':
            return 'EMITIDO'
        elif state == 'protested':
            return 'ANULADO'
        elif state == 'delivered':
            return 'ENTREGADO'
        else:
            return 'COBRADO'

    def _get_lines(self, doc):
        """
        Obtenemos las líneas de reporte
        :param doc:
        :return:
        """
        data = []
        arg = []
        if doc['filter_date'] == 'one':
            arg.append(('date', '>=', doc['start_date']))
            arg.append(('date', '<=', doc['end_date']))
        else:
            arg.append(('check_date', '>=', doc['start_date']))
            arg.append(('check_date', '<=', doc['end_date']))
        arg.append(('type', '=', 'issued'))
        arg.append(('bank_id', 'in', doc['bank_ids']._ids))
        checks = self.env['eliterp.checks'].search(arg)
        for check in checks:
            data.append({
                'bank_id': check.bank_id.name,
                'date': check.date,
                'check_date': check.check_date,
                'type': 'COEG',
                'check_number': check.name,
                'concept': check.voucher_id.concept,
                'beneficiary': check.recipient,
                'amount': check.amount,
                'state': self._get_state(check.state)
            })

        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.checks.issued.report',
            'docs': self.env['eliterp.checks.issued.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class ChecksIssuedReport(models.TransientModel):
    _name = 'eliterp.checks.issued.report'

    _description = "Ventana para reporte de cheques emitidos"

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_checks_issued_xlsx').report_action(self)

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_checks_issued_report').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    filter_date = fields.Selection([('one', 'Emisión'), ('two', 'Fecha de cheque')], 'Filtrar por', default='one')
    bank_ids = fields.Many2many('res.bank', string='Bancos',
                                domain=[('type_use', '=', 'payments')],
                                help="Dejar en blanco si desea de todos los bancos.", required=True)


class ScheduledPaymentsReportPDF(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_pay_orders'

    def get_days_mora(self, vencimiento):
        delinquency = 0
        delinquency = (fields.date.today() - vencimiento).days
        return str(delinquency)

    def _get_lines(self, doc):
        data = []
        arg = []
        if doc['form_pay'] != 'todas':
            arg.append(('way_to_pay', '=', doc['form_pay']))
        pays = self.env['eliterp.pay.order'].search(arg)
        for pay in pays:
            pay_day = pay.date
            if (pay_day >= doc['start_date'] and pay_day <= doc['end_date']):
                expiration_date = datetime.strptime(pay.invoice_id.date_due, "%Y-%m-%d").date()
                partner = self.env['res.partner'].browse(pay.invoice_id.partner_id['id'])
                if pay.invoice_id.state == 'open':  # Soló facturas por pagar
                    data.append({
                        'provider': partner.name,
                        'number_factura': pay.invoice_id.invoice_number,
                        'subtotal': pay.invoice_id.amount_untaxed,
                        'iva': pay.invoice_id.amount_tax,
                        'amount': pay.invoice_id.amount_total,
                        'outstanding_balance': pay.invoice_id.residual,
                        'expiration_date': pay.invoice_id.date_due,
                        'delinquency': "SIN MORA" if pay.invoice_id.residual == 0.00 else self.get_days_mora(
                            expiration_date),
                        'payment_value': pay.amount,
                        'form_pay': "EFECTIVO" if not pay.bank_id else self.env['res.bank'].browse(
                            pay.bank_id.id).name,
                        'pay_day': pay.date,
                    })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.pay.orders.report',
            'docs': self.env['eliterp.pay.orders.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class ScheduledPaymentsReport(models.TransientModel):
    _name = 'eliterp.pay.orders.report'

    _description = "Ventana para reporte de ordenes de pago"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_pay_orders_report').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    form_pay = fields.Selection([('todas', 'Todas'), ('efectivo', 'Efectivo'), ('cheque', 'Cheque')], 'Forma de Pago',
                                default='todas')
