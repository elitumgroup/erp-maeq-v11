# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError


class GlobalFunctions(models.TransientModel):
    _name = 'eliterp.global.functions'

    def valid_period(self, date):
        """
        Validamos el período contable de un documento
        :param date:
        :return:
        """
        date = datetime.strptime(date, "%Y-%m-%d")
        year_accounting = self.env['eliterp.account.period'].search([('year_accounting', '=', date.year)])
        if not year_accounting:
            raise UserError("No hay ningún Período contable creado en el sistema.")
        period_id = year_accounting.lines_period.filtered(lambda x: x.code == date.month)
        if not period_id:
            raise UserError("No hay ninguna Línea de Período contable creada.")
        current_date = fields.Date.today()
        # if datetime.strptime(current_date, "%Y-%m-%d") < datetime.strptime(period_id.start_date, "%Y-%m-%d"):
        # raise UserError("La fecha del documento está fuera del rango del Período contable.")
        if datetime.strptime(current_date, "%Y-%m-%d") > datetime.strptime(period_id.closing_date, "%Y-%m-%d"):
            raise UserError("El Período contable está cerrado, comuníquese con el Departamento de Contabilidad.")

    @staticmethod
    def _get_month_name(month):
        if month == 1:
            return "Enero"
        if month == 2:
            return "Febrero"
        if month == 3:
            return "Marzo"
        if month == 4:
            return "Abril"
        if month == 5:
            return "Mayo"
        if month == 6:
            return "Junio"
        if month == 7:
            return "Julio"
        if month == 8:
            return "Agosto"
        if month == 9:
            return "Septiembre"
        if month == 10:
            return "Octubre"
        if month == 11:
            return "Noviembre"
        if month == 12:
            return "Diciembre"

    @staticmethod
    def _get_last_day_month(date):
        """
        Obtenemos la fecha del último día del mes
        :param date:
        :return: date
        """
        if isinstance(date, str):  # Por si acaso venga en string el campo date
            date = datetime.strptime(date, "%Y-%m-%d").date()
        next_month = date.replace(day=28) + timedelta(days=4)
        return next_month - timedelta(days=next_month.day)

    def get_date_format_invoice(self, date):
        month = self._get_month_name(int(date[5:7]))
        return '%s de %s de %s' % (date[8:], month, date[:4])

    def get_date_format_invoice1(self, date):
        month = self._get_month_name(int(date[5:7]))
        return '%s días del mes de %s del año %s' % (date[8:], month, date[:4])

    def get_date_format_invoicesindia(self, date):
        month = self._get_month_name(int(date[5:7]))
        return '%s del mes de %s del año %s' % (date[8:], month, date[:4])
