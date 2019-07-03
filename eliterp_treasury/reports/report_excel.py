# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
import math

UNIDADES = (
    '', 'Un ', 'Dos ', 'Tres ', 'Cuatro ', 'Cinco ', 'Seis ', 'Siete ', 'Ocho ', 'Nueve ', 'Diez ', 'Once ',
    'Doce ',
    'Trece ', 'Catorce ', 'Quince ', 'Dieciséis ', 'Diecisiete ', 'Dieciocho ', 'Diecinueve ', 'Veinte ')
DECENAS = ('Veinti', 'Treinta ', 'Cuarenta ', 'Cincuenta ', 'Sesenta ', 'Setenta ', 'Ochenta ', 'Noventa ', 'Cien ')
CENTENAS = (
    'Ciento ', 'Doscientos ', 'Trescientos ', 'Cuatrocientos ', 'Quinientos ', 'Seiscientos ', 'Setecientos ',
    'Ochocientos ', 'Novecientos ')


class ChecksIssuedXlsx(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_checks_issued_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_treasury.eliterp_report_checks_issued_report']._get_lines(context)
        sheet = workbook.add_worksheet('Cheques emitidos')
        # Formatos
        bold = workbook.add_format({'bold': 1})
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        # Formatos de celda
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
        # Columnas
        sheet.set_column("A:A", 30)
        sheet.set_column("B:B", 15)
        sheet.set_column("C:C", 15)
        sheet.set_column("D:D", 10)
        sheet.set_column("E:E", 15)
        sheet.set_column("F:F", 60)
        sheet.set_column("G:G", 30)
        sheet.set_column("H:H", 15)
        sheet.set_column("I:I", 15)
        # Cabeceras con filtro
        sheet.autofilter('A3:I3')
        sheet.write('A1', 'REPORTE DE CHEQUES EMITIDOS', title)
        sheet.write(2, 0, "BANCO", bold)
        sheet.write(2, 1, "FECHA EMISIÓN", bold)
        sheet.write(2, 2, "FECHA CHEQUE", bold)
        sheet.write(2, 3, "TIPO", bold)
        sheet.write(2, 4, "NO. CHEQUE", bold)
        sheet.write(2, 5, "CONCEPTO", bold)
        sheet.write(2, 6, "BENEFICIARIO", bold)
        sheet.write(2, 7, "MONTO", bold)
        sheet.write(2, 8, "ESTADO", bold)
        row = 3
        col = 0
        for r in data:
            sheet.write(row, col, r['bank_id'])
            sheet.write(row, col + 1, r['date'], date_format)
            sheet.write(row, col + 2, r['check_date'], date_format)
            sheet.write(row, col + 3, r['type'])
            sheet.write(row, col + 4, r['check_number'])
            sheet.write(row, col + 5, r['concept'])
            sheet.write(row, col + 6, r['beneficiary'])
            sheet.write(row, col + 7, r['amount'], money_format)
            sheet.write(row, col + 8, r['state'])
            row += 1
        sum_row = row
        row += 1
        sum = '=SUM(H4:H%s)' % str(sum_row)
        sheet.write(row, 7, sum, money_format)


class WithholdPurchase(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_withhold_purchase_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, records):
        for record in records:
            sheet = workbook.add_worksheet('Comprobante')
            # Formatos
            money_format = workbook.add_format({'num_format': '$#,##0.00'})
            date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
            # Columnas
            sheet.set_column("A:A", 6)
            sheet.set_column("B:B", 22.29)
            sheet.set_column("C:C", 14)
            sheet.set_column("D:D", 14)
            sheet.set_column("E:E", 8.71)
            sheet.set_column("F:F", 1.14)
            sheet.set_column("G:G", 3)
            sheet.set_column("H:H", 3.14)
            sheet.set_column("I:I", 3.14)
            sheet.set_column("J:J", 3.14)
            sheet.set_column("K:K", 1.57)
            # Filas
            sheet.set_default_row(15)
            sheet.set_row(1, 17.25)
            sheet.set_row(5, 17.25)
            sheet.set_row(3, 17)
            sheet.set_row(4, 14.75)
            sheet.set_row(6, 19)
            sheet.set_row(9, 7.5)
            sheet.set_row(15, 14)
            # Datos
            sheet.write(4, 1, record.partner_id.name)
            sheet.write(5, 1, record.partner_id.documentation_number)
            sheet.write(6, 1, record.partner_id.street)
            sheet.write(4, 5, record.date_withhold, date_format)
            sheet.write(5, 6, "FACTURA")
            sheet.write(6, 6, record.invoice_id.invoice_number)
            # Líneas de retención
            row = 10
            right_format = workbook.add_format({'align': 'right'})
            _right_format = workbook.add_format({'align': 'right', 'num_format': '$#,##0.00'})
            for line in record.lines_withhold:
                amount = str(int(line.tax_id.amount)) + " %"
                sheet.write(row, 0, record.date_withhold[:4], right_format)
                sheet.write(row, 1, line.base_taxable, _right_format)
                sheet.write(row, 2, "RENTA" if line.retention_type == 'rent' else "IVA", right_format)
                sheet.write(row, 3, line.tax_id.code, right_format)
                sheet.merge_range(row, 4, row, 6, amount, right_format)
                sheet.merge_range(row, 7, row, 9, line.amount, _right_format)
                row += 1
            # Total
            total = sum(line.amount for line in record.lines_withhold)
            sheet.merge_range(16, 7, 16, 9, total, _right_format)


class CheckVoucher(models.AbstractModel):
    _name = 'report.eliterp_treasury.eliterp_report_check_voucher_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def __convertNumber(self, n):
        output = ''
        if (n == '100'):
            output = "Cien "
        elif (n[0] != '0'):
            output = CENTENAS[int(n[0]) - 1]
        k = int(n[1:])
        if (k <= 20):
            output += UNIDADES[k]
        else:
            if ((k > 30) & (n[2] != '0')):
                output += '%sy %s' % (DECENAS[int(n[1]) - 2], UNIDADES[int(n[2])])
            else:
                output += '%s%s' % (DECENAS[int(n[1]) - 2], UNIDADES[int(n[2])])
        return output

    def Numero_a_Texto(self, number_in):
        convertido = ''
        number_str = str(number_in) if (type(number_in) != 'str') else number_in
        number_str = number_str.zfill(9)
        millones, miles, cientos = number_str[:3], number_str[3:6], number_str[6:]
        if (millones):
            if (millones == '001'):
                convertido += 'Un Millon '
            elif (int(millones) > 0):
                convertido += '%sMillones ' % self.__convertNumber(millones)
        if (miles):
            if (miles == '001'):
                convertido += 'Mil '
            elif (int(miles) > 0):
                convertido += '%sMil ' % self.__convertNumber(miles)
        if (cientos):
            if (cientos == '001'):
                convertido += 'Un '
            elif (int(cientos) > 0):
                convertido += '%s ' % self.__convertNumber(cientos)
        return convertido

    def get_amount_to_word(self, j):
        try:
            Arreglo1 = str(j).split(',')
            Arreglo2 = str(j).split('.')
            if (len(Arreglo1) > len(Arreglo2) or len(Arreglo1) == len(Arreglo2)):
                Arreglo = Arreglo1
            else:
                Arreglo = Arreglo2

            if (len(Arreglo) == 2):
                whole = math.floor(j)
                frac = j - whole
                num = str("{0:.2f}".format(frac))[2:]
                return (self.Numero_a_Texto(Arreglo[0]) + 'con ' + num + "/100").capitalize()
            elif (len(Arreglo) == 1):
                return (self.Numero_a_Texto(Arreglo[0]) + 'con ' + '00/100').capitalize()
        except ValueError:
            return "Cero"

    def generate_xlsx_report(self, workbook, data, records):
        for record in records:
            sheet = workbook.add_worksheet('Cheque')
            # Formatos
            money_format = workbook.add_format({'num_format': '$#,##0.00', 'bold': 1})
            bold = workbook.add_format({'bold': 1})
            if (record.bank_id.display_name == 'Banco Bolivariano 0005285XXX'):
                # Margins
                sheet.set_margins(left=0.18, right=0.7, top=0.73, bottom=0.75)
                # Columnas
                sheet.set_column("A:A", 7.50)
                sheet.set_column("B:B", 10.71)
                sheet.set_column("C:C", 10.71)
                sheet.set_column("D:D", 10.71)
                sheet.set_column("E:E", 7)
                sheet.set_column("F:F", 11.57)
                # Filas
                sheet.set_default_row(15)
                sheet.set_row(3, 11.25)
                sheet.set_row(4, 13.50)
                # Datos
                sheet.write(0, 1, record.beneficiary, bold)
                sheet.write(0, 6, record.amount_cancel, money_format)
                sheet.write(1, 1, self.get_amount_to_word(record.amount_cancel), bold)
                sheet.write(4, 0, 'GUAYAQUIL, %s' % record.check_date, bold)

            elif (record.bank_id.display_name == 'Banco Internacional Cta. Cte 1500619XXX'):
                # Margins
                sheet.set_margins(left=0.04, right=0.7, top=0.0, bottom=0.75)
                # Columnas
                sheet.set_column("A:A", 8.14)
                sheet.set_column("B:B", 10.71)
                sheet.set_column("C:C", 10.71)
                sheet.set_column("D:D", 10.71)
                sheet.set_column("E:E", 10.71)
                sheet.set_column("F:F", 0.33)
                sheet.set_column("G:G", 11.57)
                # Filas
                sheet.set_default_row(15)
                sheet.set_row(0, 8.25)
                sheet.set_row(1, 18)
                sheet.set_row(2, 18)
                sheet.set_row(3, 8.25)
                sheet.set_row(7, 6)
                sheet.set_row(8, 13.50)
                # Datos
                sheet.write(4, 1, record.beneficiary, bold)
                sheet.write(4, 6, record.amount_cancel, money_format)
                sheet.write(5, 1, self.get_amount_to_word(record.amount_cancel), bold)
                sheet.write(8, 0, 'GUAYAQUIL, %s' % record.check_date, bold)

            elif (record.bank_id.display_name == 'Banco Pichincha 2100164XXX'):
                # Margins
                sheet.set_margins(left=0.18, right=0.7, top=0.0, bottom=0.75)
                # Columnas
                sheet.set_column("A:A", 7.29)
                sheet.set_column("B:B", 10.71)
                sheet.set_column("C:C", 10.71)
                sheet.set_column("D:D", 10.71)
                sheet.set_column("F:F", 12.8)
                sheet.set_column("E:E", 13.14)
                # Filas
                sheet.set_default_row(15)
                sheet.set_row(0, 10.50)
                sheet.set_row(3, 19.50)
                sheet.set_row(4, 10.50)
                sheet.set_row(5, 13.50)
                sheet.set_row(7, 18)
                # Datos
                sheet.write(3, 1, record.beneficiary, bold)
                sheet.write(3, 5, record.amount_cancel, money_format)
                sheet.write(5, 1, self.get_amount_to_word(record.amount_cancel), bold)
                sheet.write(7, 1, 'GUAYAQUIL, %s' % record.check_date, bold)
