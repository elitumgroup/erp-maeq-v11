# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class Employee(models.Model):
    _inherit = 'hr.employee'

    @api.depends('admission_date')
    @api.one
    def _get_working_time(self):
        """
        TODO: Calculamos si empleado tiene más de 365 días de trabajo le activamos los Fondos de reserva
        """
        if self.admission_date:
            day_ = 0.0328767  # Equivalencia en meses (Días exactos)
            star_date = datetime.strptime(self.admission_date, '%Y-%m-%d').date()
            end_date = datetime.today().date()
            days = abs(end_date - star_date).days + self.previous_contract_days
            months = round(days * day_, 0)
            if months >= 13:
                self.working_time = True

    working_time = fields.Boolean('Tiempo laboral?', compute='_get_working_time', default=False, help="Campo que sirve"
                                                                                                      "para saber si el empleado tiene Fondos"
                                                                                                      "de reserva.")


class LinesContractFunctions(models.Model):
    _name = "eliterp.lines.contract.functions"

    _description = 'Líneas de funciones de contrato'

    name = fields.Char('Nombre', required=True)
    functions_id = fields.Many2one('eliterp.contract.functions', string='Funciones')
    priority = fields.Selection([
        (0, 'Baja'),
        (1, 'Media'),
        (2, 'Alta'),
        (3, 'Máxima')
    ], string='Prioridad', default=0, required=True)


class ContractFunctions(models.Model):
    _name = "eliterp.contract.functions"

    _description = 'Funciones de contrato'

    name = fields.Char('Funciones')
    lines_functions = fields.One2many('eliterp.lines.contract.functions', 'functions_id',
                                      string='Líneas de funciones')
    contract_id = fields.Many2one('hr.contract', 'Contrato')


class ContractType(models.Model):
    _inherit = 'hr.contract.type'

    is_piece_contract = fields.Boolean('Es contrato destajo?', default=False)


class Contract(models.Model):
    _inherit = 'hr.contract'

    @api.model
    def _get_wage_letters(self):
        """
        Obtenemos el monto en letras
        """
        currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        text = currency[0].amount_to_text(self.wage).replace('Dollars', 'Dólares')  # Dollars, Cents
        text = text.replace('Cents', 'Centavos')
        return text.upper()

    @api.model
    def _get_date_format(self):
        return self.env['eliterp.global.functions'].get_date_format_invoice(self.date_start)

    @api.model
    def _get_date_format2(self):
        date1 = fields.Date.context_today(self)
        return self.env['eliterp.global.functions'].get_date_format_invoice(date1)

    @api.model
    def _get_date_format1(self):
        return self.env['eliterp.global.functions'].get_date_format_invoice(self.departure_date)

    @api.multi
    def imprimir_contrato(self):
        """
        Imprimimo contrato
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_employee_contract').report_action(self)

    @api.multi
    def imprimir_certificate(self):
        """
        Imprimimo certificado
        """
        contract = self.state_customize
        if contract == 'active':
            self.ensure_one()
            return self.env.ref('eliterp_hr.eliterp_action_report_employee_certificate_active').report_action(self)
        else:
            self.ensure_one()
            return self.env.ref('eliterp_hr.eliterp_action_report_employee_certificate_inactive').report_action(self)

    @api.constrains('employee_id')
    def _check_employee_id(self):
        """
        Validamos qué empleado no tenga contrato activo
        :return:
        """
        contract = self.employee_id.contract_id
        if contract:
            if contract.state_customize == 'active':
                raise ValidationError("Empleado %s tiene contrato activo en sistema." % self.employee_id.name)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        """
        ME: Traemos la fecha de ingreso, sueldo y estrucutra del empleado
        """
        res = super(Contract, self)._onchange_employee_id()
        self.wage = self.employee_id.wage
        self.struct_id = self.employee_id.struct_id.id
        if not self.state_customize == 'finalized':
            self.date_start = self.employee_id.admission_date
        return res

    @api.one
    def _get_count_functions(self):
        """
        Obtenemos la cantidad de funciones del contrato
        :return: dict
        """
        for record in self:
            functions = self.env['eliterp.contract.functions'].search([('contract_id', '=', self.id)])._ids
            count = 0
            if functions:
                lines_functions = self.env['eliterp.lines.contract.functions'].search(
                    [('functions_id', '=', functions[0])])
                count = len(lines_functions)
            record.count_functions = count

    @api.one
    def _get_antiquity(self):
        """
        Obtenemos los días de antiguedad del empleado
        """
        start_date = datetime.strptime(self.date_start, '%Y-%m-%d')
        end_date = datetime.strptime(self.date_start, '%Y-%m-%d') + timedelta(days=self.days_for_trial)
        time = (str(end_date - start_date)).strip(', 0:00:00')
        days = 0
        if time:
            days = int("".join([x for x in time if x.isdigit()]))
        self.antiquity = days

    @api.one
    def _get_days_for_trial(self):
        """
        Contador de los días de prueba
        """
        for contract in self:
            result = 0
            if contract.days_for_trial == self.test_days:
                result = self.test_days
            else:
                days = ((datetime.strptime(fields.Date.today(), '%Y-%m-%d')) - (
                    datetime.strptime(contract.date_start, '%Y-%m-%d'))).days
                result = days
                contract.days_for_trial = result

    @api.onchange('is_trial')
    def _onchange_is_trial(self):
        """
        Colocamos las fechas de inicio y fin al cambiar campo Es período de prueba?
        """
        if self.is_trial:
            if self.date_start:
                self.trial_date_start = self.date_start
                self.trial_date_end = (
                        datetime.strptime(self.date_start, '%Y-%m-%d') + relativedelta(days=+ self.test_days))

    @api.one
    def _get_end_trial(self):
        """
        Si contador de días es mayor 90 días terminó pruebas
        """
        if self.days_for_trial >= 90:
            self.end_trial = True

    @api.multi
    def active_contract(self):
        """
        Activamos contrato
        """
        number = self.env['ir.sequence'].next_by_code('hr.contract')
        new_name = "RHCI-%s-%s-%s" % (
        self.date_start[:4], self.date_start[5:7], str(number))  # Nuevo nombre de contrato
        return self.write({
            'name': new_name,
            'state_customize': 'active'
        })

    @api.multi
    def open_functions(self):
        """
        Abrimos las funciones del contrato
        :return: dict
        """
        functions_id = self.env['eliterp.contract.functions'].search([('contract_id', '=', self.id)])._ids
        res = {
            'type': 'ir.actions.act_window',
            'res_model': 'eliterp.contract.functions',
            'view_mode': 'form',
            'view_type': 'form',
        }
        if functions_id:
            res['res_id'] = functions_id[0]
            res['context'] = "{}"
        else:
            res['context'] = "{'default_contract_id': " + str(self.id) + "}"
        return res

    @api.multi
    def unlink(self):
        for record in self:
            if record.state_customize != 'draft':
                raise ValidationError("No se puede borrar contratos activos o finalizados.")
        return super(Contract, self).unlink()

    name = fields.Char('Nº de documento', required=False, copy=False)  # CM
    count_functions = fields.Integer(compute='_get_count_functions', string="Funciones")
    test_days = fields.Integer('Días de prueba')  # Configuración RRHH
    antiquity = fields.Integer('Antiguedad (días)', compute='_get_antiquity')
    is_trial = fields.Boolean('Es período de prueba?')
    end_trial = fields.Boolean(compute='_get_end_trial', string='Finalizó prueba?', default=False)
    trial_date_start = fields.Date('Fecha inicio prueba')
    days_for_trial = fields.Integer('Días de prueba', compute='_get_days_for_trial')
    state_customize = fields.Selection([
        ('draft', 'Nuevo'),
        ('active', 'Activo'),
        ('finalized', 'Finalizado')
    ], 'Estado', default='draft')
    departure_date = fields.Date(string='Fecha de salida')
    adjunt = fields.Binary('Documento firmado', attachment=True)
    adjunt_name = fields.Char('Nombre')

    @api.model
    def _get_wage_letters(self):
        """
        Obtenemos el monto en letras
        """
        amount_text = self.env['report.eliterp_treasury.eliterp_report_check_voucher_xlsx']
        dollar = amount_text.get_amount_to_word(self.renumbering)
        return dollar.upper()

    @api.model
    def _get_date_formatlarge(self):
        return self.env['eliterp.global.functions'].get_date_format_invoice1(self.date)

    @api.model
    def _get_date_formatlarges(self):
        return self.env['eliterp.global.functions'].get_date_format_invoicesindia(self.date)

    @api.multi
    def imprimir_contract_term(self):
        """
        Imprimimo Termino de contrato
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_contract_term').report_action(self)

    date = fields.Date('Fecha documento (Destajo)', default=fields.Date.context_today)
    renumbering = fields.Float(string='Remuneración', help="Base para el cálculo de bonficación.")
    comment = fields.Text('Texto Libre')
    number_hectares = fields.Char(string='Nº hectáreas')
    is_piece_contract = fields.Boolean('Es contrato destajo?', related='type_id.is_piece_contract', store=True)
