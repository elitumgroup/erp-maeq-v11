# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from datetime import datetime
from odoo import fields, api, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('product_id')
    def onchange_product_id(self):
        result = {}
        if not self.product_id:
            return result

        # Reset date, price and quantity since _onchange_quantity will provide default values
        self.date_planned = datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        self.price_unit = self.product_qty = 0.0
        self.product_uom = self.product_id.uom_po_id or self.product_id.uom_id
        result['domain'] = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}

        product_lang = self.product_id.with_context(
            lang=self.partner_id.lang,
            partner_id=self.partner_id.id,
        )
        self.name = product_lang.display_name
        if product_lang.description_purchase:  # MARZ
            self.name = product_lang.description_purchase

        fpos = self.order_id.fiscal_position_id
        if self.env.uid == SUPERUSER_ID:
            company_id = self.env.user.company_id.id
            self.taxes_id = fpos.map_tax(
                self.product_id.supplier_taxes_id.filtered(lambda r: r.company_id.id == company_id))
        else:
            self.taxes_id = fpos.map_tax(self.product_id.supplier_taxes_id)

        self._suggest_quantity()
        self._onchange_quantity()

        return result


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    name = fields.Char('Order Reference', required=True, index=True, copy=False, default='Nueva orden')

    @api.multi
    def action_rfq_send(self):
        """
        Le cambiamos el estado a SDP enviada
        :return:
        """
        res = super(PurchaseOrder, self).action_rfq_send()
        self.write({
            'state': 'sent'
        })
        return res

    @api.multi
    def to_approve(self):
        """
        Solicitar aprobación de orden de compra
        """
        self.update({'state': 'to approve'})
        # Enviar correo a usuarios para aprobación
        self.env['eliterp.managerial.helps'].send_mail(self.id, self._name, 'eliterp_approve_purchase_order_mail')

    @api.multi
    def button_confirm(self):
        """
        Agregamos confirmación de OC
        :return: object
        """
        res = super(PurchaseOrder, self).button_confirm()
        self.write({
            'state': 'purchase',
            'approval_user': self._uid
        })
        return res

    @api.multi
    def approve(self):
        """
        Aprobar orden de compra
        """
        self.update({
            'state': 'approve',
        })


    @api.multi
    def button_new_cancel(self):
        for order in self:
            if order.state_pay_order != 'generated':
                raise UserError(_("No se puede anular OCS con pagos realizados."))
            for inv in order.invoice_ids:
                if inv and inv.state not in ('cancel', 'draft'):
                    raise UserError(_("No se puede anular OCS con facturas por pagar o pagadas."))

        self.write({'state': 'cancel'})

    reference = fields.Char('Referencia', track_visibility='onchange')
    notes = fields.Text('Terms and Conditions', track_visibility='onchange')
    attach_order = fields.Binary('Adjuntar documento', attachment=True, track_visibility='onchange')
    # CM
    invoice_status = fields.Selection([
        ('no', 'Pendiente'),
        ('to invoice', 'Para facturar'),
        ('invoiced', 'Facturado'),
    ], string='Estado de facturación', compute='_get_invoiced', store=True, readonly=True, copy=False, default='no', track_visibility='onchange')
    approval_user = fields.Many2one('res.users', 'Aprobado por')
    state = fields.Selection([
        ('draft', 'SDP Borrador'),
        ('sent', 'SDP Enviada'),
        ('approve', 'Orden de compra'),
        ('to approve', 'OCS por aprobar'),
        ('purchase', 'OCS Aprobado'),
        ('done', 'Bloqueado'),
        ('cancel', 'Negado')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', track_visibility='onchange')

    # Campos modifcada la trazabilidad
    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    partner_id = fields.Many2one('res.partner', string='Vendor', required=True, states=READONLY_STATES, change_default=True, track_visibility='onchange')
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all', track_visibility='onchange')
