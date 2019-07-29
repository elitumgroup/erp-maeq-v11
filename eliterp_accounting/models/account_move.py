# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo.exceptions import UserError
from odoo import api, fields, models, _


class ReasonMoveCancel(models.TransientModel):
    _name = 'eliterp.reason.move.cancel'

    _description = 'Razón para cancelar asiento contable'

    description = fields.Text('Descripción', required=True)

    @api.one
    def cancel_move(self):
        """
        Cancelamos Asiento contable
        :return: boolean
        """
        move = self.env['account.move'].browse(self._context['active_id'])
        move.with_context(from_move=True, move_id=move.id).reverse_moves(move.date, move.journal_id or False)
        move.write({'state': 'cancel'})
        return True


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    _order = 'name asc'

    @api.multi
    def name_get(self):
        res = []
        for analytic in self:
            if analytic.usage == 'view':
                if analytic.code:
                    name = name + '[' + analytic.code + ']'
                else:
                    name = analytic.name
            else:
                if analytic.code:
                    if analytic.account_analytic:
                        name = analytic.account_analytic.name + '/' + analytic.name + '[' + analytic.code + ']'
                    else:
                        name = analytic.name + '[' + analytic.code + ']'
                else:
                    if analytic.account_analytic:
                        name = analytic.account_analytic.name + '/' + analytic.name
                    else:
                        name = analytic.name
            res.append((analytic.id, name))
        return res

    account_analytic = fields.Many2one('account.analytic.account', string="Centro de costo padre")
    usage = fields.Selection([
        ('view', 'Vista'),
        ('movement', 'Movimiento')
    ], default='movement', string='Tipo', required=True)


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.multi
    def print_move(self):
        """
        Imprimimos
        """
        self.ensure_one()
        return self.env.ref('eliterp_accounting.eliterp_action_report_account_move').report_action(self)

    @api.model
    def create(self, vals):
        if 'date' in vals:
            self.env['eliterp.global.functions'].valid_period(vals['date'])  # Validar Período contable sea correcto
        res = super(AccountMove, self).create(vals)
        return res

    @api.multi
    def open_reason_move_cancel(self):
        """
        Abrir ventana emergente para cancelar Asiento contable
        :return: dict
        """
        for line in self.line_ids:
            if line.full_reconcile_id:
                raise UserError("Hay asientos conciliados, consulte con el Departamento Contable.")
        return {
            'name': "Explique la razón",
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'eliterp.reason.move.cancel',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    @api.multi
    def post(self):
        """
        Método modificado
        :return: self
        """
        invoice = self._context.get('invoice', False)
        self._post_validate()
        for move in self:
            move.line_ids.create_analytic_lines()
            if move.name == '/':
                new_name = False
                journal = move.journal_id

                if invoice and invoice.move_name and invoice.move_name != '/':
                    new_name = invoice.move_name
                else:
                    # Cambiar el nombre del movimiento (e.g Comprobante de ingreso)
                    if 'eliterp_moves' in self._context:
                        if 'internal_voucher' in self._context:
                            new_name = self.env['ir.sequence'].next_by_code('internal.process')
                        if 'move_name' in self._context:
                            new_name = self._context['move_name']
                    else:
                        if journal.sequence_id:
                            # If invoice is actually refund and journal has a refund_sequence then use that one or use the regular one
                            sequence = journal.sequence_id
                            if invoice and invoice.type in ['out_refund', 'in_refund'] and journal.refund_sequence:
                                if not journal.refund_sequence_id:
                                    raise UserError(_('Please define a sequence for the credit notes'))
                                sequence = journal.refund_sequence_id

                            new_name = sequence.with_context(ir_sequence_date=move.date).next_by_id()
                        else:
                            raise UserError(_('Please define a sequence on the journal.'))
                if new_name:
                    move.name = new_name
        return self.write({'state': 'posted'})

    @api.multi
    def _reverse_move(self, date=None, journal_id=None):
        """
        MM: Reversamos movimiento sin conciliar
        :param date:
        :param journal_id:
        :return: object
        """
        self.ensure_one()
        default = {
            'date': date,
            'reversed': True,
            'journal_id': journal_id.id if journal_id else self.journal_id.id,
            'ref': "Reversado desde: " + self.name
        }
        name_reverse = ''
        # Cambiamos el nombre del reverso dependiendo del origen
        if 'from_invoice' in self._context:
            name_reverse = str(self.env['account.invoice'].browse(self._context['active_id']).number) + " - [Reverso]"
        if 'from_retention' in self._context:
            name_reverse = str(self.env['eliterp.retention'].browse(self._context['active_id']).name) + " - [Reverso]"
        if 'from_payment' in self._context:
            name_reverse = str(self.env['account.payment'].browse(self._context['payment_id']).name) + " - [Reverso]"
        if 'from_note' in self._context:
            name_reverse = str(
                self.env['eliterp.credit.debit.notes'].browse(self._context['note_id']).name) + " - [Reverso]"
        if 'from_move' in self._context:
            name_reverse = str(self.env['account.move'].browse(self._context['move_id']).name) + " - [Reverso]"
        if 'from_voucher' in self._context:
            name_reverse = str(self.env['account.voucher'].browse(self._context['voucher_id']).name) + " - [Reverso]"
        default.update({'name': name_reverse})
        reversed_move = self.copy(default)
        for acm_line in reversed_move.line_ids.with_context(check_move_validity=False):
            acm_line.write({
                'debit': acm_line.credit,
                'credit': acm_line.debit,
                'amount_currency': -acm_line.amount_currency
            })
        return reversed_move

    date = fields.Date(required=True, states={}, index=True, default=fields.Date.context_today)
    state = fields.Selection([('draft', 'Borrador'),
                              ('posted', 'Contabilizado'),
                              ('cancel', 'Anulado')],
                             string='Estado', required=True, readonly=True, copy=False, default='draft')
    reversed = fields.Boolean('Reversado?', default=False)
