# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def open_credit_note(self):
        """
        Abrimos la nota de crédito relacionada
        """
        credit_note = self.env['account.invoice'].search([('invoice_reference', '=', self.id)])
        imd = self.env['ir.model.data']
        if self.type == 'in_invoice':
            action = imd.xmlid_to_object('eliterp_accounting.eliterp_action_credit_note_purchase')
            list_view_id = imd.xmlid_to_res_id('account.invoice_supplier_tree')
            form_view_id = imd.xmlid_to_res_id('account.invoice_supplier_form')
        else:
            action = imd.xmlid_to_object('eliterp_accounting.eliterp_action_credit_note_customer')
            list_view_id = imd.xmlid_to_res_id('account.invoice_tree')
            form_view_id = imd.xmlid_to_res_id('account.invoice_form')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(credit_note) > 1:
            result['domain'] = "[('id','in',%s)]" % credit_note.ids
        elif len(credit_note) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = credit_note.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    @api.multi
    def add_credit_note(self):
        """
        Añadimos nota de crédito en factura
        """
        if self.type == 'out_invoice':
            journal_name = 'Nota de crédito a cliente'
        else:
            journal_name = 'Nota de crédito'
        journal_credit = self.env['account.journal'].search([('name', '=', journal_name)], limit=1)
        if not journal_credit:
            raise UserError("No existe diario (%s) para crear nota de crédito." % journal_name)
        date = fields.Date.today() or self.date_invoice
        description = ""
        credit_note = self.with_context(credit_note=True).refund(
            date,
            date,
            description,
            journal_credit[0].id if journal_credit else False
        )
        credit_note.tax_line_ids.filtered(lambda x: x.tax_id.tax_type == 'retention').unlink()  # Borramos impuestos
        # de retención
        credit_note.write({
            'invoice_reference': self.id,
            'origin': self.invoice_number
        })
        if self.type == 'out_invoice':
            credit_note._onchange_journal_id()
        imd = self.env['ir.model.data']
        if self.type == 'out_invoice':
            action = imd.xmlid_to_object('eliterp_accounting.eliterp_action_credit_note_customer')
            list_view_id = imd.xmlid_to_res_id('account.invoice_tree')
            form_view_id = imd.xmlid_to_res_id('account.invoice_form')
        else:
            action = imd.xmlid_to_object('eliterp_accounting.eliterp_action_credit_note_purchase')
            list_view_id = imd.xmlid_to_res_id('account.invoice_supplier_tree')
            form_view_id = imd.xmlid_to_res_id('account.invoice_supplier_form')
        result = {
            'name': action.name,
            'help': action.help,
            'type': action.type,
            'views': [[list_view_id, 'tree'], [form_view_id, 'form']],
            'target': action.target,
            'context': action.context,
            'res_model': action.res_model,
        }
        if len(credit_note) > 1:
            result['domain'] = "[('id','in',%s)]" % credit_note.ids
        elif len(credit_note) == 1:
            result['views'] = [(form_view_id, 'form')]
            result['res_id'] = credit_note.ids[0]
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    @api.one
    def _get_total_credit_note(self):
        """
        Obtenemos el total de notas de crédito en factura
        """
        total = 0.00
        if self.have_credit_note:
            notes_credit = self.env['account.invoice'].search([('invoice_reference', '=', self.id)])
            for note in notes_credit:
                total = total + note.amount_total
        self.total_credit_note = total

    @api.multi
    def _get_have_credit_note(self):
        """
        Obtenemos si factura tiene notas de crédito
        """
        for record in self:
            notes_credit = self.env['account.invoice'].search([('invoice_reference', '=', record.id)])
            record.have_credit_note = True if notes_credit else False

    invoice_reference = fields.Many2one('account.invoice', string='Referencia de factura')
    total_credit_note = fields.Monetary(string="Total notas de crédito", compute='_get_total_credit_note')
    have_credit_note = fields.Boolean(string='Tiene nota de crédito?', compute='_get_have_credit_note')
    state_notes = fields.Selection([
        ('draft', 'Borrador'),
        ('posted', 'Contabilizado'),
        ('cancel', 'Anulada')], string="Estado", default='draft')
