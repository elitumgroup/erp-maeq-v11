# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from collections import defaultdict
import pytz
from datetime import time, datetime, timedelta
from odoo import api, fields, models
import math
from itertools import groupby


class EmployeeReportPdf(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_report_employee_report'

    @staticmethod
    def _get_civil_status(civil_status):
        """
        Estado civil en español
        :param civil_status:
        :return: string
        """
        if civil_status == 'single':
            return "Soltero(a)"
        if civil_status == 'married':
            return "Casado(a)"
        if civil_status == 'widower':
            return "Viudo(a)"
        if civil_status == 'divorced':
            return "Divorciado(a)"
        return '-'

    def _get_last_gang(self, employee):
        last_cmc = self.env['eliterp.cmc'].search([
            ('operator', '=', employee),
            ('state', '=', 'validate'),
            '|',
            ('assistant', '=', employee),
            ('state', '=', 'validate')
        ], order='id desc', limit=1)
        if last_cmc:
            return last_cmc.gang_id.name
        else:
            return '-'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = []
        arg.append(('admission_date', '>=', doc.start_date))
        arg.append(('admission_date', '<=', doc.end_date))
        if doc.type == 'all':  # Hacemos esto porqué no coje empleados archivados
            _arg = []
            _arg.append(('admission_date', '>=', doc.start_date))
            _arg.append(('admission_date', '<=', doc.end_date))
            _arg.append(('active', '=', False))
            employees = self.env['hr.employee'].search(arg) | self.env['hr.employee'].search(_arg)
        else:
            arg.append(('active', '=', True if doc.type == 'active' else False))
            employees = self.env['hr.employee'].search(arg)
        count = 0
        if doc.structure_ids:
            employees_ = employees.filtered(lambda x: x.struct_id.id in doc.structure_ids._ids)
        else:
            employees_ = employees
        for employee in employees_:
            if employee.id == 1:  # Empleado Administrado no va
                continue
            count += 1
            data.append({
                'number': count,
                'name': employee.name,
                'identification_id': employee.identification_id,
                'age': employee.age if employee.birthday else '-',
                'civil_status': self._get_civil_status(employee.marital),
                'admission_date': employee.admission_date,
                'departure_date': employee.departure_date if employee.departure_date else '-',
                'gang_id': self._get_last_gang(employee.id),
                'job_id': employee.job_id.name,
                'benefits': 'Sí' if employee.benefits == 'yes' else 'No',
                'wage': employee.wage,
                'status': 'Activo' if employee.active else 'Inactivo',
                'struct_id': employee.struct_id.code if employee.struct_id else '-',
                'bank_account': employee.bank_account if employee.bank_account else 'No tiene'
            })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.employee.report',
            'docs': self.env['eliterp.employee.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class EmployeeReportXlsx(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_report_employee_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_hr.eliterp_report_employee_report']._get_lines(context)
        sheet = workbook.add_worksheet('Reporte de empleado')
        # Formatos
        money_format = workbook.add_format({'num_format': '$ #,##0.00'})
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        bold = workbook.add_format({'bold': 1})
        # Columnas
        sheet.set_column("A:A", 4)
        sheet.set_column("B:B", 40)
        sheet.set_column("C:C", 11)
        sheet.set_column("D:D", 5.20)
        sheet.set_column("E:E", 13)
        sheet.set_column("F:F", 10)
        sheet.set_column("G:G", 10)
        sheet.set_column("H:H", 16)
        sheet.set_column("I:I", 16)
        sheet.set_column("J:J", 11.86)
        sheet.set_column("K:K", 9)
        sheet.set_column("L:L", 12)
        sheet.set_column("M:M", 11)
        # Filas
        # Datos
        sheet.autofilter('B3:M3')
        sheet.merge_range('A1:M1', 'REPORTE DE EMPLEADOS', title)
        sheet.write(2, 0, "Nº", bold)
        sheet.write(2, 1, "NOMBRES", bold)
        sheet.write(2, 2, "CÉDULA", bold)
        sheet.write(2, 3, "EDAD", bold)
        sheet.write(2, 4, "ESTADO CIVIL", bold)
        sheet.write(2, 5, "F. INGRESO", bold)
        sheet.write(2, 6, "F. SALIDA", bold)
        sheet.write(2, 7, "CUADRILLA", bold)
        sheet.write(2, 8, "CARGO", bold)
        sheet.write(2, 9, "A. BENEFICIO", bold)
        sheet.write(2, 10, "SUELDO", bold)
        sheet.write(2, 11, "C. BANCARIA", bold)
        sheet.write(2, 12, "E. SALARIAL", bold)
        row = 3
        col = 0
        cont = 1
        for r in data:
            sheet.write(row, col, cont)
            sheet.write(row, col + 1, r['name'])
            sheet.write(row, col + 2, r['identification_id'])
            sheet.write(row, col + 3, r['age'])
            sheet.write(row, col + 4, r['civil_status'])
            sheet.write(row, col + 5, r['admission_date'], date_format)
            sheet.write(row, col + 6, r['departure_date'], date_format)
            sheet.write(row, col + 7, r['gang_id'])
            sheet.write(row, col + 8, r['job_id'])
            sheet.write(row, col + 9, r['benefits'])
            sheet.write(row, col + 10, r['wage'], money_format)
            sheet.write(row, col + 11, r['bank_account'])
            sheet.write(row, col + 12, r['struct_id'])
            row += 1
            cont += 1


class EmployeeReport(models.TransientModel):
    _name = 'eliterp.employee.report'

    _description = "Ventana para reporte de empleados"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_employee_report').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_employee_xlsx').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    structure_ids = fields.Many2many("hr.payroll.structure", string='Estructuras salariales')
    type = fields.Selection([
        ('all', 'Todos'),
        ('active', 'Activos'),
        ('not active', 'Inactivos')
    ], default='all', string='Tipo', required=True)


class AttendanceReportPdf(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_report_attendance_report'

    @staticmethod
    def float_to_time(float_hour):
        """
        Transformamos de flotante a tiempo
        :param float_hour:
        :return: time
        """
        return time(int(math.modf(float_hour)[1]), int(60 * math.modf(float_hour)[0]), 0)

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data_base = []
        data = []
        arg = []
        arg.append(('date', '>=', doc.start_date))
        arg.append(('date', '<=', doc.end_date))
        arg.append(('state', '=', 'validate'))
        attendances = self.env['eliterp.attendance'].search(arg)
        for attendance_ in attendances:
            for attendance in attendance_.lines_employee:
                data_base.append({
                    'employee_id': attendance.employee_id.id,
                    'employee': attendance.employee_id.name,
                    'date': attendance.attendance_id.date,
                    'in': self.float_to_time(attendance.check_in_am),
                    'out': self.float_to_time(attendance.check_out_pm),
                    'comments': attendance.news or '-'
                })
        if not doc.type_employees == 'all':
            data_base = filter(lambda x: x['employee_id'] == doc.employee_id.id, data_base)
        data_base = sorted(data_base,
                           key=lambda x: (x['employee'], x['date']))  # Ordenamos por empleado y fecha de inicio
        for line in data_base:
            data.append({
                'employee': line['employee'],
                'date': line['date'],
                'in': line['in'],
                'out': line['out'],
                'comments': line['comments']
            })

        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.attendance.report',
            'docs': self.env['eliterp.attendance.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class AttendanceReport(models.TransientModel):
    _name = 'eliterp.attendance.report'

    _description = 'Ventana para reporte de asistencias'

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_attendance_report').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en EXCEL
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_attendance_xlsx').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    type_employees = fields.Selection([('all', 'Todos'), ('one', 'Empleado')], string='Tipo', default='all')
    employee_id = fields.Many2one('hr.employee', string='Empleado')


class AttendanceReportExcel(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_action_report_attendance_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_hr.eliterp_report_attendance_report']._get_lines(context)
        sheet = workbook.add_worksheet('Asistencia')
        # Formatos
        center_format = workbook.add_format({'align': 'center'})
        _right_format = workbook.add_format({'align': 'right', 'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        hora_format = workbook.add_format({'num_format': 'hh:mm'})

        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
        # Columnas
        sheet.set_column("A:A", 40)
        sheet.set_column("B:B", 15)
        sheet.set_column("C:C", 8)
        sheet.set_column("D:D", 8)
        sheet.set_column("E:E", 15)
        # Filas
        sheet.set_default_row(15)
        # Datos
        sheet.merge_range('A1:E2', 'Asistencia', title)
        sheet.autofilter('A3:E3')
        sheet.write(2, 0, "EMPLEADO")
        sheet.write(2, 1, "FECHA")
        sheet.write(2, 2, "ENTRADA")
        sheet.write(2, 3, "SALIDA")
        sheet.write(2, 4, "NOVEDAD")
        row = 3
        for r in data:
            sheet.write(row, 0, r['employee'])
            sheet.write(row, 1, r['date'], date_format)
            sheet.write(row, 2, r['in'], hora_format)
            sheet.write(row, 3, r['out'], hora_format)
            sheet.write(row, 4, r['comments'])
            row += 1


class ReportAbsencesPdf(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_report_report_absences'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = []
        arg.append(('state', '=', 'validate'))
        arg.append(('holiday_type', '=', 'employee'))
        arg.append(('date_from', '>=', doc.start_date))
        arg.append(('date_from', '<=', doc.end_date))
        if doc.type_absences != 'all':
            arg.append(('holiday_status_id', '=', doc.holidays_status_id.id))
        if doc.type_employees != 'all':
            arg.append(('employee_id', '=', doc.employee_id.id))
        absences = self.env['hr.holidays'].search(arg)
        for line in absences:
            data.append({
                'employee': line.employee_id.name,
                'holiday': line.name,
                'color': line.holiday_status_id.color_name,
                'date_from': line.date_from[:10],
                'date_to': line.date_to,
                'days': str(int(line.number_of_days_temp)),
                'report_note': line.report_note if line.report_note else '-'
            })
        data = sorted(data,
                      key=lambda x: (x['employee'], x['date_from']))  # Ordenamos por empleado y fecha de inicio
        # Buscamos las ausencias de Nómina
        absences_category = self.env['hr.holidays'].search([
            ('state', '=', 'validate'),
            ('date_from', '>=', doc.start_date),
            ('date_from', '<=', doc.end_date),
            ('holiday_type', '=', 'category')
        ])
        for line in absences_category:
            data.append({
                'employee': line.employee_id.name,
                'holiday': line.name,
                'color': line.holiday_status_id.color_name,
                'date_from': line.date_from[:10],
                'date_to': line.date_to,
                'days': str(int(line.number_of_days_temp)),
                'report_note': line.report_note if line.report_note else '-'
            })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.report.absences',
            'docs': self.env['eliterp.report.absences'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class ReportAbsences(models.TransientModel):
    _name = 'eliterp.report.absences'

    _description = 'Ventana para reporte de ausencias'

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_report_absences').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en EXCEL
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_absences_xlsx').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    type_employees = fields.Selection([('all', 'Todos'), ('one', 'Empleado')], string='Tipo', default='all')
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    type_absences = fields.Selection([('all', 'Todas'), ('one', 'Asusencia')], string='Tipo de ausencias',
                                     default='all')
    holidays_status_id = fields.Many2one('hr.holidays.status', string='Ausencia')


class ReportAbsencesExcel(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_action_report_absences_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_hr.eliterp_report_report_absences']._get_lines(context)
        sheet = workbook.add_worksheet('Ausencias')
        # Formatos
        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
        header = workbook.add_format({
            'bold': True,
            'align': 'center'
        })
        # Columnas
        sheet.set_column("A:A", 50)
        sheet.set_column("B:B", 25)
        sheet.set_column("C:C", 15)
        sheet.set_column("D:D", 8)
        sheet.set_column("E:E", 35)
        # Filas
        sheet.set_default_row(15)
        # Filtros
        sheet.autofilter('A3:B3')
        # Datos
        sheet.merge_range('A1:F2', 'REPORTE DE AUSENCIAS', title)
        sheet.write(2, 0, "EMPLEADO", header)
        sheet.write(2, 1, "TIPO DE AUSENCIA", header)
        sheet.write(2, 2, "FECHA NOVEDAD", header)
        sheet.write(2, 3, "DÍA(S)", header)
        sheet.write(2, 4, "NOTAS", header)
        row = 3
        for r in data:
            sheet.write(row, 0, r['employee'])
            sheet.write(row, 1, r['holiday'])
            sheet.write(row, 2, r['date_from'])
            sheet.write(row, 3, r['days'])
            sheet.write(row, 4, r['report_note'])
            row += 1


class HolidayReportPdf(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_reprt_holiday_report'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = [('admission_date', '>=', doc['start_date']), ('admission_date', '<=', doc['end_date'])]
        if doc['type_report'] != 'all':
            arg.append(('id', '=', doc['employee_id'].id))
        for employee in self.env['hr.employee'].search(arg).sorted(key=lambda r: r.name):
            vacations_taken = employee.days_taken
            lines = self.env['hr.holidays']._get_lines_vacations(employee)
            data.append({
                'name': employee.name,
                'admission_date': employee.admission_date,
                'holidays': lines
            })
            for line in lines:
                if vacations_taken != 0:
                    if vacations_taken == line['vacations_generated']:
                        line.update({
                            'vacations_taken': vacations_taken,
                            'vacations_available': 0
                        })
                        vacations_taken = 0
                        continue
                    if vacations_taken - line['vacations_generated'] > 0:
                        line.update({
                            'vacations_taken': line['vacations_generated'],
                            'vacations_available': 0
                        })
                        vacations_taken = vacations_taken - line['vacations_generated']
                        continue
                    if vacations_taken - line['vacations_generated'] < 0:
                        line.update({
                            'vacations_taken': vacations_taken,
                            'vacations_available': abs(vacations_taken - line['vacations_generated'])
                        })
                        vacations_taken = 0
                        continue
                if vacations_taken == 0:
                    line.update({
                        'vacations_taken': 0,
                        'vacations_available': line['vacations_generated']
                    })
            if vacations_taken != 0:
                lines[-1].update(
                    {'vacations_available': lines[-1]['vacations_generated'] - vacations_taken})
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.holiday.report',
            'docs': self.env['eliterp.holiday.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class HolidayReport(models.TransientModel):
    _name = 'eliterp.holiday.report'

    _description = 'Ventana para reporte de vacaciones del personal'

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_holiday_report').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en EXCEL
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_holiday_xlsx').report_action(self)

    type_report = fields.Selection([('all', 'Todos'), ('one', 'Empleado')], string='Tipo de reporte', default='all')
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)


class HolidayReportExcel(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_action_report_holiday_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_hr.eliterp_reprt_holiday_report']._get_lines(context)
        sheet = workbook.add_worksheet('Vacaciones')
        # Formatos
        _right_format = workbook.add_format({'align': 'right', 'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
        title2 = workbook.add_format({
            'bold': True,
            'color': 'red'
        })
        # Columnas
        sheet.set_column("A:A", 40)
        sheet.set_column("B:B", 15)
        sheet.set_column("C:C", 8)
        sheet.set_column("D:D", 8)
        sheet.set_column("E:E", 15)
        # Filas
        sheet.set_default_row(15)
        # Datos
        sheet.merge_range('A1:D2', 'VACACIONES', title)
        row = 2
        for r in data:
            sheet.write(row, 0, "EMPLEADO", title2)
            sheet.write(row, 1, "FECHA DE INGRESO", title2)
            row += 1
            sheet.write(row, 0, r['name'])
            sheet.write(row, 1, r['admission_date'])
            row += 1
            for v in r['holidays']:
                sheet.write(row, 0, "PERÍODO")
                sheet.write(row, 1, "GENERADAS")
                sheet.write(row, 2, "GOZADAS")
                sheet.write(row, 3, "DISPONIBLES")
                row += 1
                sheet.write(row, 0, v['period'])
                sheet.write(row, 1, v['vacations_generated'])
                sheet.write(row, 2, v['vacations_taken'])
                sheet.write(row, 3, v['vacations_available'])
                row += 1


class ExtraHourReportPdf(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_reprt_extra_hour_report'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = []
        arg.append(('date', '>=', doc['start_date']))
        arg.append(('date', '<=', doc['end_date']))
        if doc.employee_id:
            arg.append(('name', 'in', doc.employee_id.ids))
        record_overtime = self.env['eliterp.record.overtime'].search(arg)
        if doc.type_report == 'all':
            for record_overtime_ in record_overtime:
                if record_overtime_.name.active:
                    if record_overtime_.name.struct_id.id in doc.structure_ids.ids:
                        data.append({
                            'employee': record_overtime_.name.name,
                            'additional_hours': record_overtime_.additional_hours,
                            'total_hours': record_overtime_.total_additional_hours,
                            'date': record_overtime_.date,
                        })
        else:
            ro = record_overtime.filtered(lambda x: x.name.active and x.name.struct_id.id in doc.structure_ids._ids)
            record_overtime_ = ro.sorted(key=lambda r: r.name.name)
            for name, records in groupby(record_overtime_, key=lambda x: x.name.name):
                list_records = list(records)
                data.append({
                    'employee': name,
                    'additional_hours': sum(r.additional_hours for r in list_records),
                    'total_hours': sum(r.total_additional_hours for r in list_records),
                    'date': False
                })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.extra_hour.report',
            'docs': self.env['eliterp.extra_hour.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class ExtraHourReport(models.TransientModel):
    _name = 'eliterp.extra_hour.report'

    _description = 'Ventana para reporte de hora extra'

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_extra_hour_xlsx').report_action(self)

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_extra_hour_report').report_action(self)

    type_report = fields.Selection([('one', 'Consolidado'), ('all', 'Detallado')], string='Tipo de reporte',
                                   default='all')
    employee_id = fields.Many2many('hr.employee', string='Empleados', help="Si se deja vacío, van todos los empleados.")
    structure_ids = fields.Many2many("hr.payroll.structure", string='Estructuras salariales')
    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)


class ExtraHourReportXlsx(models.AbstractModel):
    _name = 'report.eliterp_hr.eliterp_report_extra_hour_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_hr.eliterp_reprt_extra_hour_report']._get_lines(context)
        sheet = workbook.add_worksheet('Reporte de hora extra')
        # Formatos
        money_format = workbook.add_format({'num_format': '$ #,##0.00'})
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        bold = workbook.add_format({'bold': 1})
        # Columnas
        sheet.set_column("A:A", 4)
        sheet.set_column("B:B", 11)
        sheet.set_column("C:C", 40)
        sheet.set_column("D:D", 11.20)
        sheet.set_column("E:E", 11.20)
        # Filas
        # Datos
        sheet.autofilter('B3:E3')
        sheet.merge_range('A1:E1', 'REPORTE DE HORA EXTRA', title)
        sheet.write(2, 0, "Nº", bold)
        sheet.write(2, 1, "FECHA", bold)
        sheet.write(2, 2, "NOMBRE", bold)
        sheet.write(2, 3, "HORAS", bold)
        sheet.write(2, 4, "MONTO DE HORAS", bold)
        row = 3
        col = 0
        cont = 1
        for r in data:
            sheet.write(row, col, cont)
            sheet.write(row, col + 1, r['date'], date_format)
            sheet.write(row, col + 2, r['employee'])
            sheet.write(row, col + 3, r['additional_hours'])
            sheet.write(row, col + 4, r['total_hours'])
            row += 1
            cont += 1
