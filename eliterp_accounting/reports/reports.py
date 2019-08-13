# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from datetime import datetime
from odoo.tools import float_is_zero
from itertools import groupby


class FinancialSituationReportXlsx(models.AbstractModel):
    _name = 'report.eliterp_accounting.eliterp_report_financial_xlsx'

    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        global TOTALES
        TOTALES = []
        object = self.env['report.eliterp_accounting.eliterp_report_financial_situation']
        lines_1 = sorted(object._get_report('1', context), key=lambda k: int(k['code'].replace('.', '')))
        lines_2 = sorted(object._get_report('2', context), key=lambda k: int(k['code'].replace('.', '')))
        lines_3 = sorted(object._get_report('3', context), key=lambda k: int(k['code'].replace('.', '')))
        sheet = workbook.add_worksheet('Situación financiera')
        # Columnas
        sheet.set_column("A:A", 15)
        sheet.set_column("B:B", 50)
        sheet.set_column("C:C", 10)
        sheet.set_column("D:D", 15)
        sheet.autofilter('A3:D3')
        # Formatos
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        heading = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'align': 'center',
            'border': 1
        })
        heading_1 = workbook.add_format({
            'bold': True,
            'font_size': 11
        })
        heading_1_number = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'num_format': '#,##0.00'
        })
        heading_2 = workbook.add_format({
            'font_size': 9,
            'bold': True,
        })
        heading_2_number = workbook.add_format({
            'font_size': 9,
            'bold': True,
            'num_format': '#,##0.00'
        })
        heading_3 = workbook.add_format({
            'font_size': 8,
        })
        heading_3_number = workbook.add_format({
            'font_size': 8,
            'num_format': '#,##0.00'
        })
        # Formatos de celda
        sheet.write('A1', 'ESTADO DE SITUACIÓN FINANCIERA', title)
        columns = [
            'CÓDIGO', 'NOMBRE DE CUENTA', 'TIPO', 'BALANCE'
        ]
        row = 2
        col = 0
        for column in columns:
            sheet.write(row, col, column, heading)
            col += 1
        # 1
        row += 1
        for line in lines_1:
            if line['tipo'] == 'padre':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['monto'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['monto'], heading_2_number)
                if line['sub_cuenta']:
                    for lsb in line['sub_cuenta']:
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['monto'], heading_3_number)
                row += 1
        # 2
        for line in lines_2:
            if line['tipo'] == 'padre':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['monto'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['monto'], heading_2_number)
                if line['sub_cuenta']:
                    for lsb in line['sub_cuenta']:
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['monto'], heading_3_number)
                row += 1
        # 3
        for line in lines_3:
            if line['tipo'] == 'padre':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['monto'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['monto'], heading_2_number)
                if line['sub_cuenta']:
                    for lsb in line['sub_cuenta']:
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['monto'], heading_3_number)
                row += 1
        row += 1
        sheet.write(row, 1, 'PATRIMONIO + PASIVO', heading_1)
        sheet.write(row, 3, TOTALES[1]['total_pasivo'] + TOTALES[2]['total_patrimonio'], heading_1_number)


class FinancialSituationReportPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting.eliterp_report_financial_situation'

    def get_saldo_resultado(self, cuenta, tipo, fecha_inicio, fecha_fin):
        '''Obtenemos el saldo del Estado de Resultados'''
        movimientos = self.env['account.move.line'].search([('account_id', '=', cuenta),
                                                            ('date', '>=', fecha_inicio if fecha_inicio else '2000-01-01'),
                                                            ('date', '<=', fecha_fin)])

        credit = 0.00
        debit = 0.00
        for line in movimientos:
            credit += line.credit
            debit += line.debit
        monto = round(debit - credit, 2)
        if tipo == '5':
            if debit < credit:
                if monto > 0:
                    monto = -1 * round(debit - credit, 2)
        if tipo == '4':
            if debit < credit:
                if monto < 0:
                    monto = -1 * round(debit - credit, 2)
            if debit > credit:
                if monto > 0:
                    monto = -1 * round(debit - credit, 2)
        return monto

    def estado_resultado(self, fecha_inicio, fecha_fin):
        '''Obtener el monto dde Estado de Resultados'''
        cuentas_contables = self.env['account.account'].search([('user_type_id.name', '!=', 'odoo')], order="code")
        cuentas = []
        movimientos = []
        padre = False
        total_movimiento = 0.00
        cuentas_4 = cuentas_contables.filtered(lambda x: (x.code.split("."))[0] == '4')
        cuentas_5 = cuentas_contables.filtered(lambda x: (x.code.split("."))[0] == '5')
        total_ingresos = 0.00
        total_gastos = 0.00
        for cuenta in cuentas_4:
            if cuentas == []:
                cuentas.append({'code': self.env['account.account'].search([('code', '=', '4')])[0].code,
                                'name': 'INGRESOS',
                                'tipo': 'padre',
                                'sub_cuenta': [],
                                'monto': 0.00,
                                'cuenta': self.env['account.account'].search([('code', '=', '4')])[0],
                                'padre': padre})
            else:
                if cuenta.account_type == 'view':
                    padre = self.buscar_padre(cuenta)
                    cuentas = self.update_saldo(cuentas)
                    cuentas.append({'code': cuenta.code,
                                    'tipo': 'vista',
                                    'sub_cuenta': [],
                                    'name': cuenta.name,
                                    'monto': 0.00,
                                    'cuenta': cuenta,
                                    'padre': padre})
                else:
                    monto_movimiento = self.get_saldo_resultado(cuenta.id, '4', fecha_inicio, fecha_fin)
                    padre = self.buscar_padre(cuenta)
                    print(cuenta.code)
                    index = list(map(lambda x: x['code'], cuentas)).index(padre)
                    cuentas[index]['sub_cuenta'].append({'code': cuenta.code,
                                                         'tipo': 'movimiento',
                                                         'name': cuenta.name,
                                                         'monto': monto_movimiento})
                    cuentas[index]['monto'] = cuentas[index]['monto'] + monto_movimiento
        cuentas = self.update_saldo(cuentas)
        total_ingresos = cuentas[0]['monto']
        cuentas = []
        movimientos = []
        padre = False
        total_movimiento = 0.00
        for cuenta in cuentas_5:
            if cuentas == []:
                cuentas.append({'code': self.env['account.account'].search([('code', '=', '5')])[0].code,
                                'name': 'GASTOS',
                                'tipo': 'padre',
                                'sub_cuenta': [],
                                'monto': 0.00,
                                'cuenta': self.env['account.account'].search([('code', '=', '5')])[0],
                                'padre': padre})
            else:
                if cuenta.account_type == 'view':
                    padre = self.buscar_padre(cuenta)
                    cuentas = self.update_saldo(cuentas)
                    cuentas.append({'code': cuenta.code,
                                    'tipo': 'vista',
                                    'sub_cuenta': [],
                                    'name': cuenta.name,
                                    'monto': 0.00,
                                    'cuenta': cuenta,
                                    'padre': padre})
                else:
                    monto_movimiento = self.get_saldo_resultado(cuenta.id, '5', fecha_inicio, fecha_fin)
                    padre = self.buscar_padre(cuenta)
                    print(cuenta.code)
                    index = list(map(lambda x: x['code'], cuentas)).index(padre)
                    cuentas[index]['sub_cuenta'].append({'code': cuenta.code,
                                                         'tipo': 'movimiento',
                                                         'name': cuenta.name,
                                                         'monto': monto_movimiento})
                    cuentas[index]['monto'] = cuentas[index]['monto'] + monto_movimiento
        cuentas = self.update_saldo(cuentas)
        total_gastos = cuentas[0]['monto']
        return total_ingresos - total_gastos

    def update_saldo(self, cuentas):
        '''Actualizamos el saldo de la Cuenta Padre'''
        cuentas = cuentas[::-1]
        if len(cuentas) == 1:
            return cuentas[::-1]
        for cuenta in cuentas:
            cuenta['monto'] = 0.00
            total = 0.00
            if cuenta['sub_cuenta'] != []:
                for sub_cuenta in cuenta['sub_cuenta']:
                    total = total + sub_cuenta['monto']
                cuenta['monto'] = total
        for x in range(len(cuentas)):
            for y in range(len(cuentas)):
                if cuentas[x]['padre'] == cuentas[y]['code']:
                    cuentas[y]['monto'] = cuentas[y]['monto'] + cuentas[x]['monto']
        return cuentas[::-1]

    def get_saldo(self, cuenta, tipo, doc):
        '''Obtenemos el saldo de la cuenta y verificamos su naturaleza'''
        # MARZ
        movimientos = self.env['account.move.line'].search([('account_id', '=', cuenta.id),
                                                            ('date', '>=', doc.start_date if doc.start_date else '2000-01-01'),
                                                            ('date', '<=', doc.end_date)])
        credit = 0.00
        debit = 0.00
        if cuenta.code == '3.3.3':
            date_object = datetime.strptime(doc.end_date, "%Y-%m-%d")
            final = date_object.replace(year=date_object.year - 1)
            movimiento = self.env['account.move.line'].search([('account_id', '=', cuenta.id),
                                                               ('date', '=', str(final))])
            movimientos = movimientos | movimiento
        for line in movimientos:
            credit += line.credit
            debit += line.debit
        monto = round(debit - credit, 2)
        if tipo == '1':
            if debit < credit:
                if monto > 0:
                    monto = -1 * round(debit - credit, 2)
        if tipo in ('2', '3'):
            if debit < credit:
                if monto < 0:
                    monto = -1 * round(debit - credit, 2)
            if debit > credit:
                if monto > 0:
                    monto = -1 * round(debit - credit, 2)

        return monto

    def buscar_padre(self, cuenta):
        '''Buscamos la cuenta padre de la cuenta'''
        split = cuenta.code.split(".")[:len(cuenta.code.split(".")) - 1]
        codigo = ""
        for code in split:
            if codigo == "":
                codigo = codigo + str(code)
            else:
                codigo = codigo + "." + str(code)
        return codigo

    def _get_report(self, tipo, doc):
        '''Reporte General'''
        cuentas_contables = self.env['account.account'].search([('user_type_id.name', '!=', 'odoo')], order="code")
        cuentas = []
        movimientos = []
        padre = False
        total_movimiento = 0.00
        for cuenta in cuentas_contables:
            if (cuenta.code.split("."))[0] == tipo:
                if cuentas == []:
                    # Cuentas Principales (Sin Movimiento)
                    if tipo == '1':
                        name = "ACTIVOS"
                    if tipo == '2':
                        name = "PASIVOS"
                    if tipo == '3':
                        name = "PATRIMONIO NETO"
                    cuentas.append({'code': self.env['account.account'].search([('code', '=', tipo)])[0].code,
                                    'name': name,
                                    'tipo': 'padre',
                                    'sub_cuenta': [],
                                    'monto': 0.00,
                                    'cuenta': self.env['account.account'].search([('code', '=', tipo)])[0],
                                    'padre': padre})
                else:
                    if cuenta.account_type == 'view':
                        # Cuentas Vistas
                        padre = self.buscar_padre(cuenta)
                        cuentas = self.update_saldo(cuentas)
                        cuentas.append({'code': cuenta.code,
                                        'tipo': 'vista',
                                        'sub_cuenta': [],
                                        'name': cuenta.name,
                                        'monto': 0.00,
                                        'cuenta': cuenta,
                                        'padre': padre})
                    else:
                        # Cuentas con Movimientos
                        conciliacion_bancaria = []
                        if cuenta.user_type_id.type == 'bank':
                            conciliacion_bancaria = self.env['eliterp.bank.conciliation'].search(
                                [('start_date', '=', doc.start_date),
                                 ('end_date', '=', doc.end_date),
                                 ('account_id', '=', cuenta.id)])
                            if len(conciliacion_bancaria) != 0:
                                monto_movimiento = conciliacion_bancaria[0].total
                            else:
                                monto_movimiento = self.get_saldo(cuenta, tipo, doc)
                        else:
                            monto_movimiento = self.get_saldo(cuenta, tipo, doc)
                        padre = self.buscar_padre(cuenta)
                        if cuenta.code:  # Imprimimos Cuentas (tipo = movimiento)
                            print(cuenta.code)
                        index = list(map(lambda x: x['code'], cuentas)).index(padre)
                        cuentas[index]['sub_cuenta'].append({'code': cuenta.code,
                                                             'tipo': 'movimiento',
                                                             'name': cuenta.name,
                                                             'monto': round(monto_movimiento, 2)})
                        cuentas[index]['monto'] = cuentas[index]['monto'] + monto_movimiento
            cuentas = self.update_saldo(cuentas)
        if tipo == '1':
            TOTALES.append({'total_activo': cuentas[0]['monto']})
        if tipo == '2':
            TOTALES.append({'total_pasivo': cuentas[0]['monto']})
        if tipo == '3':
            movimientos = []
            cuenta_estado = list(filter(lambda x: x['code'] == '3.3', cuentas))
            if cuenta_estado:
                if cuenta_estado[0]['monto'] != 0.00:
                    # MARZ
                    monto = self.estado_resultado(doc.start_date, doc.end_date)
                    movimientos_internos = {}
                    if monto >= 0:
                        movimientos_internos['code'] = '3.3.1.1'
                        movimientos_internos['tipo'] = 'movimiento'
                        movimientos_internos['name'] = 'GANANCIA NETA DEL PERIODO'
                        movimientos_internos['monto'] = monto
                    else:
                        movimientos_internos['code'] = '3.3.2.1'
                        movimientos_internos['tipo'] = 'movimiento'
                        movimientos_internos['name'] = '(-) PERDIDA NETA DEL PERIODO'
                        movimientos_internos['monto'] = monto
                    for cuenta in cuentas:
                        if cuenta['code'] == '3.3':
                            cuenta['sub_cuenta'].append(movimientos_internos)
                            cuenta['monto']  = cuenta['monto'] + movimientos_internos['monto']
                    TOTALES.append({'total_patrimonio': cuentas[0]['monto'] + monto})
                    cuentas[0]['monto'] = cuentas[0]['monto'] + movimientos_internos['monto']
                    return cuentas
            # Si Estado de Resultados es igual a 0
            monto = self.estado_resultado(doc.start_date, doc.end_date)
            if monto >= 0:
                movimientos.append({'code': '3.3.1.1',
                                    'tipo': 'movimiento',
                                    'name': 'GANANCIA NETA DEL PERIODO',
                                    'monto': monto})
            else:
                movimientos.append({'code': '3.3.2.1',
                                    'tipo': 'movimiento',
                                    'name': '(-) PERDIDA NETA DEL PERIODO',
                                    'monto': monto})
            cuentas.append({'code': '3.3',
                            'tipo': 'vista',
                            'sub_cuenta': movimientos,
                            'name': 'RESULTADO DEL EJERCICIO',
                            'monto': monto,
                            'cuenta': False,
                            'padre': False})
            cuentas[0]['monto'] = cuentas[0]['monto'] + monto
            TOTALES.append({'total_patrimonio': cuentas[0]['monto']})
        return cuentas

    def get_total_activo(self):
        return TOTALES[0]['total_activo']

    def get_total_pasivo(self):
        return TOTALES[1]['total_pasivo']

    def get_total_patrimonio(self):
        return TOTALES[2]['total_patrimonio']

    def get_total_ejercicio(self):
        return TOTALES[1]['total_pasivo'] + TOTALES[2]['total_patrimonio']

    def get_periodo(self, fecha):
        return (fecha.split("-"))[0]

    def get_cuentas_orden(self, lista):
        lista_ordenada = sorted(lista, key=lambda k: int(k['code'].replace('.', '')))
        return lista_ordenada

    @api.model
    def get_report_values(self, docids, data=None):
        global TOTALES
        TOTALES = []
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.financial.situation',
            'docs': self.env['eliterp.financial.situation'].browse(docids),
            'data': data,
            'get_report': self._get_report,
            'get_total_activo': self.get_total_activo,
            'get_total_pasivo': self.get_total_pasivo,
            'get_total_patrimonio': self.get_total_patrimonio,
            'get_total_ejercicio': self.get_total_ejercicio,
            'get_periodo': self.get_periodo,
            'get_cuentas_orden': self.get_cuentas_orden,
        }


class FinancialSituationReport(models.TransientModel):
    _name = 'eliterp.financial.situation'

    _description = "Ventana para reporte de estado de situación financiera"

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_financial_situation_xlsx').report_action(self)

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_financial_situation').report_action(self)

    start_date = fields.Date('Fecha inicio')
    end_date = fields.Date('Fecha fin', required=True)


class StatusResultsReportXlsx(models.AbstractModel):
    _name = 'report.eliterp_accounting.eliterp_report_result_xlsx'

    _inherit = 'report.report_xlsx.abstract'


    def _get_lines(self, doc, type):

        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        object = self.env['report.eliterp_accounting.eliterp_report_status_results']
        accounts = []
        accounts_base = self.env['account.account'].search([('code', '=ilike', type + '%')])
        for account in accounts_base:
            if not accounts:
                accounts.append({
                    'code': account.code,
                    'name': account.name,
                    'type': 'principal',
                    'subaccounts': [],
                    'amount': 0.00,
                    'account': account,
                    'parent': False
                })
            else:
                if account.account_type == 'view':
                    parent = object._query_parent(account)
                    accounts = object._update_amount(accounts)
                    accounts.append({
                        'code': account.code,
                        'name': account.name,
                        'type': 'view',
                        'subaccounts': [],
                        'amount': 0.00,
                        'account': account,
                        'parent': parent
                    })
                else:
                    parent = object._query_parent(account)
                    index = list(map(lambda x: x['code'], accounts)).index(parent)
                    accounts[index]['subaccounts'].append({
                        'code': account.code,
                        'type': 'movement',
                        'name': account.name,
                        'amount': object._get_balance(account, type, doc)
                    })
                    accounts[index]['amount'] = accounts[index]['amount'] + object._get_balance(account, type, doc)
        accounts = object._update_amount(accounts)
        return accounts


    def generate_xlsx_report(self, workbook, data, context):
        lines_4 = sorted(self._get_lines(context, '4'), key=lambda k: int(k['code'].replace('.', '')))
        lines_5 = sorted(self._get_lines(context, '5'), key=lambda k: int(k['code'].replace('.', '')))
        sheet = workbook.add_worksheet('Estado de resultados')
        # Columnas
        sheet.set_column("A:A", 15)
        sheet.set_column("B:B", 50)
        sheet.set_column("C:C", 10)
        sheet.set_column("D:D", 15)
        sheet.autofilter('A3:D3')
        # Formatos
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        heading = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'align': 'center',
            'border': 1
        })
        heading_1 = workbook.add_format({
            'bold': True,
            'font_size': 11
        })
        heading_1_number = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'num_format': '#,##0.00'
        })
        heading_2 = workbook.add_format({
            'font_size': 9,
            'bold': True,
        })
        heading_2_number = workbook.add_format({
            'font_size': 9,
            'bold': True,
            'num_format': '#,##0.00'
        })
        heading_3 = workbook.add_format({
            'font_size': 8,
        })
        heading_3_number = workbook.add_format({
            'font_size': 8,
            'num_format': '#,##0.00'
        })
        # Formatos de celda
        sheet.write('A1', 'ESTADO DE RESULTADOS', title)
        columns = [
            'CÓDIGO', 'NOMBRE DE CUENTA', 'TIPO', 'BALANCE'
        ]
        row = 2
        col = 0
        for column in columns:
            sheet.write(row, col, column, heading)
            col += 1
        # 4
        row += 1
        for line in lines_4:
            if line['type'] == 'principal':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['amount'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['amount'], heading_2_number)
                if line['subaccounts']:
                    for lsb in line['subaccounts']:
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['amount'], heading_3_number)
                row += 1
        # 5
        for line in lines_5:
            if line['type'] == 'principal':
                sheet.write(row, 0, line['code'], heading_1)
                sheet.write(row, 1, line['name'], heading_1)
                sheet.write(row, 3, line['amount'], heading_1_number)
                row += 1
            else:
                sheet.write(row, 0, line['code'], heading_2)
                sheet.write(row, 1, line['name'], heading_2)
                sheet.write(row, 2, 'VISTA', heading_2)
                sheet.write(row, 3, line['amount'], heading_2_number)
                if line['subaccounts']:
                    for lsb in line['subaccounts']:
                        row += 1
                        sheet.write(row, 0, lsb['code'], heading_3)
                        sheet.write(row, 1, lsb['name'], heading_3)
                        sheet.write(row, 2, 'MOVIMIENTO', heading_3)
                        sheet.write(row, 3, lsb['amount'], heading_3_number)
                row += 1
        row += 1
        amount_total = lines_4[0]['amount'] - lines_5[0]['amount']
        heading_result_number = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'num_format': '#,##0.00',
            'bg_color': 'red'
        })
        if amount_total > 0:
            sheet.write(row, 3, amount_total, heading_1)
        else:
            sheet.write(row, 3, amount_total, heading_result_number)


class StatusResultsReportPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting.eliterp_report_status_results'

    @staticmethod
    def _query_parent(account):
        split = account.code.split(".")[:len(account.code.split(".")) - 1]
        code = ""
        for a in split:
            if code == "":
                code = code + str(a)
            else:
                code = code + "." + str(a)
        return code

    @staticmethod
    def _update_amount(accounts):
        accounts = accounts[::-1]
        if len(accounts) == 1:
            return accounts[::-1]
        for account in accounts:
            account['amount'] = 0.00
            total = 0.00
            if account['subaccounts']:
                for subaccount in account['subaccounts']:
                    total = total + subaccount['amount']
                account['amount'] = total
        for x in range(len(accounts)):
            for y in range(len(accounts)):
                if accounts[x]['parent'] == accounts[y]['code']:
                    accounts[y]['amount'] = accounts[y]['amount'] + accounts[x]['amount']
        return accounts[::-1]

    def _get_balance(self, account, type, doc):
        args = [
            ('account_id', '=', account.id),
            ('date', '>=', doc.start_date if doc.start_date else '2000-01-01'),
            ('date', '<=', doc.end_date)
        ]
        if doc.project_id:
            args.append(('project_id', '=', doc.project_id.id))
        if doc.account_analytic_id:
            args.append(('analytic_account_id', '=', doc.account_analytic_id.id))
        moves = self.env['account.move.line'].search(args)
        credit = 0.00
        debit = 0.00
        for line in moves:
            credit += line.credit
            debit += line.debit
        amount = round(debit - credit, 2)
        if type == '5':
            if debit < credit:
                if amount > 0:
                    amount = -1 * round(debit - credit, 2)
        if type == '4':
            if debit < credit:
                if amount < 0:
                    amount = -1 * round(debit - credit, 2)
            if debit > credit:
                if amount > 0:
                    amount = -1 * round(debit - credit, 2)
        return round(amount, 2)

    def _get_lines(self, doc, type):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        accounts = []
        accounts_base = self.env['account.account'].search([('code', '=ilike', type + '%')])
        for account in accounts_base:
            if not accounts:
                accounts.append({
                    'code': account.code,
                    'name': account.name,
                    'type': 'principal',
                    'subaccounts': [],
                    'amount': 0.00,
                    'account': account,
                    'parent': False
                })
            else:
                if account.account_type == 'view':
                    parent = self._query_parent(account)
                    accounts = self._update_amount(accounts)
                    accounts.append({
                        'code': account.code,
                        'name': account.name,
                        'type': 'view',
                        'subaccounts': [],
                        'amount': 0.00,
                        'account': account,
                        'parent': parent
                    })
                else:
                    parent = self._query_parent(account)
                    index = list(map(lambda x: x['code'], accounts)).index(parent)
                    accounts[index]['subaccounts'].append({
                        'code': account.code,
                        'type': 'movement',
                        'name': account.name,
                        'amount': self._get_balance(account, type, doc)
                    })
                    accounts[index]['amount'] = accounts[index]['amount'] + self._get_balance(account, type, doc)
        accounts = self._update_amount(accounts)
        if type == '4':
            TOTALS.append({'total_income': accounts[0]['amount']})
        else:
            TOTALS.append({'total_spends': accounts[0]['amount']})
        return accounts

    @staticmethod
    def _get_total_exercise():
        """
        Total del ejercicio buscado
        :return: float
        """
        return TOTALS[0]['total_income'] - TOTALS[1]['total_spends']

    @staticmethod
    def _get_result():
        """
        Si existen ganancias o pérdidas en período buscado
        :return: boolean
        """
        if TOTALS[0]['total_income'] - TOTALS[1]['total_spends'] >= 0:
            return True
        else:
            return False

    @api.model
    def get_report_values(self, docids, data=None):
        global TOTALS  # Variable para valores totales
        TOTALS = []
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.status.results.report',
            'docs': self.env['eliterp.status.results.report'].browse(docids),
            'get_lines': self._get_lines,
            'get_total_exercise': self._get_total_exercise,
            'get_result': self._get_result,
            'data': data,
        }


class StatusResultsReport(models.TransientModel):
    _name = 'eliterp.status.results.report'

    _description = "Ventana para reporte de estado de resultados"

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_status_results_xlsx').report_action(self)

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_status_results').report_action(self)

    start_date = fields.Date('Fecha inicio')
    end_date = fields.Date('Fecha fin', required=True)


class GeneralLedgerReportPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting.eliterp_report_general_ledger'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        if doc.type == 'all':
            base_accounts = self.env['account.account'].search([('account_type', '=', 'movement')])  # Todas las cuentas
        else:
            base_accounts = doc.account_id
        accounts = []
        data = []
        for c in base_accounts:
            accounts.append(c)
        accounts.sort(key=lambda x: x.code, reverse=False)  # Ordenamos de menor a mayor por código
        for account in accounts:
            lines = self.env['account.move.line'].search(
                [('account_id', '=', account.id), ('date', '>=', doc.start_date), ('date', '<=', doc.end_date)],
                order="date, full_reconcile_id")  # Movimientos de la cuenta ordenamos por fecha
            beginning_balance = self.env['eliterp.accounting.help']._get_beginning_balance(account, doc.start_date,
                                                                                           doc.end_date)
            balance = beginning_balance
            total_debit = 0.00
            total_credit = 0.00
            data_line = []  # Líneas de movimientos de la cuenta
            if doc.not_canceled:
                lines = lines.filtered(lambda a: not a.move_id == 'cancel' or not a.move_id.reversed)
            for line in lines:
                total_debit = total_debit + line.debit
                total_credit = total_credit + line.credit
                type = (account.code.split("."))[0]
                amount = line.debit - line.credit
                if type in ['1', '5']:
                    if line.debit < line.credit:
                        if amount > 0:
                            amount = -1 * round(line.debit - line.credit, 2)
                if type in ['2', '3', '4']:
                    if line.debit < line.credit:
                        if amount < 0:
                            amount = -1 * round(line.debit - line.credit, 2)
                    if line.debit > line.credit:
                        if amount > 0:
                            amount = -1 * round(line.debit - line.credit, 2)
                balance = balance + amount
                data_line.append({'name': line.move_id.name,
                                  'reconciled_number': line.full_reconcile_id.name if line.full_reconcile_id else ' ',
                                  'date': line.date,
                                  'detail': line.name[:97] + '...' if line.name else '-',
                                  'debit': line.debit,
                                  'credit': line.credit,
                                  'balance': balance})

            total_balance = total_debit - total_credit
            if len(lines) != 0:  # Naturaleza de cuentas
                if type in ['1', '5']:
                    if total_debit < total_credit:
                        if total_balance > 0:
                            total_balance = -1 * round(total_debit - total_credit, 2)
                if type in ['2', '3', '4']:
                    if total_debit < total_credit:
                        if total_balance < 0:
                            total_balance = -1 * round(total_debit - total_credit, 2)
                    if total_debit > total_credit:
                        if total_balance > 0:
                            total_balance = -1 * round(total_debit - total_credit, 2)
            total_balance = beginning_balance + total_balance
            if data_line or beginning_balance > 0:  # Soló si tienes líneas de movimiento o saldo inicial
                data.append({
                    'account': account.name,
                    'code': account.code,
                    'moves': data_line,
                    'total_debit': total_debit,
                    'total_credit': total_credit,
                    'total_balance': total_balance,
                    'beginning_balance': beginning_balance
                })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.general.ledger.report',
            'docs': self.env['eliterp.general.ledger.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class GeneralLedgerReport(models.TransientModel):
    _name = 'eliterp.general.ledger.report'

    _description = "Ventana para reporte de libro mayor"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_general_ledger').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True)
    type = fields.Selection([('all', 'Todas'), ('one', 'Seleccionar cuentas')], default='all', string='Tipo de reporte')
    not_canceled = fields.Boolean('No colocar asientos anulados', default=False, help="Se filtra por asientos no validados y/o reversados.")
    account_id = fields.Many2many('account.account', string='Cuentas contables', domain=[('account_type', '=', 'movement')])


class Taxes103104ReportXlsx(models.AbstractModel):
    _name = 'report.eliterp_accounting.eliterp_report_taxes_103_104_xlsx'

    _inherit = 'report.report_xlsx.abstract'

    def _get_lines_sales(self, context):
        """
        Obtenemos todas las líneas facturadas de ventas con sus valores de retención
        :param context:
        :return: list
        """
        data = []
        arg = []
        arg.append(('date_invoice', '>=', context.start_date))
        arg.append(('date_invoice', '<=', context.end_date))
        arg.append(('state', 'not in', ('draft', 'cancel')))
        arg.append(('type', '=', 'out_invoice'))
        invoices = self.env['account.invoice'].search(arg)
        count = 0
        for invoice in invoices:
            count_invoice = 0
            authorization = invoice.sri_authorization_id
            for line in invoice.invoice_line_ids:
                register = []
                register.append("F" if invoice.type == 'out_invoice' else "N")  # Tipo
                register.append(authorization.establishment)  # Establecimiento
                register.append(authorization.emission_point)  # P. Emisión
                register.append(invoice.reference)  # Secuencial
                register.append(datetime.strptime(invoice.date_invoice, "%Y-%m-%d"))  # Fecha
                register.append(invoice.withhold_number if invoice.withhold_number else "-")  # No. Retención
                register.append(line.name)  # Descripción
                register.append(invoice.partner_id.name)  # Cliente
                register.append(invoice.partner_id.documentation_number)  # No. Documento
                register.append(authorization.authorization)  # Autorización
                register.append(invoice.tax_support_id.code if invoice.tax_support_id else "-")  # S. Tributario
                register.append(0.00)  # Base iva (11)
                register.append(0.00)  # Base 0
                register.append(0.00)  # ICE
                register.append(0.00)  # Base no iva
                register.append("-")  # C. Renta
                register.append("-")  # P. Renta
                register.append(0.00)  # Monto renta
                register.append(invoice.amount_tax if count_invoice == 0 else 0.00)  # R. Base I.
                register.append("-")  # C. Iva
                register.append("-")  # P. Iva
                register.append(0.00)  # Valor iva
                register.append(0.00)  # Total de factura
                data.append(register)
                count_invoice = 1
                if len(line.invoice_line_tax_ids) == 0:
                    data[-1][14] = line.price_subtotal
                else:
                    for tax in line.invoice_line_tax_ids:
                        if tax.amount > 0:
                            data[-1][11] = line.price_subtotal
                        if tax.amount == 0:
                            data[-1][12] = line.price_subtotal
            rent = []
            iva = []
            for line in invoice.withhold_id.lines_withhold:
                if line.retention_type == 'rent':
                    rent.append(line)
                if line.retention_type == 'iva':
                    iva.append(line)
            count = -1
            for r in rent:
                data[count][15] = r.tax_id.code if r.tax_id.code else "-"
                data[count][16] = str(int(r.tax_id.amount)) + '%' if r.tax_id.amount else "-"
                data[count][17] = r.amount
                count = count - 1
            count = -1
            for i in iva:
                data[count][19] = i.tax_id.code if i.tax_id.code else "-"
                data[count][20] = str(int(i.tax_id.amount)) + '%' if i.tax_id.amount else "-"
                data[count][21] = i.amount
                count = count - 1
            data[-1][22] = invoice.amount_total
        return data

    def _get_lines_purchases(self, context):
        """
        Obtenemos todas las líneas facturadas de compras con sus valores de retención
        :param context:
        :return: list
        """
        data = []
        arg = []
        arg.append(('date_invoice', '>=', context.start_date))
        arg.append(('date_invoice', '<=', context.end_date))
        arg.append(('state', 'not in', ('draft', 'cancel')))
        arg.append(('type', 'in', ('in_invoice', 'in_refund')))
        invoices = self.env['account.invoice'].search(arg)
        count = 0
        for invoice in invoices:
            count_invoice = 0
            authorization = invoice.authorization
            establishment = invoice.establishment
            emission_point = invoice.emission_point
            type = ""
            if invoice.type == 'in_refund':
                type = "NC"
            elif invoice.type == 'in_invoice':
                type = "F"
            else:
                type = "N"                
            for line in invoice.invoice_line_ids:
                register = []
                register.append(type)  # Tipo
                register.append(establishment)  # Establecimiento
                register.append(emission_point)  # P. Emisión
                register.append(invoice.reference)  # Secuencial
                register.append(datetime.strptime(invoice.date_invoice, "%Y-%m-%d"))  # Fecha
                register.append(invoice.withhold_number if invoice.withhold_number else "-")  # No. Retención
                register.append(line.name)  # Descripción
                register.append(invoice.partner_id.name)  # Proveedor
                register.append(invoice.partner_id.documentation_number)  # No. Documento
                register.append(authorization)  # Autorización
                register.append(invoice.tax_support_id.code if invoice.tax_support_id else "-")  # S. Tributario
                register.append(0.00)  # Base iva (11)
                register.append(0.00)  # Base 0
                register.append(0.00)  # ICE
                register.append(0.00)  # Base no iva
                register.append("-")  # C. Renta
                register.append("-")  # P. Renta
                register.append(0.00)  # Monto renta
                invoice_tax = 0
                if count_invoice == 0:
                    invoice_tax = -1 * invoice.amount_tax if invoice.type == 'in_refund' else invoice.amount_tax
                register.append(invoice_tax)  # R. Base I.
                register.append("-")  # C. Iva
                register.append("-")  # P. Iva
                register.append(0.00)  # Valor iva
                register.append(0.00)  # Total de factura
                data.append(register)
                count_invoice = 1
                if len(line.invoice_line_tax_ids) == 0:
                    data[-1][14] = -1 * line.price_subtotal if invoice.type == 'in_refund' else line.price_subtotal
                else:
                    for tax in line.invoice_line_tax_ids:
                        if tax.amount > 0:
                            data[-1][11] = -1 * line.price_subtotal if invoice.type == 'in_refund' else line.price_subtotal
                        if tax.amount == 0:
                            data[-1][12] = -1 * line.price_subtotal if invoice.type == 'in_refund' else line.price_subtotal
            rent = []
            iva = []
            for line in invoice.withhold_id.lines_withhold:
                if line.retention_type == 'rent':
                    rent.append(line)
                if line.retention_type == 'iva':
                    iva.append(line)
            if len(rent) == 2:
                register = []
                register.append(type)  # Tipo
                register.append(establishment)  # Establecimiento
                register.append(emission_point)  # P. Emisión
                register.append(invoice.reference)  # Secuencial
                register.append(datetime.strptime(invoice.date_invoice, "%Y-%m-%d"))  # Fecha
                register.append(invoice.withhold_number if invoice.withhold_number else "-")  # No. Retención
                register.append(line.name)  # Descripción
                register.append(invoice.partner_id.name)  # Cliente
                register.append(invoice.partner_id.documentation_number)  # No. Documento
                register.append(authorization)  # Autorización
                register.append(invoice.tax_support_id.code if invoice.tax_support_id else "-")  # S. Tributario
                register.append(0.00)  # Base iva (11)
                register.append(0.00)  # Base 0
                register.append(0.00)  # ICE
                register.append(0.00)  # Base no iva
                register.append("-")  # C. Renta
                register.append("-")  # P. Renta
                register.append(0.00)  # Monto renta
                register.append(0.00)  # R. Base I.
                register.append("-")  # C. Iva
                register.append("-")  # P. Iva
                register.append(0.00)  # Valor iva
                register.append(0.00)  # Total de factura
                data.append(register)
            count = -1
            for r in rent:
                data[count][15] = r.tax_id.code if r.tax_id.code else "-"
                data[count][16] = str(int(r.tax_id.amount)) + '%' if r.tax_id.amount else "-"
                data[count][17] = r.amount if invoice.state != 'cancel' else 0.00
                count = count - 1
                if not RETENTIONS:  # No existe retenciones (código) se crea
                    RETENTIONS.append({
                        'code': r.tax_id.code,
                        'name': r.tax_id.name,
                        'subtotal': r.base_taxable if invoice.state != 'cancel' else 0.00,
                        'amount': r.amount if invoice.state != 'cancel' else 0.00,
                        'type': "rent"
                    })
                else:
                    flag = any(x['code'] == r.tax_id.code for x in RETENTIONS)
                    if flag:  # Si existe código  actualizamso monto
                        index = list(map(lambda x: x['code'], RETENTIONS)).index(r.tax_id.code)
                        RETENTIONS[index]['amount'] = RETENTIONS[index]['amount'] + (
                            r.amount if invoice.state != 'cancel' else 0.00)
                        RETENTIONS[index]['subtotal'] = RETENTIONS[index]['subtotal'] + (
                            r.base_taxable if invoice.state != 'cancel' else 0.00)
                    else:
                        RETENTIONS.append({
                            'code': r.tax_id.code,
                            'name': r.tax_id.name,
                            'subtotal': r.base_taxable if invoice.state != 'cancel' else 0.00,
                            'amount': r.amount if invoice.state != 'cancel' else 0.00,
                            'type': "rent"
                        })
            count = -1
            for i in iva:
                data[count][19] = i.tax_id.code if i.tax_id.code else "-"
                data[count][20] = str(int(i.tax_id.amount)) + '%' if i.tax_id.amount else "-"
                data[count][21] = i.amount
                count = count - 1
                if not RETENTIONS:  # No existe retenciones (código) se crea
                    RETENTIONS.append({
                        'code': i.tax_id.code,
                        'name': i.tax_id.name,
                        'subtotal': i.base_taxable if invoice.state != 'cancel' else 0.00,
                        'amount': i.amount if invoice.state != 'cancel' else 0.00,
                        'type': "iva"
                    })
                else:
                    flag = any(x['code'] == i.tax_id.code for x in RETENTIONS)
                    if flag:  # Si existe código  actualizamos monto
                        index = list(map(lambda x: x['code'], RETENTIONS)).index(i.tax_id.code)
                        RETENTIONS[index]['amount'] = RETENTIONS[index]['amount'] + (
                            i.amount if invoice.state != 'cancel' else 0.00)
                        RETENTIONS[index]['subtotal'] = RETENTIONS[index]['subtotal'] + (
                            i.base_taxable if invoice.state != 'cancel' else 0.00)
                    else:
                        RETENTIONS.append({
                            'code': i.tax_id.code,
                            'name': i.tax_id.name,
                            'subtotal': i.base_taxable if invoice.state != 'cancel' else 0.00,
                            'amount': i.amount if invoice.state != 'cancel' else 0.00,
                            'type': "iva"
                        })
            data[-1][22] = -1 * invoice.amount_total if invoice.type == 'in_refund' else invoice.amount_total
        return data

    def _get_last(self, start_date):
        month = start_date.month - 1
        year = start_date.year
        if month == 0:  # Mes de enero
            month = 12
            year = year - 1
        return month, year

    def _set_tributary_credit(self, tributary_credit, period, amount_iva, amount_rent):
        """
        Crédito tributario registro
        :param data:
        :return:
        """
        # Si no existe lo creamos con nuevos datos
        if not tributary_credit:
            self.env['eliterp.tributary.credit'].create({
                'name': period.id,
                'amount_iva': amount_iva,
                'amount_rent': amount_rent,
            })
        # Si existe la actualizó
        else:
            tributary_credit.update({
                'amount_iva': amount_iva,
                'amount_rent': amount_rent
            })

    def generate_xlsx_report(self, workbook, data, context):
        # Verificar exista período
        start_date = datetime.strptime(context.start_date, "%Y-%m-%d")
        month, year = self._get_last(start_date)  # Último mes y año
        year_accounting = self.env['eliterp.account.period'].search([('year_accounting', '=', start_date.year)])
        if not year_accounting:
            return
        period_id = year_accounting.lines_period.filtered(lambda x: x.code == start_date.month)
        global RETENTIONS  # Variable global para suma total de retenciones por código
        RETENTIONS = []
        sales = self._get_lines_sales(context)  # Lista de factura de ventas
        purchases = self._get_lines_purchases(context)  # Lista de factura de compras
        sheet = workbook.add_worksheet('103-104')
        # Formatos
        bold = workbook.add_format({'bold': 1})
        title = workbook.add_format({
            'bold': True,
            'align': 'center',
            'border': 1
        })
        heading = workbook.add_format({
            'bold': True,
            'bg_color': '#D3D3D3',
            'align': 'center',
            'border': 1
        })
        # Formatos de celda
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yy'})
        sheet.write('A1', 'ANEXO DE DECLARACIÓN 103, 104', title)
        sheet.write('A3', 'COMPRAS', heading)
        columns = [
            'TIPO', 'EST.', 'P. EMI.', 'SEC.', 'FECHA', '# RET.', 'DESCRIPCIÓN', 'RAZÓN SOCIAL',
            '# DOCUMENTO', 'AUTORIZACIÓN', 'S. TRI.', 'B. IVA', 'B. CERO', 'ICE', 'B. NO IVA',
            'C. RENTA', 'P. RENTA', 'MONTO R.', 'R. BASE IVA', 'C. IVA', 'P. IVA', 'MONTO I.', 'TOTAL'
        ]
        row = 4
        col = 0
        sum_columns = (
            ['L', 11], ['M', 12], ['N', 13], ['O', 14],
            ['R', 17], ['S', 18], ['V', 21], ['W', 22]
        )  # Variable par sumar columnas
        """
            COMRPAS
        """
        for column in columns:
            sheet.write(row, col, column, bold)
            col += 1
        row += 1
        for line in purchases:
            col = 0
            for column in line:
                if isinstance(column, str):
                    sheet.write(row, col, column)
                elif isinstance(column, datetime):
                    sheet.write(row, col, column, date_format)
                else:
                    sheet.write(row, col, column, money_format)
                col += 1
            row += 1
        sheet.write(row, 10, 'Totales', bold)
        for l, c in sum_columns:
            sum_purchases = '=SUM(%s6:%s%s)' % (l, l, str(row))  # Sumar columnas
            sheet.write(row, c, sum_purchases, money_format)
        """
            VENTAS
        """
        row += 2
        col = 0
        sheet.write('A%s' % str(row), 'VENTAS', heading)
        row += 1
        for column in columns:
            sheet.write(row, col, column, bold)
            col += 1
        row += 1
        sum_row = row + 1
        for line in sales:
            col = 0
            for column in line:
                if isinstance(column, str):
                    sheet.write(row, col, column)
                elif isinstance(column, datetime):
                    sheet.write(row, col, column, date_format)
                else:
                    sheet.write(row, col, column, money_format)
                col += 1
            row += 1
        sheet.write(row, 10, 'Totales', bold)
        for l, c in sum_columns:
            sum_sales = '=SUM(%s%s:%s%s)' % (l, str(sum_row), l, str(row))  # Sumar columnas
            sheet.write(row, c, sum_sales, money_format)
        """
             RENTA/IVA
        """
        row += 2
        col = 0
        sheet.write('A%s' % str(row), 'CÓDIGO DE RENTENCIÓN', heading)
        row += 1
        columns_ = [
            'CÓDIGO', 'NOMBRE', 'TOTAL'
        ]
        for column in columns_:
            sheet.write(row, col, column, bold)
            col += 1
        row += 1
        sum_row = row + 1
        data = []
        for line in RETENTIONS:
            register = []
            if float_is_zero(line['amount'], precision_rounding=3):
                continue
            register.append(line['code'])
            register.append(line['name'][:10] + '...')
            register.append(line['amount'])
            data.append(register)
        for line in data:
            col = 0
            for column in line:
                if isinstance(column, str):
                    sheet.write(row, col, column)
                else:
                    sheet.write(row, col, column, money_format)
                col += 1
            row += 1
        sum_retentions = '=SUM(C%s:C%s)' % (str(sum_row), str(row))
        sheet.write(row, 2, sum_retentions, money_format)
        # Operaciones de crédito tributario
        last_tributary_credit = self.env['eliterp.tributary.credit'].search(
            [('month', '=', month), ('year', '=', year)])
        amount_iva = 0.00
        amount_rent = 0.00
        if last_tributary_credit:
            amount_iva = last_tributary_credit.amount_iva
            amount_rent = last_tributary_credit.amount_rent
        new_tributary_credit = self.env['eliterp.tributary.credit'].search(
            [('month', '=', start_date.month), ('year', '=', start_date.year)])
        total_iva = 0.00
        total_rent = 0.00
        total_iva_month = 0.00
        subtraction_iva = sum(line[18] for line in sales) - sum(line[18] for line in purchases)
        # 1
        if subtraction_iva <= 0:
            total_iva = subtraction_iva
            total_iva_month = sum(line[21] for line in purchases)
        # 2
        elif subtraction_iva > 0:
            total_iva = subtraction_iva - amount_iva + sum(line[21] for line in purchases)
            total_iva_month = total_iva
            total_iva = 0.00
        # 3
        elif amount_iva == 0:
            total_iva = subtraction_iva + sum(line[21] for line in purchases) - amount_rent
            total_iva_month = total_iva
            total_iva = 0.00
            total_rent = 0.00
        else:
            total_rent = amount_rent - sum(line[21] for line in sales)
        self._set_tributary_credit(new_tributary_credit, period_id, amount_iva, amount_rent)
        total_pay = 0.00
        total_pay = sum(line[17] for line in sales) - total_iva_month


class Taxes103104Report(models.TransientModel):
    _name = 'eliterp.taxes.103.104.report'

    _description = "Ventana para reporte de impuestos (103, 104)"

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_taxes_103_104_xlsx').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True)


class BillsReportXlsx(models.AbstractModel):
    _name = 'report.eliterp_accounting.eliterp_report_bills_xlsx'

    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_accounting.eliterp_report_bills']._get_lines(context)
        sheet = workbook.add_worksheet('Facturas')
        # Formatos
        money_format = workbook.add_format({'num_format': '$ #,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        bold = workbook.add_format({'bold': 1})
        # Datos
        sheet.autofilter('B3:L3')
        sheet.merge_range('A1:L1', 'REPORTE DE FACTURAS', title)
        sheet.write(2, 0, "FECHA", bold)
        sheet.write(2, 1, "ESTADO", bold)
        sheet.write(2, 2, "EMPRESA", bold)
        sheet.write(2, 3, "NO. FACTURA", bold)
        sheet.write(2, 4, "NO. RETENCIÓN", bold)
        sheet.write(2, 5, "SUBTOTAL", bold)
        sheet.write(2, 6, "BASE 0%", bold)
        sheet.write(2, 7, "BASE IVA", bold)
        sheet.write(2, 8, "TOTAL A RETENER", bold)
        sheet.write(2, 9, "TOTAL", bold)
        sheet.write(2, 10, "SALDO", bold)
        sheet.write(2, 11, "COBROS", bold)
        row = 3
        col = 0
        if data:
            for r in data[0]['rows']:
                sheet.write(row, col, r['date'])
                sheet.write(row, col + 1, r['state'], date_format)
                sheet.write(row, col + 2, r['partner'])
                sheet.write(row, col + 3, r['invoice_number'])
                sheet.write(row, col + 4, r['retention'])
                sheet.write(row, col + 5, r['subtotal'], money_format)
                sheet.write(row, col + 6, r['subtotal_zero'], money_format)
                sheet.write(row, col + 7, r['iva'], money_format)
                sheet.write(row, col + 8, r['amount_retention'], money_format)
                sheet.write(row, col + 9, r['total'], money_format)
                sheet.write(row, col + 10, r['residual'], money_format)
                sheet.write(row, col + 11, r['amount_payments'], money_format)
                row += 1


class BillsReportPdf(models.AbstractModel):
    _name = 'report.eliterp_accounting.eliterp_report_bills'

    @staticmethod
    def _get_state(s):
        if s == 'open':
            return 'Por pagar'
        else:
            return 'Pagada'

    def _get_payments(self, invoice):
        pays = invoice._get_payments_vals()
        amount = 0.00
        for pay in filter(lambda x: not x['journal_name'] == 'Retención en venta', pays):
            amount += pay['amount']
        return amount

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = []
        arg.append(('date_invoice', '>=', doc.start_date))
        arg.append(('date_invoice', '<=', doc.end_date))
        arg.append(('state', 'in', ['open', 'paid']))
        if doc.type_report != 'all':
            arg.append(('type', '=', doc.type_report))
        if doc.partner:
            arg.append(('partner_id', '=', doc.partner.id))
        invoices = self.env['account.invoice'].search(arg)
        order_invoices = sorted(invoices, key=lambda x: x.type)
        for type, records in groupby(order_invoices, key=lambda x: x.type):
            rows = []
            for r in records:
                rows.append({
                    'date': r.date_invoice,
                    'partner': r.partner_id.name,
                    'invoice_number': r.invoice_number,
                    'retention': r.withhold_number if r.withhold_id else '-',
                    'subtotal': r.amount_untaxed if r.amount_tax > 0 else 0.00,
                    'subtotal_zero': r.base_zero_iva if r.amount_tax <= 0 else 0.00,
                    'iva': r.amount_tax,
                    'amount_retention': r.amount_retention,
                    'total': r.amount_total,
                    'residual': r.residual,
                    'amount_payments': self._get_payments(r),
                    'state': self._get_state(r.state)
                })
            data.append({
                'type': 'Ventas' if type == 'out_invoice' else 'Compras',
                'rows': sorted(rows, key=lambda x: x['date'])
            })

        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.bills.report',
            'docs': self.env['eliterp.bills.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class BillsReport(models.TransientModel):
    _name = 'eliterp.bills.report'

    _description = "Ventana para reporte de facturas"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_bills').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_bills_xlsx').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True)
    partner = fields.Many2one('res.partner', string='Empresa', domain=[('is_contact', '=', False)])
    type_report = fields.Selection([
        ('all', 'Todos'),
        ('out_invoice', 'Ventas'),
        ('in_invoice', 'Compras'),
    ], default='all', string='Tipo', required=True)
