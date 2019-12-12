# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError
import json
from operator import itemgetter
from itertools import groupby
from odoo.tools import float_is_zero
from datetime import datetime, timedelta


class ViaticalConcepts(models.Model):
    _name = 'eliterp.viatical.concepts'

    _description = 'Conceptos de viático'

    @api.constrains('max_amount')
    def _check_amount(self):
        """
        Verificamos qué el valor sea mayor a 0
        """
        if not self.max_amount > 0:
            raise ValidationError("El monto debe ser mayor a 0.")

    name = fields.Char('Concepto', required=True)
    account_id = fields.Many2one('account.account', string="Cuenta contable",
                                 domain=[('account_type', '=', 'movement')], required=True)
    max_amount = fields.Float('Monto máximo (Diario)')
    combustible = fields.Boolean('Gasolina o diesel?', defaul=False,
                                 help='Se lo marca para calcular valor diario con distancia (KM) con costo de KM.')

    _sql_constraints = [
        ('account_id_unique', 'unique (account_id)', "Ya existe cuenta asignada.")
    ]


class TravelDestinations(models.Model):
    _name = 'eliterp.travel.destinations'

    _description = 'Destinos para viático'

    name = fields.Char('Destino', required=True)
    distance = fields.Float('Distancia', required=True)
    amount = fields.Float('Monto', help="Monto aproximado de la cantidad de dinero gastado según KM's")


class ViaticalConceptsLine(models.Model):
    _name = 'eliterp.viatical.concepts.line'

    _description = 'Línea de conceptos para viático'

    @api.one
    @api.depends('daily_value', 'days', 'number_of_people')
    def _get_total(self):
        """
        Obtenemos el total de la línea
        """
        self.total = round(float(self.daily_value * self.days * self.number_of_people), 2)

    viatical_concepts_id = fields.Many2one('eliterp.viatical.concepts', string="Concepto", required=True)
    travel_allowance_request_id = fields.Many2one('eliterp.travel.allowance.request', string="Solicitud")
    daily_value = fields.Float('Valor diario')
    days = fields.Integer('No. días', default=1)
    number_of_people = fields.Integer('No. personas', default=1)
    total = fields.Float('Total', compute='_get_total')


class TravelAllowanceRequest(models.Model):
    _name = 'eliterp.travel.allowance.request'

    _description = 'Solicitud de viáticos'

    _inherit = ['mail.thread']

    @api.multi
    def unlink(self):
        for payment in self:
            if payment.state != 'draft':
                raise UserError("No se puede eliminar una Solicitud de viático diferente a estado borrador.")
        return super(TravelAllowanceRequest, self).unlink()

    @api.multi
    def print_request(self):
        """
        Imprimimos solicitud
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_travel_allowance_request').report_action(self)

    @api.one
    @api.depends('application_lines')
    def _get_amount_total(self):
        """
        Obtenemos el total de las líneas para solicitud
        """
        self.amount_total = sum(line.total for line in self.application_lines)

    @api.model
    def create(self, values):
        """
        :param values:
        :return: object
        """
        object_sequence = self.env['ir.sequence']
        viaticum = super(TravelAllowanceRequest, self).create(values)
        viaticum.name = object_sequence.next_by_code('travel.allowance.request')
        return viaticum

    @api.multi
    def approve(self):
        """
        Aprobar solicitud
        """
        self.write({
            'state': 'approve',
            'approval_user': self.env.uid
        })

    @api.multi
    def open_reason_deny_solicitud(self):
        # TODO: Verificar luego si se abre la ventana
        self.write({'state': 'deny'})

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación
        """
        if not self.application_lines:
            raise ValidationError("No tiene línea de conceptos creadas para solicitud.")
        self.write({
            'state': 'to_approve'
        })

    @api.model
    def _default_employee(self):
        """
        Obtenemos el empleado por defecto del usuario
        """
        return self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

    @api.constrains('return_date')
    def _check_return_date(self):
        """
        Verificamos la fechas
        """
        if self.return_date < self.trip_date:
            raise ValidationError('La fecha de retorno no puede ser menor a la del viaje.')

    name = fields.Char('No. Documento', copy=False, default='Nueva solicitud')
    application_date = fields.Date('Fecha de solicitud', default=fields.Date.context_today, required=True,
                                   readonly=True, states={'draft': [('readonly', False)]})
    trip_date = fields.Date('Fecha de viaje', default=fields.Date.context_today, required=True, readonly=True,
                            states={'draft': [('readonly', False)]})
    return_date = fields.Date('Fecha de retorno', default=fields.Date.context_today, required=True
                              , readonly=True, states={'draft': [('readonly', False)]})
    beneficiary = fields.Many2one('hr.employee', string='Beneficiario', required=True,
                                  default=_default_employee, readonly=True, states={'draft': [('readonly', False)]})
    destination = fields.Char(string='Destino', required=True, readonly=True, states={'draft': [('readonly', False)]})
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo", required=True, readonly=True,
                                          states={'draft': [('readonly', False)]})
    reason = fields.Char('Motivo', required=True, readonly=True, states={'draft': [('readonly', False)]})
    amount_total = fields.Float(compute='_get_amount_total', string="Monto total", store=True)
    approval_user = fields.Many2one('res.users', 'Aprobado por')
    reason_deny = fields.Text('Negado por')
    application_lines = fields.One2many('eliterp.viatical.concepts.line', 'travel_allowance_request_id',
                                        string='Línea de conceptos')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('approve', 'Aprobado'),
        ('liquidated', 'Liquidado'),
        ('deny', 'Negado')
    ], "Estado", default='draft')


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_invoice_open(self):
        """
        MM: Validamos la factura, para verificar qué sea cuenta correcta de las líneas
        :return: object
        """
        res = super(AccountInvoice, self).action_invoice_open()
        if self.viaticum:
            viatical_concepts = self.env['eliterp.viatical.concepts'].search([])  # Todas las cuentas de viáticos
            accounts = []
            for account in viatical_concepts:
                accounts.append(account.account_id)
            if not any(self.invoice_line_ids.filtered(lambda x: x.account_id in accounts)) and self.viaticum:
                raise UserError('Una cuenta de las líneas no corresponden a las cuentas de viáticos.')
        return res

    viaticum = fields.Boolean('Viático?', default=False)
    invoice_liquidated = fields.Boolean('Factura liquidada?', default=False)


class VoucherLiquidationSettlement(models.Model):
    _name = 'eliterp.voucher.liquidation.settlement'

    _description = 'Comprobante de viático en liquidación'

    @api.constrains('amount_total')
    def _check_amount_total(self):
        """
        Validamos monto
        """
        if self.amount_total <= 0:
            raise ValidationError("Monto no puede ser menor o igual a 0.")

    @api.onchange('invoice_id')
    def _onchange_invoice_id(self):
        """
        Para la factura llenamos estos campos con sus datos
        :return:
        """
        if self.invoice_id:
            self.date = self.invoice_id.date_invoice
            self.name = self.invoice_id.invoice_number
            self.amount_total = self.invoice_id.amount_total

    @api.onchange('sale_note_id')
    def _onchange_sale_note_id(self):
        """
        Para la nota de venta llenamos estos campos con sus datos
        :return:
        """
        if self.sale_note_id:
            self.date = self.sale_note_id.date_invoice
            self.name = self.sale_note_id.invoice_number
            self.amount_total = self.sale_note_id.amount_total

    type_voucher = fields.Selection([
        ('vale', 'Vale'),
        ('invoice', 'Factura'),
        ('note', 'Nota de venta')
    ], string="Tipo", required=True)
    invoice_id = fields.Many2one('account.invoice', string='Factura', domain=[('viaticum', '=', True),
                                                                              ('invoice_liquidated', '=', False),
                                                                              ('is_sale_note', '=', False),
                                                                              ('state', '=', 'open')])
    sale_note_id = fields.Many2one('account.invoice', string='Nota de venta', domain=[('viaticum', '=', True),
                                                                                      (
                                                                                          'invoice_liquidated', '=',
                                                                                          False),
                                                                                      ('state', '=', 'open'),
                                                                                      ('is_sale_note', '=', True)
                                                                                      ])
    # Al seleccionar factura cambiar estos valores
    date = fields.Date('Fecha documento', required=True)
    name = fields.Char(string="No. Documento")
    amount_total = fields.Float("Monto total")
    viatical_concepts_id = fields.Many2one('eliterp.viatical.concepts', string="Concepto")  # Sólo para vale
    type_validation_without = fields.Selection([
        ('charge', 'Cargo a la empresa'),
        ('reimburse', 'Por reembolsar'),
    ], string="Tipo de validación", default='reimburse')
    account_id = fields.Many2one('account.account', string="Cuenta contable",
                                 domain=[('account_type', '=', 'movement')])
    liquidation_settlement_id = fields.Many2one('eliterp.liquidation.settlement', string="Liquidación")


class TravelAllowanceRequestPayOrder(models.Model):
    _inherit = 'eliterp.travel.allowance.request'

    @api.multi
    def generate_request(self):
        """
        Abrimos ventana para añadir generar orden de pago
        :return: dict
        """
        self.flag_change = True
        view = self.env.ref('eliterp_treasury.eliterp_view_form_pay_wizard')
        context = {
            'default_default_date': self.application_date,
            'default_type': 'svi',
            'default_default_amount': self.residual_pay_order,
            'default_amount': self.residual_pay_order,
            'default_project_id': self.project_id.id
        }
        return {
            'name': "Crear orden de pago",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.pay.wizard',
            'view_id': view.id,
            'target': 'new',
            'context': context,
        }

    @api.one
    @api.depends('flag_change', 'lines_pay_order.state')
    def _get_customize_amount(self):
        """
        Calculamos el estado de las ordenes
        """
        pays = self.lines_pay_order.filtered(lambda x: x.state == 'paid')
        if not pays:
            self.state_pay_order = 'generated'
            self.residual_pay_order = self.amount_total
        else:
            total = 0.00
            for pay in pays:  # Soló contabilizadas
                total += round(pay.amount, 2)
            self.improved_pay_order = total
            self.residual_pay_order = round(self.amount_total - self.improved_pay_order, 2)
            if float_is_zero(self.residual_pay_order, precision_rounding=0.01):
                self.state_pay_order = 'paid'
            else:
                self.state_pay_order = 'partial_payment'

    state_pay_order = fields.Selection([
        ('generated', 'Sin abonos'),
        ('partial_payment', 'Abono parcial'),
        ('paid', 'Pagado'),
    ], default='generated', string="Estado de pago", compute='_get_customize_amount', readonly=True, copy=False,
        store=True)
    improved_pay_order = fields.Float('Abonado OP', compute='_get_customize_amount', store=True)
    residual_pay_order = fields.Float('Saldo OP', compute='_get_customize_amount', store=True)
    lines_pay_order = fields.One2many('eliterp.pay.order', 'viaticum_id', string='Órdenes de pago')
    flag_change = fields.Boolean('Bandera de cambio?')

    @api.multi
    def _compute_pay_orders_count(self):
        for record in self:
            record.pay_orders_count = len(record.lines_pay_order)

    @api.multi
    def open_pay_orders(self):
        imd = self.env['ir.model.data']
        action = imd.xmlid_to_object('eliterp_treasury.eliterp_action_pay_order')
        list_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_tree_pay_order')
        form_view_id = imd.xmlid_to_res_id('eliterp_treasury.eliterp_view_form_pay_order')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(self.lines_pay_order) > 1:
            result['domain'] = "[('id','in',%s)]" % self.lines_pay_order.ids
        elif len(self.lines_pay_order) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = self.lines_pay_order.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    pay_orders_count = fields.Integer('No. OP', compute='_compute_pay_orders_count')


class LiquidationSettlement(models.Model):
    _name = 'eliterp.liquidation.settlement'
    _inherit = ['mail.thread']

    _description = 'Liquidación de viáticos'

    @api.multi
    def print_liquidation(self):
        """
        Imprimimos solicitud
        """
        self.ensure_one()
        return self.env.ref('eliterp_treasury.eliterp_action_report_liquidation_settlement').report_action(self)

    @api.model
    def _default_journal(self):
        """
        Diario por defecto para la liquidación de viático
        :return:
        """
        return self.env['account.journal'].search([('name', '=', 'Liquidación de viático')], limit=1)[0].id

    @api.multi
    def open_reason_deny_liquidation(self):
        # TODO: Verificar luego si se abre la ventana
        self.write({'state': 'deny'})

    @api.multi
    def approve(self):
        self.write({
            'state': 'approve',
            'approval_user': self.env.uid
        })

    @api.multi
    def to_approve(self):
        """
        Solicitamos aprobamos la liquidación
        """
        if not self.document_lines_without:
            raise UserError("No tiene líneas de documentos ingresadas.")
        self.write({
            'name': self.journal_id.sequence_id.next_by_id(),
            'state': 'to_approve'
        })

    @api.depends('document_lines_without')
    def _get_difference(self):
        """
        Calculamos la diferencia entre total de solicitud y registro de documentos
        """
        for record in self:
            if record.with_request:
                amount_total = sum(line['amount_total'] for line in record.document_lines_without)
                difference = record.travel_allowance_request_id.amount_total - amount_total
                record.difference = round(difference, 2)
            else:
                record.amount_total = sum(line['amount_total'] for line in record.document_lines_without)

    def liquidate(self):
        """
        Realizamos la liquidación
        """
        list_accounts = []
        for line in self.document_lines_without:
            if not line.account_id:
                raise ValidationError("Debe seleccionar una cuenta en la línea de comprobante.")
            if line.type_voucher != 'vale':
                partner = line.invoice_id.partner_id.id or line.sale_note_id.partner_id.id
                account = line.invoice_id.account_id.id or line.sale_note_id.account_id.id
                name = line.invoice_id.concept or line.sale_note_id.concept
                if line.type_voucher == 'invoice':
                    line.invoice_id.write({'invoice_liquidated': True})  # Para no volverla a seleccionar
                else:
                    line.sale_note_id.write({'invoice_liquidated': True})  # Para no volverla a seleccionar
            else:
                account = line.viatical_concepts_id.account_id.id
                partner = False
                name = line.viatical_concepts_id.name
            list_accounts.append({
                'partner': partner,
                'name': name,
                'account': account,
                'account_credit': line.account_id,
                'invoice': line.invoice_id.id or line.sale_note_id.id or False,
                'amount': line.amount_total
            })
        # Generamos Asiento contable
        move_id = self.env['account.move'].create({
            'journal_id': self.journal_id.id,
            'date': self.date
        })
        for register in list_accounts:
            # Gastos de viáticos (Debe)
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'name': register['name'],
                'journal_id': self.journal_id.id,
                'partner_id': register['partner'],
                'account_id': register['account'],
                'move_id': move_id.id,
                'debit': register['amount'],
                'invoice_id': register['invoice'],
                'credit': 0.00,
                'project_id': self.project_id.id if self.project_id else False,
                'date': self.date
            })
        moves_credit = []
        for account, group in groupby(list_accounts, key=itemgetter('account_credit')):
            amount = 0.00
            for i in group:
                amount += i['amount']
            moves_credit.append({
                'account': account,
                'amount': amount
            })
        count = len(moves_credit)
        for line in moves_credit:
            count -= 1
            if count == 0:
                self.env['account.move.line'].with_context(check_move_validity=True).create(
                    {'name': line['account'].name,
                     'journal_id': self.journal_id.id,
                     'account_id': line['account'].id,
                     'move_id': move_id.id,
                     'credit': line['amount'],
                     'debit': 0.00,
                     'project_id': self.project_id.id if self.project_id else False,
                     'date': self.date})
            else:
                self.env['account.move.line'].with_context(check_move_validity=False).create(
                    {'name': line['account'].name,
                     'journal_id': self.journal_id.id,
                     'account_id': line['account'].id,
                     'move_id': move_id.id,
                     'credit': line['amount'],
                     'debit': 0.00,
                     'project_id': self.project_id.id if self.project_id else False,
                     'date': self.date})
        move_id.with_context(eliterp_moves=True, move_name=self.name).post()
        move_id.write({'ref': 'LV por motivo de %s' % self.reason})
        # Liquidamos con factura
        for line in self.document_lines_without.filtered(lambda l: l.type_voucher in ['invoice', 'note']):
            d = line.invoice_id or line.sale_note_id
            movelines = d.move_id.line_ids or d.move_id.line_ids
            line_ = move_id.line_ids.filtered(lambda x: x.invoice_id == d)
            line_x = movelines.filtered(lambda x: x.invoice_id == d and x.account_id.user_type_id.type == 'payable')
            (line_x + line_).reconcile()
        # Cambiamos estado de la solicitud
        if self.with_request:
            self.travel_allowance_request_id.update({'state': 'liquidated'})
        self.write({
            'state': 'liquidated',
            'move_id': move_id.id
        })
        return True

    @api.onchange('with_request')
    def _onchange_with_request(self):
        """
        Quitamos la solicitud
        """
        if not self.with_request:
            self.travel_allowance_request_id = False

    @api.onchange('travel_allowance_request_id')
    def _onchange_travel_allowance_request_id(self):
        """
        Llenamos los datos con la solicitud
        """
        if self.with_request:
            self.application_date = self.travel_allowance_request_id.application_date
            self.trip_date = self.travel_allowance_request_id.trip_date
            self.return_date = self.travel_allowance_request_id.return_date
            self.beneficiary = self.travel_allowance_request_id.beneficiary
            self.destination = self.travel_allowance_request_id.destination
            self.reason = self.travel_allowance_request_id.reason
            self.project_id = self.travel_allowance_request_id.project_id.id
            self.amount_total = self.travel_allowance_request_id.amount_total
            self.account_analytic_id = self.travel_allowance_request_id.account_analytic_id.id

        return {}

    @api.constrains('return_date')
    def _check_return_date(self):
        """
        Verificamos la fechas
        """
        if self.return_date < self.trip_date:
            raise ValidationError('La fecha de retorno no puede ser menor a la del viaje.')

    @api.multi
    def unlink(self):
        for record in self:
            if not record.state == 'draft':
                raise UserError("No se puede borrar una liquidación si no está en borrador.")
        return super(LiquidationSettlement, self).unlink()

    name = fields.Char('No. Documento', copy=False)
    date = fields.Date('Fecha de documento', default=fields.Date.context_today, required=True,
                       readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    with_request = fields.Boolean('Con solicitud?', default=False,
                                  readonly=True, states={'draft': [('readonly', False)]})
    travel_allowance_request_id = fields.Many2one('eliterp.travel.allowance.request', string="Solicitud",
                                                  domain=[('state', '=', 'approve')],
                                                  readonly=True, states={'draft': [('readonly', False)]})

    application_date = fields.Date('Fecha de solicitud', default=fields.Date.context_today, required=True,
                                   readonly=True, states={'draft': [('readonly', False)]})
    trip_date = fields.Date('Fecha de viaje', default=fields.Date.context_today, required=True
                            , readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    return_date = fields.Date('Fecha de retorno', default=fields.Date.context_today, required=True
                              , readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    beneficiary = fields.Many2one('hr.employee', string='Beneficiario', required=True
                                  , readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange')
    destination = fields.Char(string='Destino', required=True, readonly=True,
                              states={'draft': [('readonly', False)]})

    reason = fields.Char('Motivo', required=True, readonly=True, states={'draft': [('readonly', False)]})
    amount_total = fields.Float(string="Monto total", required=True, readonly=True,
                                states={'draft': [('readonly', False)]}, track_visibility='onchange')
    approval_user = fields.Many2one('res.users', 'Aprobado por')
    move_id = fields.Many2one('account.move', string='Asiento contable')
    journal_id = fields.Many2one('account.journal', string="Diario", default=_default_journal)
    reason_deny = fields.Text('Negado por')
    comment = fields.Text('Notas y comentarios')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por aprobar'),
        ('approve', 'Aprobado'),
        ('liquidated', 'Liquidado'),
        ('deny', 'Negado')
    ], "Estado", default='draft', track_visibility='onchange')
    document_lines_without = fields.One2many('eliterp.voucher.liquidation.settlement', 'liquidation_settlement_id',
                                             "Comprobantes")
    difference = fields.Float('Diferencia', compute='_get_difference', store=True)

    @api.depends('trip_date', 'return_date')
    def _compute_days(self):
        if self.trip_date and self.return_date:
            start_date = datetime.strptime(self.trip_date, "%Y-%m-%d") + timedelta(hours=5)
            end_date = datetime.strptime(self.return_date, "%Y-%m-%d") + timedelta(hours=5)
            delta = end_date - start_date
            self.number_days = 1 if delta.days == 0 else delta.days

    number_days = fields.Integer('No. días', compute='_compute_days', store=True)
    number_of_people = fields.Integer('No. personas', default=1,
                                      readonly=True, states={'draft': [('readonly', False)]})
