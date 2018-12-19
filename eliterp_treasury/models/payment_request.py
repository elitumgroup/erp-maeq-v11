# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PaymentRequestLines(models.Model):
    _name = 'eliterp.payment.request.lines'

    _description = 'Líneas de requerimiento de pago'

    @api.constrains('amount')
    def _check_amount(self):
        """
        Validamos monto
        """
        if self.amount <= 0:
            raise ValidationError("Monto no puede ser menor o igual a 0.")

    payment_request_id = fields.Many2one('eliterp.payment.request', string="Requerimiento de pago")
    detail = fields.Char('Detalle', required=True)
    amount = fields.Float('Monto', required=True)


class PaymentRequest(models.Model):
    _name = 'eliterp.payment.request'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _description = 'Requerimiento de pago'

    @api.depends('lines_request')
    @api.one
    def _get_total(self):
        """
        Total de líneas de solicitud
        """
        self.total = round(sum(line.amount for line in self.lines_request), 2)

    @api.multi
    def print_request(self):
        """
        Imprimimos solicitud
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_payment_request').report_action(self)

    @api.multi
    def approve(self):
        """
        Aprobar solicitud
        """
        self.write({
            'state': 'approve',
            'approval_user': self._uid,
        })

    @api.multi
    def deny(self):
        """
        Negar solicitud
        """
        self.write({
            'state': 'deny'
        })

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación
        """
        for request in self:
            if not request.lines_request:
                raise UserError('No existen líneas en solicitud.')
        self.write({
            'state': 'to_approve',
            'name': self.env['ir.sequence'].sudo().next_by_code('payment.request')
        })
        # Enviar correo a usuarios para aprobación
        self.env['eliterp.managerial.helps'].send_mail(self.id, self._name, 'eliterp_approve_payment_request_mail')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.beneficiary = self.employee_id.name

    @api.onchange('supplier_id')
    def _onchange_supplier_id(self):
        if self.supplier_id:
            self.beneficiary = self.supplier_id.name

    @api.onchange('type')
    def _onchange_type(self):
        if self.type == 'other':
            self.beneficiary = False

    @api.multi
    def copy(self, default=None):
        default = default or {}
        lines_request = []
        for line in self.lines_request:
            lines_request.append([0, 0, {
                'detail': line.detail,
                'amount': line.amount
            }])
        default['lines_request'] = lines_request
        return super(PaymentRequest, self).copy(default=default)

    @api.multi
    def unlink(self):
        for payment in self:
            if not payment.state == 'draft' or payment.pay_orders_count > 0:
                raise UserError("No se puede eliminar un requerimiento diferente a estado borrador o con OP vigentes.")
        return super(PaymentRequest, self).unlink()

    name = fields.Char('No. Documento', default='Nueva solicitud', copy=False)
    application_date = fields.Date('Fecha solicitud', default=fields.Date.context_today, required=True, readonly=True,
                                   states={'draft': [('readonly', False)]})
    payment_date = fields.Date('Fecha de pago', default=fields.Date.context_today, required=True, readonly=True,
                               states={'draft': [('readonly', False)]}, track_visibility='onchange')
    employee_id = fields.Many2one('hr.employee', string='Responsable', readonly=True,
                                  states={'draft': [('readonly', False)]})
    supplier_id = fields.Many2one('res.partner', string='Responsable', readonly=True,
                                  states={'draft': [('readonly', False)]}, domain=[('supplier', '=', True)])
    beneficiary = fields.Char('Titular', readonly=True, states={'draft': [('readonly', False)]},
                              track_visibility='onchange')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('approve', 'Aprobado'),
        ('deny', 'Negado'), ], string='Estado RPG', default='draft', copy=False, track_visibility='always')
    comments = fields.Text('Notas y comentarios', track_visibility='onchange')
    document = fields.Binary('Documento', attachment=True, copy=False)
    document_name = fields.Char('Nombre de documento', copy=False)
    lines_request = fields.One2many('eliterp.payment.request.lines', 'payment_request_id',
                                    string='Líneas de solicitud', readonly=True,
                                    states={'draft': [('readonly', False)]})
    total = fields.Float(compute='_get_total', string="Total", store=True, track_visibility='onchange')
    approval_user = fields.Many2one('res.users', 'Aprobado por', readonly=True, states={'draft': [('readonly', False)]},
                                    copy=False)

    type = fields.Selection([
        ('other', 'Otro'),
        ('employee', 'Empleado'),
        ('supplier', 'Proveedor'),
    ], string="Para", default='other', readonly=True, states={'draft': [('readonly', False)]})
