# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from odoo.exceptions import UserError
from datetime import datetime
from odoo.exceptions import ValidationError


class LinesAdvancePayment(models.Model):
    _name = 'eliterp.lines.advance.payment'

    _rec_name = "employee_id"

    _description = 'Líneas de anticipo de quincena'

    @api.multi
    def unlink(self):
        """
        No eliminamos líneas contabilizadas
        :return:
        """
        for line in self:
            if line.parent_state == 'posted':
                raise UserError("No podemos borrar líneas de anticipo contabilizadas.")
        return super(LinesAdvancePayment, self).unlink()

    @api.depends('advanced_id.state')
    def _compute_parent_state(self):
        """
        Obtenemos el estado del padre
        """
        for record in self.filtered('advanced_id'):
            record.parent_state = record.advanced_id.state

    @api.one
    @api.depends('amount_advance', 'mobilization')
    def _get_total(self):
        """
        Total de línea
        """
        self.amount_total = round(self.amount_advance + self.mobilization, 2)

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    job_id = fields.Many2one('hr.job', string='Cargo de trabajo', related='employee_id.job_id', store=True)
    admission_date = fields.Date(related='employee_id.admission_date', store=True, string='Fecha ingreso')
    amount_advance = fields.Float('Monto', default=0.00)
    mobilization = fields.Float(string='Movilización')
    antiquity = fields.Integer('Días')
    amount_total = fields.Float('Total', compute='_get_total', store=True)
    advanced_id = fields.Many2one('eliterp.advance.payment', 'Anticipo', ondelete="cascade")
    parent_state = fields.Char(compute="_compute_parent_state", string="Estado de anticipo")


class ReasonDenyAdvance(models.TransientModel):
    _name = 'eliterp.reason.deny.advance'

    _description = 'Razón para negar anticipo de quincena'

    description = fields.Text('Descripción', required=True)

    @api.multi
    def deny_advance(self):
        """
        Cancelamos el anticipo de quincena
        """
        advance_id = self.env['eliterp.advance.payment'].browse(self._context['active_id'])
        advance_id.update({
            'state': 'deny',
            'reason_deny': self.description
        })
        return advance_id


class AdvancePayment(models.Model):
    _name = 'eliterp.advance.payment'
    _inherit = ['mail.thread']

    _description = 'Anticipo de quincena'

    @api.multi
    def print_advance(self):
        """
        Imprimimos anticipo
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_advance_payment').report_action(self)

    @api.multi
    def button_cancel(self):
        self.write({'state': 'cancel'})

    def _get_antiquity(self, employee):
        """
        Obtener días de antiguedad con fecha de documento
        :param employee:
        :return: integer
        """
        start_date = datetime.strptime(employee.admission_date, '%Y-%m-%d')
        end_date = datetime.strptime(self.date, '%Y-%m-%d')
        time = (str(end_date - start_date)).strip(', 0:00:00')
        days = 0
        if time:
            days = int("".join([x for x in time if x.isdigit()]))
        return days

    def load_employees(self):
        """
        Cargamos empleados para total de anticipo, debe tener un contrato el empleado
        """
        if self.lines_advance:
            self.lines_advance.unlink()  # Borramos líneas anteriores, no montar
        list_employees = []
        for employee in self.env['hr.employee'].search([
            ('active', '=', True),
            ('contract_id', '!=', False),
            ('project_id', '=', self.project_id.id)
        ]):
            amount_advance = 0.0  # Para MAEQ se trabajará así por el momento la variable está configurada en Ajustes
            # RRHH
            antiquity = self._get_antiquity(employee)
            if antiquity >= self.advance_days:
                amount_advance = round(float((employee.wage * 40) / 100), 2)
            else:
                amount_advance = 80.0
            list_employees.append([0, 0, {
                'employee_id': employee.id,
                'antiquity': antiquity,
                'mobilization': round(employee.mobilization / 2, 2),
                'amount_advance': amount_advance,
            }])
        return self.write({'lines_advance': list_employees})

    @api.one
    @api.depends('lines_advance')
    def _get_total(self):
        """
        Total de líneas de anticipo
        """
        self.total = sum(line.amount_total for line in self.lines_advance)

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación de anticipo de quincena
        """
        if not self.lines_advance:
            raise UserError("No hay líneas de anticipo creadas.")
        self.update({'state': 'to_approve'})
        # Enviar correo a usuarios para aprobación
        self.env['eliterp.managerial.helps'].send_mail(self.id, self._name, 'eliterp_approve_advance_mail')

    @api.multi
    def reviewed(self):
        """
        Revisado
        """
        self.update({'state': 'reviewed', 'reviewed_user': self._uid})

    @api.multi
    def approve(self):
        """
        Aprobar anticipo de quincena
        """
        self.update({'state': 'approve', 'approval_user': self._uid})

    @api.multi
    def open_reason_deny_advance(self):
        """
        Abrir ventana emergente para cancelar anticipo
        :return: dict
        """
        return {
            'name': "Explique la razón",
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.reason.deny.advance',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    @api.multi
    def posted_advance(self):
        """
        Contabilizar anticipo
        """
        ref = "Anticipo de " + self.period
        move_id = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.date,
            'ref': ref
        })
        account_debit = self.journal_id.default_debit_account_id.id
        account_credit = self.journal_id.default_credit_account_id.id
        if not account_credit or not account_debit:
            raise UserError('No existe cuenta acredora y/o deudora en diario.')
        self.env['account.move.line'].with_context(check_move_validity=False).create({
            'name': ref,
            'journal_id': self.journal_id.id,
            'account_id': account_credit,
            'move_id': move_id.id,
            'project_id': self.project_id.id,
            'debit': 0.0,
            'credit': self.total,
            'date': self.date
        })
        self.env['account.move.line'].with_context(check_move_validity=True).create({
            'name': ref,
            'journal_id': self.journal_id.id,
            'account_id': account_debit,
            'move_id': move_id.id,
            'project_id': self.project_id.id,
            'debit': self.total,
            'credit': 0.0,
            'date': self.date
        })
        move_id.post()
        return self.write({
            'name': move_id.name,
            'state': 'posted',
            'move_id': move_id.id
        })

    @api.one
    @api.depends('date')
    def _get_period(self):
        """
        Obtenemos el período con la fecha de emisión
        """
        month = self.env['eliterp.global.functions']._get_month_name(int(self.date[5:7]))
        self.period = "%s [%s]" % (month, self.date[:4])

    @api.depends('lines_advance')
    def _get_count_lines(self):
        """
        Cantidad de líneas de anticipo
        """
        for record in self:
            record.count_lines = len(record.lines_advance)

    @api.multi
    def unlink(self):
        """
        No eliminamos roles diferentes de borrador
        :return:
        """
        for line in self:
            if line.state != 'draft':
                raise ValidationError("No podemos borrar anticipos diferentes de borrador.")
        return super(AdvancePayment, self).unlink()

    name = fields.Char('No. Documento', index=True, default='Nuevo')
    period = fields.Char('Período', compute='_get_period', store=True)
    date = fields.Date('Fecha de emisión', default=fields.Date.context_today, required=True,
                       readonly=True, states={'draft': [('readonly', False)]})
    lines_advance = fields.One2many('eliterp.lines.advance.payment', 'advanced_id', string='Líneas de anticipo')
    move_id = fields.Many2one('account.move', string='Asiento contable')
    total = fields.Float('Total de anticipo', compute='_get_total', store=True, track_visibility='onchange')
    journal_id = fields.Many2one('account.journal', string="Diario de anticipo",
                                 default=lambda self: self.env.ref("eliterp_hr.eliterp_journal_advance_payment").id)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('reviewed', 'Revisado'),
        ('approve', 'Aprobado'),
        ('posted', 'Contabilizado'),
        ('deny', 'Negado'),
        ('cancel', 'Anulado')], string="Estado", default='draft', track_visibility='onchange')
    approval_user = fields.Many2one('res.users', string='Aprobado por')
    reviewed_user = fields.Many2one('res.users', string='Revisado por')
    reason_deny = fields.Text('Negado por')
    count_lines = fields.Integer('Nº empleados', compute='_get_count_lines')
    comment = fields.Text('Notas y comentarios', readonly=True, states={'draft': [('readonly', False)]})
    # Dato parametrizado para MAEQ (Pago de ADQ según días de empleados)
    advance_days = fields.Integer('Días de ADQ')
