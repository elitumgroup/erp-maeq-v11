# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from datetime import datetime, timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HolidaysType(models.Model):
    _inherit = 'hr.holidays.status'

    description = fields.Char('Descripción')
    is_vacations = fields.Boolean('Es vacaciones?', default=False, help="Campo qué sirve para mostrar líneas de "
                                                                        "vacaciones en registros y calcular "
                                                                        "las mismas")


class LinesEmployeeCategory(models.Model):
    _name = 'eliterp.lines.employee.category'

    _description = 'Linea de empleados para etiqueta'

    employee_id = fields.Many2one('hr.employee', string="Empleado")
    admission_date = fields.Date('Fecha de ingreso', related='employee_id.admission_date')
    employee_category_id = fields.Many2one('hr.employee.category', string='Etiqueta de empleado')


class EmployeeCategory(models.Model):
    _inherit = 'hr.employee.category'

    description = fields.Char('Descripción')
    employee_ids = fields.One2many('eliterp.lines.employee.category', 'employee_category_id', string="Empleados")


class HolidayLines(models.Model):
    _name = 'eliterp.holiday.lines'

    _description = 'Líneas de vacaciones'

    employee = fields.Many2one('hr.employee', string='Empleado')
    period = fields.Char('Período')
    vacations_generated = fields.Integer('Generadas')
    vacations_taken = fields.Integer('Gozadas')
    vacations_available = fields.Integer('Por gozar')
    holiday_id = fields.Many2one('hr.holidays', 'De')


class Employee(models.Model):
    _inherit = 'hr.employee'

    @api.one
    def _get_days_taken(self):
        """
        Calculamos los días tomados de vacaciones por empleado
        """
        for record in self:
            holidays_type = self.env['hr.holidays.status'].search([('is_vacations', '=', 'True')])[0]
            # Soló vacaciones
            holidays = self.env['hr.holidays'].search([
                ('employee_id', '=', record.id),
                ('holiday_status_id', '=', holidays_type.id),
                ('state', '=', 'validate')
            ])
            days_taken = 0
            for line in holidays:
                if line.holiday_type == 'employee':
                    days_taken += line.number_of_days_temp
                else:  # Vacaciones por etiqueta de empleado
                    for line in line.category_id.line_employe_category:
                        if line.employee_id == record.id:
                            days_taken += line.number_of_days_temp
            self.days_taken = days_taken

    days_taken = fields.Integer('Días tomados', compute='_get_days_taken')


class Holidays(models.Model):
    _inherit = 'hr.holidays'
    _order = "employee_id asc, date_from desc"

    def _get_number_of_days(self, date_from, date_to, employee_id):
        """
        MM: Cambiamos para qué genere días por fechas, y no por horas
        """
        days = 0
        start_date = (fields.Datetime.from_string(date_from) - timedelta(hours=5)).date()
        end_date = (fields.Datetime.from_string(date_to) - timedelta(hours=5)).date()
        return int((end_date - start_date).days) + 1

    @api.one
    def action_refuse(self):
        """
        MM: Negamos la ausencia
        """
        return self.write({'state': 'refuse'})

    @api.one
    def action_cancel(self):
        """
        MM: Cancelamos la ausencia
        """
        return self.write({'state': 'cancel'})

    def _check_state_access_right(self, vals):
        """
        MM
        :param vals:
        :return: boolean
        """
        return True

    @api.constrains('state', 'number_of_days_temp', 'holiday_status_id')
    def _check_holidays(self):
        """
        MM
        """
        return True

    @api.multi
    def action_approve(self):
        """
        MM: Aprobamos al ausencia
        """
        return self.write({
            'approval_user': self.env.user.id,
            'state': 'validate1'
        })

    @api.one
    def action_validate(self):
        """
        MM: Validamos la ausencia
        """
        return self.write({'state': 'validate'})

    @api.onchange('holiday_status_id')
    def _onchange_holiday_status_id(self):
        """
        Actualizamos la descripción de la ausencia
        """
        self.name = self.holiday_status_id.description
        self.color_name = self.holiday_status_id.color_name

    @api.one
    def action_confirm(self):
        """
        MM: Solicitamos la aprobación
        """
        return self.write({
            'state': 'confirm'
        })

    @api.constrains('number_of_days_temp')
    def _check_number_of_days_temp(self):
        """
        Validamos qué vacaciones no sean mayores a las por gozar
        """
        if self.is_vacations and self.holiday_type == 'employee':
            total = 0
            for line in self.lines_vacations:
                total += line.vacations_available
            if self.number_of_days_temp > total:
                raise ValidationError("Duración de vacaciones a tomar mayores a las totales por gozar (%s)." % int(total))

    @staticmethod
    def _get_lines_vacations(employee):
        """
        Obtenemos las líneas de vacaciones por período
        :return: list
        """
        lines = []
        if not employee:
            return lines
        today = datetime.today().date()
        days = 0
        admission_date = datetime.strptime(employee.admission_date, "%Y-%m-%d").date()
        years = today.year - admission_date.year
        if years == 0:
            days = int(float((datetime.combine(today, datetime.min.time()) - datetime.combine(admission_date,
                                                                                              datetime.min.time())).days) / float(
                24))
            data = {
                'employee': employee.id,
                'period': str(admission_date.year) + "-" + str(today.year),
                'vacations_generated': days,
                'vacations_taken': 0,
                'vacations_available': 0,
            }
            lines.append(data)
        if years >= 1:
            if years == 1:
                if today < admission_date.replace(year=today.year):
                    days = int(float((datetime.combine(today, datetime.min.time()) - datetime.combine(
                        admission_date, datetime.min.time())).days) / float(24))
                    data = {
                        'employee': employee.id,
                        'period': str(admission_date.year) + "-" + str(today.year),
                        'vacations_generated': days,
                        'vacations_taken': 0,
                        'vacations_available': 0,
                    }
                    lines.append(data)
                else:
                    days = 15
                    data = {
                        'employee': employee.id,
                        'period': str(admission_date.year) + "-" + str(today.year),
                        'vacations_generated': days,
                        'vacations_taken': 0,
                        'vacations_available': 0,
                    }
                    lines.append(data)

                    days = int(float((datetime.combine(today, datetime.min.time()) - datetime.combine(
                        admission_date.replace(year=today.year), datetime.min.time())).days) / float(24))
                    data = {'employee': employee.id,
                            'period': str(today.year) + "-" + str(today.year + 1),
                            'vacations_generated': days,
                            'vacations_taken': 0,
                            'vacations_available': 0, }
                    lines.append(data)
            if years > 1:
                for x in range(1, years):
                    days = 15
                    data = {'employee': employee.id,
                            'period': str(admission_date.year) + "-" + str(admission_date.year + x),
                            'vacations_generated': days,
                            'vacations_taken': 0,
                            'vacations_available': 0, }
                    lines.append(data)
                if today < admission_date.replace(year=today.year):
                    days = int(float((datetime.combine(today, datetime.min.time()) - datetime.combine(
                        admission_date.replace(year=today.year - 1), datetime.min.time())).days) / float(24))
                    data = {'employee': employee.id,
                            'period': str(admission_date.year + 1) + "-" + str(today.year),
                            'vacations_generated': days,
                            'vacations_taken': 0,
                            'vacations_available': 0, }
                    lines.append(data)
                else:
                    days = 15
                    data = {'employee': employee.id,
                            'period': str(admission_date.year + 1) + "-" + str(today.year),
                            'vacations_generated': days,
                            'vacations_taken': 0,
                            'vacations_available': 0, }
                    lines.append(data)
                    days = int(float((datetime.combine(today, datetime.min.time()) - datetime.combine(
                        admission_date.replace(year=today.year), datetime.min.time())).days) / float(24))
                    data = {'employee': employee.id,
                            'period': str(today.year) + "-" + str(today.year + 1),
                            'vacations_generated': days,
                            'vacations_taken': 0,
                            'vacations_available': 0, }
                    lines.append(data)
        return lines

    @api.onchange('employee_id', 'holiday_status_id')
    def _onchange_employee_id(self):
        """
        Generamos las vacaciones de empleado si el tipo de ausencia
        es para vacaciones y asigar departamento si tiene
        """
        self.department_id = self.employee_id.department_id
        if self.is_vacations and self.holiday_type == 'employee':
            employee = self.employee_id
            lines_vacations = self.lines_vacations.browse([])
            data = self._get_lines_vacations(employee)
            for line in data:  # Añadimos líneas de vacaciones a objeto
                lines_vacations += lines_vacations.new(line)
            self.lines_vacations = lines_vacations
            vacations_taken = self.employee_id.days_taken  # Las vacaciones tomados por empleado
            # Hacemos la disminución con los días de vacaciones tomados
            for line in self.lines_vacations:
                if vacations_taken != 0:
                    if vacations_taken == line.vacations_generated:
                        line.update({
                            'vacations_taken': vacations_taken,
                            'vacations_available': 0
                        })
                        vacations_taken = 0
                        continue
                    if vacations_taken - line.vacations_generated > 0:
                        line.update({
                            'vacations_taken': line.vacations_generated,
                            'vacations_available': 0
                        })
                        vacations_taken = vacations_taken - line.vacations_generated
                        continue
                    if vacations_taken - line.vacations_generated < 0:
                        line.update({
                            'vacations_taken': vacations_taken,
                            'vacations_available': abs(vacations_taken - line.vacations_generated)
                        })
                        vacations_taken = 0
                        continue
                if vacations_taken == 0:
                    line.update({
                        'vacations_taken': 0,
                        'vacations_available': line.vacations_generated
                    })
            if vacations_taken != 0:
                self.lines_vacations[-1].update(
                    {'vacations_available': self.lines_vacations[-1].vacations_available - vacations_taken})
        return

    @api.model
    def _get_vacations(self):
        """
        R: Obtenemos las vacaciones menos los días de la solicitud
        """
        data = []
        days = int(self.number_of_days_temp)
        for line in self.lines_vacations:
            if line.vacations_available <= days:
                data.append({
                    'period': line.period,
                    'vacations_available': line.vacations_available,
                    'requested': line.vacations_available,
                    'residue': 0
                })
                days = days - line.vacations_available
            else:
                data.append({
                    'period': line.period,
                    'vacations_available': line.vacations_available,
                    'requested': days,
                    'residue': int(line.vacations_available - days)
                })
                days = 0
        return data

    @api.multi
    def print_request(self):
        """
        Imprimimos solicitud de vacaciones
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_vacations').report_action(self)

    # CM
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirm', 'Por aprobar'),
        ('refuse', 'Negado'),
        ('validate1', 'Aprobado'),
        ('validate', 'Validado'),
        ('cancel', 'Anulado'),
    ], string='Status', readonly=True, track_visibility='onchange', copy=False, default='draft',
        help="The status is set to 'To Submit', when a holiday request is created." +
             "\nThe status is 'To Approve', when holiday request is confirmed by user." +
             "\nThe status is 'Refused', when holiday request is refused by manager." +
             "\nThe status is 'Approved', when holiday request is approved by manager.")

    color_name = fields.Selection([
        ('red', 'Red'),
        ('blue', 'Blue'),
        ('lightgreen', 'Light Green'),
        ('lightblue', 'Light Blue'),
        ('lightyellow', 'Light Yellow'),
        ('magenta', 'Magenta'),
        ('lightcyan', 'Light Cyan'),
        ('black', 'Black'),
        ('lightpink', 'Light Pink'),
        ('brown', 'Brown'),
        ('violet', 'Violet'),
        ('lightcoral', 'Light Coral'),
        ('lightsalmon', 'Light Salmon'),
        ('lavender', 'Lavender'),
        ('wheat', 'Wheat'),
        ('ivory', 'Ivory')], default='lightblue')
    # CM
    type = fields.Selection([
        ('remove', 'Leave Request'),
        ('add', 'Allocation Request')
    ], string='Request Type', required=True, readonly=True, index=True, default='remove',
        states={'draft': [('readonly', False)], 'confirm': [('readonly', False)]},
        help="Choose 'Leave Request' if someone wants to take an off-day. "
             "\nChoose 'Allocation Request' if you want to increase the number of leaves available for someone")
    is_vacations = fields.Boolean('Es vacaciones?', related='holiday_status_id.is_vacations', store=True)
    lines_vacations = fields.One2many('eliterp.holiday.lines', 'holiday_id', string='Vacaciones', copy=False)
    approval_user = fields.Many2one('res.users', 'Aprobado por', copy=False)
    adjunt = fields.Binary('Adjunto', attachment=True, copy=False)
    adjunt_name = fields.Char('Nombre de adjunto', copy=False)
    employee_active = fields.Boolean('Empleado activo?', related='employee_id.active', store=True)
