# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class Voucher(models.Model):
    _inherit = 'account.voucher'

    check_number = fields.Char('No. Cheque', readonly=True, states={'draft': [('readonly', False)]},
                               track_visibility='onchange')
    reconcile = fields.Boolean('Conciliado?', default=False, track_visibility='onchange')


class ChangeStateChecks(models.TransientModel):
    _name = 'eliterp.change.state.checks'
    _description = 'Venta para cambio de estado de cheques'

    checks = fields.Many2many('eliterp.checks', string='Cheques emitidos')
    state = fields.Selection([
        ('issued', 'Emitido'),
        ('delivered', 'Entregado'),
        ('charged', 'Cobrado')
    ], string='Estado de cambio', default='charged')

    @api.model
    def default_get(self, my_fields):
        rec = super(ChangeStateChecks, self).default_get(my_fields)
        active_ids = self._context.get('active_ids')
        checks = self.env['eliterp.checks'].browse(active_ids)
        if any(check.state == 'protested' or check.type == 'receipts' for check in checks):
            raise UserError("Soló se puede cambiar estado de cheques emitidos y no anulados.")
        rec.update({
            'checks': [(6, 0, checks.ids)],
        })
        return rec

    @api.multi
    def change_state_checks(self):
        self.checks.update({'state': self.state})
        return True


class Checks(models.Model):
    _name = 'eliterp.checks'
    _order = "date asc"
    _inherit = ['mail.thread']

    _description = 'Cheques'

    @api.multi
    def unlink(self):
        for payment in self:
            if payment.state != 'draft':
                raise UserError("No se puede eliminar un cheques emitidos diferente a estado borrador.")
        return super(Checks, self).unlink()

    @api.one
    @api.depends('amount')
    def _get_amount_letters(self):
        """
        Obtenemos el monto en letras
        """
        currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        text = currency[0].amount_to_text(self.amount).replace('Dollars', 'Dólares')  # Dollars, Cents
        text = text.replace('Cents', 'Centavos')
        self.amount_in_letters = text.upper()

    @api.multi
    def action_reconcile_checks(self):
        self.ensure_one()
        voucher_id = self.voucher_id
        voucher_id.write({'reconcile': True})
        return True

    recipient = fields.Char('Girador/Beneficiario')
    partner_id = fields.Many2one('res.partner', string='Cliente/Proveedor')
    bank_id = fields.Many2one('res.bank', 'Banco')
    amount = fields.Float('Monto', required=True, track_visibility='onchange')
    amount_in_letters = fields.Char('Monto en letras', compute='_get_amount_letters', readonly=True)
    date = fields.Date('Fecha Recepción/Emisión', required=True, default=fields.Date.context_today,
                       track_visibility='onchange')
    check_date = fields.Date('Fecha cheque', required=True, track_visibility='onchange')
    type = fields.Selection([('receipts', 'Recibidos'), ('issued', 'Emitidos')], string='Tipo')
    check_type = fields.Selection([('current', 'Corriente'), ('to_date', 'A la fecha')], string='Tipo de cheque'
                                  , default='current')
    state = fields.Selection([
        ('received', 'Recibido'),
        ('deposited', 'Depositado'),
        ('issued', 'Emitido'),
        ('delivered', 'Entregado'),
        ('charged', 'Cobrado'),
        ('protested', 'Anulado')
    ], string='Estado', track_visibility='onchange')

    voucher_id = fields.Many2one('account.voucher', string='Pago/Cobro')
    reconcile = fields.Boolean(related='voucher_id.reconcile', string='Conciliado?')
    name = fields.Char('No. Cheque', related='voucher_id.check_number', store=True)
