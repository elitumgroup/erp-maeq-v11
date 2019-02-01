# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)

from odoo import api, fields, models, tools, _
from calendar import monthrange
from datetime import datetime, date
from odoo.exceptions import UserError


class PayrollProvisionLine(models.Model):
    _name = 'hr.payroll.provision.line'
    _description = 'Línea de provisión de nómina'

    @api.multi
    def unlink(self):
        """
        No eliminamos líneas contabilizadas
        :return:
        """
        for line in self:
            if line.parent_state != 'draft':
                raise UserError("No podemos borrar líneas diferentes de borrador.")
        return super(PayrollProvisionLine, self).unlink()

    @api.depends('payroll_provision_id.state')
    def _compute_parent_state(self):
        """
        Calculamos el estado del padre
        :return:
        """
        for record in self.filtered('payroll_provision_id'):
            record.parent_state = record.payroll_provision_id.state

    name = fields.Many2one('hr.employee', string='Empleado')
    number_roles = fields.Integer(string='# Roles')
    amount = fields.Float(string='Monto a pagar')
    reconciled = fields.Boolean('Pagado?', default=False, help="Indica si la línea se encuentra pagada.")
    parent_state = fields.Selection([('draft', 'Borrador'),
                                     ('validate', 'Validado'),
                                     ('cancel', 'Anulado')],
                                    string='Estado del padre', compute='_compute_parent_state')
    payroll_provision_id = fields.Many2one('hr.payroll.provision', string='Provisión de nómina', ondelete="cascade")


class PayrollProvision(models.Model):
    _name = 'hr.payroll.provision'
    _inherit = ['mail.thread']
    _description = 'Provisión de nómina'
    _order = 'date'

    @api.one
    @api.depends('line_ids.reconciled')
    def _compute_reconciled(self):
        """
        Calculamos si todas las líneas han sido seleccionadas cómo pagadas
        :return:
        """
        if not self.line_ids:
            return
        if all(l.reconciled for l in self.line_ids):
            self.reconciled = True
        else:
            self.reconciled = False

    @api.one
    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        """
        Calculamos el monto total de las líneas
        :return:
        """
        self.amount_total = sum(line.amount for line in self.line_ids)

    @api.onchange('type')
    def _onchange_type(self):
        """
        Al cambiar de fecha se le cambia el período
        # 31-12-2018, 30-11-2019
        # 01-03-2018, 28-02-2019
        :return:
        """
        today = datetime.today().date()
        if self.type == 'thirteenth':
            self.date_from = date(month=12, day=monthrange(today.year - 1, 12)[1], year=today.year - 1)
            self.date_to = date(month=11, day=monthrange(today.year, 11)[1], year=today.year)
        else:
            self.date_from = date(month=3, day=1, year=today.year - 1)
            self.date_to = date(month=2, day=monthrange(today.year, 2)[1], year=today.year)

    @api.multi
    def action_validate(self):
        """
        Validamos registro
        :return:
        """
        self.write({'state': 'validate'})

    @api.multi
    def action_cancel(self):
        """
        Anulamos registro
        :return:
        """
        if self.reconciled:
            raise UserError(_('No se puede cancelar registro pagado totalmente.'))
        self.write({'state': 'cancel'})

    @api.multi
    def action_calculate(self):
        """
        Cargar datos de roles en período seleccionado
        :return:
        """
        line_ids = self.line_ids.browse([])
        if self.type == 'thirteenth':
            code = 'PDT'
        else:
            code = 'PDC'
        employees_provision = self.env['hr.employee'].search([('benefits', '=', 'yes')])
        for employee in employees_provision:
            domain = [
                ('date_from', '>=', self.date_from),
                ('date_to', '<=', self.date_to),
                ('state', '=', 'done'),
                ('employee_id', '=', employee.id)
            ]
            roles = self.env['hr.payslip'].search(domain)
            if roles:
                amount = 0.00
                for role in roles:
                    amount += role.input_line_ids_3.filtered(lambda x: x.code == code)[0].amount
                a = {
                    'name': employee,
                    'number_roles': len(roles),
                    'amount': round(amount, 2)
                }
            line_ids += line_ids.new(a)
        self.line_ids = line_ids

    @api.multi
    def unlink(self):
        """
        No se puede eliminar registro en estado diferente de borrador
        :return:
        """
        for r in self:
            if r.state != 'draft':
                raise UserError("No se puede eliminar una registro diferente a estado borrador.")
        return super(PayrollProvision, self).unlink()

    name = fields.Char(string='Referencia', required=True, index=True, readonly=True,
                       states={'draft': [('readonly', False)]})
    type = fields.Selection([('thirteenth', 'Décimo tercero'),
                             ('fourteenth', 'Décimo cuarto')],
                            string='Tipo de provisión', required=True, default='thirteenth'
                            , readonly=True,
                            states={'draft': [('readonly', False)]},
                            track_visibility='onchange')
    date = fields.Date(string='Fecha de documento', required=True, readonly=True, default=fields.Date.context_today,
                       states={'draft': [('readonly', False)]}, track_visibility='onchange')
    date_from = fields.Date(string='Fecha inicio', readonly=True, required=True,
                            states={'draft': [('readonly', False)]})
    date_to = fields.Date(string='Fecha fin', readonly=True, required=True,
                          states={'draft': [('readonly', False)]})
    line_ids = fields.One2many('hr.payroll.provision.line', 'payroll_provision_id', string='Líneas de provisión')
    state = fields.Selection([('draft', 'Borrador'),
                              ('validate', 'Validado'),
                              ('cancel', 'Anulado')],
                             string='Estado', default='draft', track_visibility='always')
    amount_total = fields.Float(string="Monto total", compute='_compute_amount_total', store=True, readonly=True)
    reconciled = fields.Boolean(string='Pagado?', store=True, readonly=True, compute='_compute_reconciled',
                                help="Indica si el documento está pagado completamente.")
