# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import api, fields, models
from odoo.exceptions import UserError
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LinesPayslipRun(models.Model):
    _name = 'eliterp.lines.payslip.run'

    _description = 'Líneas de rol consolidado'

    @api.depends('payslip_run_id')
    def _compute_parent_state(self):
        """
        Obtenemos el estado del padre
        """
        for record in self.filtered('payslip_run_id'):
            record.parent_state = record.payslip_run_id.state

    name = fields.Char('Empleado')
    departament = fields.Char('Departamento')
    admission_date = fields.Date('Fecha de ingreso')
    identification_id = fields.Char('No. identificación')
    worked_days = fields.Integer('Días trabajados')
    # Ingresos
    wage = fields.Float('Sueldo')
    extra_hours = fields.Float('HE 100%')
    additional_hours = fields.Float('HE 50%')
    reserve_funds = fields.Float('Fondos reserva')
    tenth_3 = fields.Float('Décimo tercero')
    tenth_4 = fields.Float('Décimo cuarto')
    other_income = fields.Float('Otros ingresos')
    total_income = fields.Float('Total de ingresos')
    mobilization = fields.Float('Movilización')  # MAEQ
    # Egresos
    payment_advance = fields.Float('Anticipo de quincena')
    iess_personal = fields.Float('IESS 9.45%')
    iess_patronal = fields.Float('IESS 17.60%')  # GERENTE GENERAL
    loan_payment_advance = fields.Float('Préstamo de quincena')
    loan_unsecured = fields.Float('Préstamo quirografário')
    loan_mortgage = fields.Float('Préstamo hipotecario')
    spouses_extension = fields.Float('Extensión conyuges')  # MAEQ
    penalty = fields.Float('Multas')
    absence = fields.Float('Faltas y atrasos')
    cellular_plan = fields.Float('Plan celular')
    other_expenses = fields.Float('Otros egresos')
    total_expenses = fields.Float('Total de egresos')
    # Suma
    net_receive = fields.Float('Neto a recibir')
    role_id = fields.Many2one('hr.payslip', 'Rol individual')
    payslip_run_id = fields.Many2one('hr.payslip.run', 'Rol consolidado', ondelete="cascade")
    parent_state = fields.Char(compute="_compute_parent_state", string="Estado de anticipo")


class ReasonDenyPayslipRun(models.TransientModel):
    _name = 'eliterp.reason.deny.payslip.run'

    _description = 'Razón para negar rol consolidado'

    description = fields.Text('Descripción', required=True)

    @api.multi
    def deny_payslip_run(self):
        """
        Negar rol consolidado
        """
        payslip_run_id = self.env['hr.payslip.run'].browse(self._context['active_id'])
        payslip_run_id.update({
            'state': 'deny'
        })
        return payslip_run_id


class PayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _inherit = ['hr.payslip.run', 'mail.thread']

    @api.multi
    def print_payslip_run(self):
        """
        Imprimimos rol consolidado
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_hr_payslip_run').report_action(self)

    @api.model
    def _default_journal(self):
        """
        MM: Obtener diario por defecto
        """
        return self.env['account.journal'].search([('name', '=', 'Rol consolidado')], limit=1)[0].id

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación de rol consolidado
        """
        if not self.lines_payslip_run:
            raise UserError("No hay líneas de roles creadas en el sistema.")
        self.update({'state': 'to_approve'})
        # Enviar correo a usuarios para aprobación
        self.env['eliterp.managerial.helps'].send_mail(self.id, self._name, 'eliterp_approve_payslip_run_mail')

    @api.multi
    def approve(self):
        """
        Aprobar rol consolidado
        """
        for rol in self.lines_payslip_run:  # Roles individuales, los aprobamos uno a uno
            rol.role_id.write({
                'approval_user': self._uid,
                'state': 'done',
            })
        # Rol consolidado
        self.update({
            'state': 'approve',
            'approval_user': self._uid
        })

    @api.multi
    def open_reason_deny_payslip_run(self):
        """
        Abrimos ventana emergente para negar rol
        :return:
        """
        return {
            'name': "Explique la razón",
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.reason.deny.payslip.run',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def _create_line_expenses(self, code_rule, move, amount):
        """
        Creamos líneas de movimientos para egresos
        :param rule:
        :param move:
        :param amount:
        :return: object
        """
        rule = self.env['hr.salary.rule'].search([('code', '=', code_rule)])[0]
        amount = round(amount, 3)
        self.env['account.move.line'].with_context(check_move_validity=False).create({
            'name': rule.name,
            'journal_id': self.journal_id.id,
            'account_id': rule.account_id.id,
            'move_id': move.id,
            'debit': 0.00,
            'credit': amount,
            'project_id': self.project_id.id,
            'date': self.date_end
        })
        _logger.info(rule.name + ': ' + str(amount))

    def _create_line_income(self, code_rule, move, amount, check):
        """
        Creamos líneas de movimientos para ingresos
        :param rule:
        :param move:
        :param amount:
        :param check:
        :return: object
        """
        rule = self.env['hr.salary.rule'].search([('code', '=', code_rule)])[0]
        amount = round(amount, 3)
        self.env['account.move.line'].with_context(check_move_validity=check).create({
            'name': rule.name,
            'journal_id': self.journal_id.id,
            'account_id': rule.account_id.id,
            'move_id': move.id,
            'debit': amount,
            'credit': 0.00,
            'date': self.date_end
        })
        _logger.info(rule.name + ': ' + str(amount))

    @api.one
    def confirm_payslip_run(self):
        """
        Confirmamos y contabilizamos el rol consolidado
        """
        move_id = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.date_end,
        })
        # Ingresos
        wage = 0.00
        tenth_3 = 0.00
        tenth_4 = 0.00
        reserve_funds = 0.00
        extra_hours = 0.00  # TODO: Pendiente de revisar
        additional_hours = 0.00
        other_income = 0.00
        mobilization = 0.00  # MAEQ
        total_income = 0.00
        # Egresos
        payment_advance = 0.00
        loan_payment_advance = 0.00
        iess_personal = 0.00
        loan_unsecured = 0.00
        loan_mortgage = 0.00
        spouses_extension = 0.00  # MAEQ
        penalty = 0.00
        absence = 0.00
        cellular_plan = 0.00
        iess_patronal = 0.00
        other_expenses = 0.00
        total_expenses = 0.00
        # Provisiones
        net_receive = 0.00
        provision_tenth_3 = []
        provision_tenth_4 = []
        provision_reserve_funds = 0.00
        advances = []
        flag_benefits = False  # Bandera para acumular beneficios
        for role in self.lines_payslip_run:  # Comenzamos a sumar los roles individuales para creación del consolidado
            wage += round(role.wage, 3)
            mobilization += round(role.mobilization, 3)
            additional_hours += round(role.additional_hours, 3)  # MAEQ
            other_income += round(role.other_income, 3)
            iess_personal += round(role.iess_personal, 3)
            iess_patronal += round(role.iess_patronal, 3)
            loan_payment_advance += round(role.loan_payment_advance, 3)
            loan_unsecured += round(role.loan_unsecured, 3)
            loan_mortgage += round(role.loan_mortgage, 3)
            spouses_extension += round(role.spouses_extension, 3)
            # Añadimos ADQ
            advances.append(
                {
                    'amount': round(role.payment_advance, 3),
                })
            penalty += round(role.penalty, 3)
            absence += round(role.absence, 3)
            cellular_plan += round(role.cellular_plan, 3)
            other_expenses += round(role.other_expenses, 3)
            net_receive += round(role.net_receive, 3)
            if role.role_id.struct_id.provisions:  # Para no colocar nada a las ES sin provisiones
                # DT y DT
                if role.tenth_3 == 0.00:
                    provision_tenth_3.append(role)
                else:
                    tenth_3 += round(role.tenth_3, 3)
                if role.tenth_4 == 0.00:
                    provision_tenth_4.append(role)
                else:
                    tenth_4 += round(role.tenth_4, 3)
                # Fondos de reserva retenidos
                if role.role_id.employee_id.benefits == 'yes' and role.role_id.employee_id.working_time:
                    flag_benefits = True
                    provision_reserve_funds += round((float(role.wage) * float(8.33)) / float(100),
                                                     3)
                # Fondos de reserva cobrados
                if role.role_id.employee_id.working_time:
                    reserve_funds += round((float(role.wage) * float(8.33)) / float(100), 3)
        # Décimos
        amount_provision_tenth_3 = 0.00
        for tenth_3_object in provision_tenth_3:
            amount_provision_tenth_3 += round((tenth_3_object.wage + tenth_3_object.additional_hours) / 12.00, 3)
        amount_provision_tenth_4 = 0.00
        for tenth_4_object in provision_tenth_4:
            amount_provision_tenth_4 += round((float(386) / 360) * tenth_4_object.worked_days, 3)
        # Creamos líneas de movimiento de egresos
        _logger.info('***EGRESOS***')
        amount_advances = 0.00
        for advance in advances:  # Anticipos de quincena
            amount_advances += round(advance['amount'], 3)
        self._create_line_expenses('ADQ', move_id, amount_advances)  # ADQ
        self._create_line_expenses('IESS_9.45%', move_id, iess_personal)  # IESS 9.45%
        self._create_line_expenses('PRES_QUIRO', move_id, loan_unsecured)  # Préstamo quirografario
        self._create_line_expenses('PRES_HIPO', move_id, loan_mortgage)  # Préstamo hipotecario
        self._create_line_expenses('MUL', move_id, penalty)  # Multas
        self._create_line_expenses('FALT_ATRA', move_id, absence)  # Faltas y atrasos
        self._create_line_expenses('PLAN', move_id, cellular_plan)  # Plan celular
        self._create_line_expenses('PRES_ANTIC', move_id, loan_payment_advance)  # Préstamo anticipo quincena
        self._create_line_expenses('EXT_IESS', move_id, spouses_extension)  # Extensión conyuges
        self._create_line_expenses('IESS_17.60%', move_id, iess_patronal)  # IEES 17.60%
        self._create_line_expenses('OEG', move_id, other_expenses)  # Otros egresos

        # Creamos líneas de movimiento de provisión, PROVISIÓN VACACIONES
        _logger.info('***PROVISIONES***')
        if flag_benefits:  # Si acumula beneficios (Fondos de reserva) se crea está línea de movimiento
            self._create_line_expenses('PFR', move_id, provision_reserve_funds)
        patronal = round((float(wage * 12.15)) / 100, 3)
        self._create_line_expenses('PDT', move_id, amount_provision_tenth_3)  # Provisión de DT
        self._create_line_expenses('PDC', move_id, amount_provision_tenth_4)  # Provisión de DC
        self._create_line_expenses('IESS_12.15%', move_id, patronal)  # IEES 12.15%
        self._create_line_expenses('NPP', move_id, net_receive)  # Nómina a pagar

        total_credit = 0.00
        total_credit = amount_advances + iess_personal + loan_unsecured + loan_mortgage + penalty + absence
        total_credit = total_credit + cellular_plan + loan_payment_advance + spouses_extension + iess_patronal
        total_credit = total_credit + other_expenses + provision_reserve_funds + amount_provision_tenth_3
        total_credit = total_credit + amount_provision_tenth_4 + patronal + net_receive
        _logger.critical('-TOTAL HABER = %f\n' % round(total_credit, 2))

        # Creamos líneas de movimiento de ingresos
        _logger.info('***INGRESOS***')
        self._create_line_income('PGA', move_id, patronal, False)  # Patronal (Gastos)
        amount_tenth_3 = round(tenth_3, 3) + round(amount_provision_tenth_3, 3)
        self._create_line_income('DT_MENSUAL', move_id, amount_tenth_3, False)  # Décimo tercero mensual
        amount_tenth_4 = round(tenth_4, 3) + round(amount_provision_tenth_4, 3)
        self._create_line_income('DC_MENSUAL', move_id, amount_tenth_4, False)  # Décimo cuarto mensual
        self._create_line_income('FR_MENSUAL', move_id, reserve_funds, False)  # Fondos de reserva mensual
        # self._create_line_income('HEEX', move_id, extra_hours, False)  # Horas extras
        self._create_line_income('HESU', move_id, additional_hours,
                                 False)  # Horas suplementarias (Sumatoria de horas de CMC's)
        self._create_line_income('OIN', move_id, other_income, False)  # Otros ingresos
        self._create_line_income('MOVILIZ', move_id, mobilization, False)  # MAEQ: Movilización

        total_debit = 0.00
        total_debit = patronal + amount_tenth_3 + amount_tenth_4 + reserve_funds
        total_debit = total_debit + additional_hours + other_income + mobilization + wage
        _logger.critical('-TOTAL DEBE = %f\n' % round(total_debit, 2))
        _logger.critical('-DIFERENCIA = %f' % round((total_credit - total_debit), 2))

        self._create_line_income('SUE', move_id, wage, True)  # Sueldo, se verifica asiento cuadrado

        move_id.post()
        name_split = move_id.name.split("-")
        date_split = self.date_start.split("-")
        new_name = "ROL" + "-" + date_split[0] + "-" + date_split[1] + "-" + name_split[1]
        move_id.write({
            'ref': "Rol consolidado" + "-" + self.name,
            'name': new_name,
            'date': self.date_end
        })
        self.update({'state': 'closed', 'move_id': move_id.id})

    @api.multi
    def unlink(self):
        """
        No eliminamos roles consolidados
        :return:
        """
        for line in self:
            if line.state != 'draft':
                if line.state != 'deny':
                    raise ValidationError("No podemos borrar rol diferente de borrador.")
        return super(PayslipRun, self).unlink()

    @api.multi
    def add_roles(self):
        """
        Añadimos los roles de cada uno de los empleados creados
        en el mismo período
        """
        roles = self.env['hr.payslip'].search(
            [
                ('date_from', '>=', self.date_start),
                ('date_from', '<=', self.date_end),
                ('state', '=', 'draft'),
                ('employee_id.project_id', '=', self.project_id.id)
            ]
        )
        if len(roles) == 0:
            raise UserError("No hay roles en el período selecionado.")
        else:
            lines_payslip_run = self.lines_payslip_run.browse([])  # Limpiar roles anteriores al cargar
            if not self.type:  # Si no son todos se filtran por estructuras
                roles = roles.filtered(lambda x: x.struct_id.id in self.structure_ids.ids)
                if not roles:
                    raise UserError("No hay roles individuales con estás estructuras seleccionadas.")
            for role in roles:
                data = {
                    'name': role.employee_id.name,
                    'departament': role.employee_id.department_id.name,
                    'admission_date': role.employee_id.admission_date,
                    'identification_id': role.employee_id.identification_id,
                    'worked_days': role.worked_days,
                    # Ingresos
                    'wage': role.input_line_ids.filtered(lambda x: x.code == 'SUE')[0].amount,
                    'extra_hours': role.input_line_ids.filtered(lambda x: x.code == 'HEEX')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'HEEX') else 0.00,
                    'additional_hours': role.input_line_ids.filtered(lambda x: x.code == 'HESU')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'HESU') else 0.00,
                    'reserve_funds': role.input_line_ids.filtered(lambda x: x.code == 'FR_MENSUAL')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'FR_MENSUAL') else 0.00,
                    'tenth_3': role.input_line_ids.filtered(lambda x: x.code == 'DT_MENSUAL')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'DT_MENSUAL') else 0.00,
                    'tenth_4': role.input_line_ids.filtered(lambda x: x.code == 'DC_MENSUAL')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'DC_MENSUAL') else 0.00,
                    'other_income': role.input_line_ids.filtered(lambda x: x.code == 'OIN')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'OIN') else 0.00,
                    'total_income': sum(line.amount for line in role.input_line_ids),
                    'mobilization': role.input_line_ids.filtered(lambda x: x.code == 'MOVILIZ')[
                        0].amount if role.input_line_ids.filtered(
                        lambda x: x.code == 'MOVILIZ') else 0.00,  # MAEQ
                    # Egresos
                    'payment_advance': role.input_line_ids_2.filtered(lambda x: x.code == 'ADQ')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'ADQ') else 0.00,
                    'iess_personal': role.input_line_ids_2.filtered(lambda x: x.code == 'IESS_9.45%')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'IESS_9.45%') else 0.00,
                    'iess_patronal': role.input_line_ids_2.filtered(lambda x: x.code == 'IESS_17.60%')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'IESS_17.60%') else 0.00,
                    'loan_payment_advance': role.input_line_ids_2.filtered(lambda x: x.code == 'PRES_ANTIC')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'PRES_ANTIC') else 0.00,
                    'loan_unsecured': role.input_line_ids_2.filtered(lambda x: x.code == 'PRES_QUIRO')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'PRES_QUIRO') else 0.00,
                    'spouses_extension': role.input_line_ids_2.filtered(lambda x: x.code == 'EXT_IESS')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'EXT_IESS') else 0.00,  # MAEQ
                    'loan_mortgage': role.input_line_ids_2.filtered(lambda x: x.code == 'PRES_HIPO')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'PRES_HIPO') else 0.00,
                    'penalty': role.input_line_ids_2.filtered(lambda x: x.code == 'MUL')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'MUL') else 0.00,
                    'absence': role.input_line_ids_2.filtered(lambda x: x.code == 'FALT_ATRA')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'FALT_ATRA') else 0.00,
                    'cellular_plan': role.input_line_ids_2.filtered(lambda x: x.code == 'PLAN')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'PLAN') else 0.00,
                    'other_expenses': role.input_line_ids_2.filtered(lambda x: x.code == 'OEG')[
                        0].amount if role.input_line_ids_2.filtered(
                        lambda x: x.code == 'OEG') else 0.00,
                    'total_expenses': sum(line.amount for line in role.input_line_ids_2),
                    'net_receive': role.net_receive,
                    'role_id': role.id
                }
                lines_payslip_run += lines_payslip_run.new(data)
            self.lines_payslip_run = lines_payslip_run

    @api.depends('lines_payslip_run')
    @api.one
    def _get_total(self):
        """
        Obtenemos el total del rol consolidado
        """
        self.total = sum(line.net_receive for line in self.lines_payslip_run)

    @api.one
    @api.depends('lines_payslip_run')
    def _get_count_employees(self):
        """
        Calculamos el total de empleados en rol
        """
        self.count_employees = len(self.lines_payslip_run)

    @api.onchange('date_start')
    def _onchange_date_start(self):
        """
        Nombre por defecto al cambiar fecha de rol
        """
        if self.date_start:
            month = self.env['eliterp.global.functions']._get_month_name(int(self.date_start[5:7]))
            self.name = "%s [%s]" % (month, self.date_start[:4])

    @api.multi
    def reviewed(self):
        """
        Revisado
        """
        for rol in self.lines_payslip_run:
            rol.role_id.write({
                'reviewed_user': self._uid
            })
        self.update({
            'state': 'reviewed',
            'reviewed_user': self._uid
        })

    @api.multi
    def duplicate(self):
        """
        TODO: Duplicar el rol consolidado, creando nuevas funciones
        :return: object
        """
        start = time.strftime('%Y-%m-01')
        end = str(datetime.now() + relativedelta(months=+1, day=1, days=-1))[:10]
        month = self.env['eliterp.global.functions']._get_month_name(int(start[5:7]))
        for line in self.lines_payslip_run:
            Payslip = self.env['hr.payslip']
            new_role = Payslip.create({
                'employee_id': line.role_id.employee_id.id,
                'struct_id': line.role_id.struct_id.id,
                'date_from': start,
                'date_to': end,
            })
            input_ids = Payslip.get_inputs(new_role.employee_id, new_role)
            input_lines = Payslip.input_line_ids.browse([])
            input_lines_2 = Payslip.input_line_ids_2.browse([])
            input_lines_3 = Payslip.input_line_ids_3.browse([])
            for r in input_ids:
                if r['type'] == 'INGRESOS':
                    input_lines += input_lines.new(r)
                if r['type'] == 'EGRESOS':
                    input_lines_2 += input_lines_2.new(r)
                if r['type'] == 'PROVISIÓN':
                    input_lines_3 += input_lines_3.new(r)
            # Actualizamos líneas del nuevo rol
            new_role.update({
                'input_line_ids': input_lines,
                'input_line_ids_2': input_lines_2,
                'input_line_ids_3': input_lines_3
            })
        values = {}
        values['date_start'] = start
        values['date_end'] = end
        values['name'] = "%s [%s]" % (month, start[:4])
        object = self.create(values)
        object.add_roles()  # Realizamos la acción para duplicar el rol
        # Regresamos al mismo creado
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_hr.eliterp_action_payslip_run')
        form_view_id = imd.xmlid_to_res_id('eliterp_hr.eliterp_view_form_payslip_run')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [form_view_id, 'form'],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(object) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = object.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    @api.model
    def _get_structure_ids(self):
        a = []
        for line in self.structure_ids:
            a.append(line.name)
        return ', '.join(a)

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('reviewed', 'Revisado'),  # MAEQ
        ('approve', 'Aprobado'),
        ('closed', 'Contabilizado'),
        ('deny', 'Negado')
    ], string='Estado', index=True, readonly=True, copy=False, default='draft', track_visibility='onchange')  # CM
    lines_payslip_run = fields.One2many('eliterp.lines.payslip.run', 'payslip_run_id',
                                        string="Líneas de rol consolidado")
    move_id = fields.Many2one('account.move', string="Asiento contable", copy=False)
    journal_id = fields.Many2one('account.journal', string="Diario", default=_default_journal)  # CM
    total = fields.Float('Total de rol', compute='_get_total', store=True, track_visibility='onchange')
    count_employees = fields.Integer('No. Empleados', compute='_get_count_employees', track_visibility='onchange')
    approval_user = fields.Many2one('res.users', 'Aprobado por', copy=False, track_visibility='onchange')
    reviewed_user = fields.Many2one('res.users', string='Revisado por', copy=False)  # MAEQ
    comment = fields.Text('Notas y comentarios', readonly=True, states={'draft': [('readonly', False)]})
    type = fields.Boolean('Todas las estructuras', default=True, readonly=True, states={'draft': [('readonly', False)]})
    structure_ids = fields.Many2many("hr.payroll.structure", string='Estructuras salariales', readonly=True,
                                     states={'draft': [('readonly', False)]})
