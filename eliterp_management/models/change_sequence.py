# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class ChangeSequence(models.Model):
    _name = 'eliterp.change.sequence'
    _description = 'Cambiar secuencia de documentos'

    @api.multi
    def change_sequence(self):
        """
        Realizamos la operación para cambiar
        :return:
        """
        table = self.model_id.model
        order_by = '%s %s' % (self.sorty_by.name, self.type_ordering)
        if table in ['purchase.order', 'eliterp.pay.order', 'eliterp.payment.request',
                     'eliterp.liquidation.settlement']:
            records = self.env[table].search([], order=order_by)
        else:
            if table == 'account.payment':
                records = self.env[table].search([('payment_type_customize', '=', self.payment_type_customize)],
                                                 order=order_by)
            if table == 'eliterp.credit.debit.notes':
                records = self.env[table].search([('type', '=', 'debit')],
                                                 order=order_by)
            if table == 'eliterp.withhold':
                records = self.env[table].search([('type', '=', self.retention_type)],
                                                 order=order_by)
            if table == 'account.invoice':
                records = self.env[table].search([('type', '=', self.invoice_type), ('is_sale_note', '=', False)],
                                                 order=order_by)
            if table == 'account.voucher':
                if self.voucher_type == 'sale':
                    records = self.env[table].search([('voucher_type', '=', 'sale')],
                                                     order=order_by)
                else:
                    records = self.env[table].search(
                        [('voucher_type', '=', 'purchase'), ('type_egress', 'in', ['bank', 'transfer'])],
                        order=order_by)
        for register in records:
            new_name = self.env['ir.sequence'].next_by_code(self.sequence_id.code)  # Nueva secuencia
            # COMPRAS
            if table == 'purchase.order':
                register.update({'%s' % self.field_change.name: new_name})
                for invoice in register.invoice_ids:
                    invoice.update({'origin': new_name})
                for pay in register.lines_pay_order:
                    pay.update({'origin': new_name})
            # ORDEN DE PAGO
            if table == 'eliterp.pay.order':
                month = register.date[5:7]
                new_name = new_name[0:9] + month + new_name[11:]
                register.update({'%s' % self.field_change.name: new_name})
            # REQUERIMIENTO DE PAGO, TODO: No actualiza el origen de orden de pago
            if table == 'eliterp.payment.request':
                month = register.application_date[5:7]
                new_name = new_name[0:9] + month + new_name[11:]
                register.update({'%s' % self.field_change.name: new_name})
                for pay in register.lines_pay_order:
                    pay.write({'origin': new_name})
            # LIQUIDACIÓN DE VIÁTICOS (MOVIMENTO CONTABLE)
            if table == 'eliterp.liquidation.settlement':
                month = register.date[5:7]
                new_name = new_name[0:9] + month + new_name[11:]
                register.update({'%s' % self.field_change.name: new_name})
                for pay in register.lines_pay_order:
                    pay.update({'origin': new_name})
                if register.move_id:
                    register.move_id.update({'name': new_name})
            # DEPÓSITOS, TRANSFERENCIAS (MOVIMENTO CONTABLE)
            if table == 'account.payment':
                month = register.payment_date[5:7]
                new_name = new_name[0:9] + month + new_name[11:]
                register.update({'%s' % self.field_change.name: new_name})
                if register.move_id:
                    register.move_id.update({'name': new_name})
            # NOTAS DE CRÉDITO BANCARIAS (MOVIMENTO CONTABLE)
            if table == 'eliterp.credit.debit.notes':
                month = register.date[5:7]
                new_name = new_name[0:9] + month + new_name[11:]
                register.update({'%s' % self.field_change.name: new_name})
                if register.move_id:
                    register.move_id.update({'name': new_name})
            # RETENCIONES, SOLÓ CON VENTAS TIENEN ASIENTO CONTABLE
            if table == 'eliterp.withhold':
                month = register.date_withhold[5:7]
                new_name = new_name[0:9] + month + new_name[11:]
                register.update({'%s' % self.field_change.name: new_name})
                if register.move_id:
                    register.move_id.update({'name': new_name})
            # FACTURAS, NOTAS DE CRÉDITO, TODO: Notas de venta directo en el sistema son pocas
            # update account_invoice set number = null;
            # Colocar códigos invoice.sale, invoice.purchase
            if table == 'account.invoice':
                for pay in register.lines_pay_order:  # Soló las qué son de una factura actualizamos el origen
                    if pay.invoice_ids:
                        pay.update({'origin': ', '.join(str(i.number) for i in pay.invoice_ids)})
            # Pagos, Cobros
            if table == 'account.voucher':
                if self.voucher_type == 'sale':
                    month = register.date[5:7]
                    new_name = new_name[0:9] + month + new_name[11:]
                    register.update({'%s' % self.field_change.name: new_name})
                else:
                    if self.type_egress == 'cash':
                        new_name = "CEG-MQEFC-2018-" + new_name
                    elif self.type_egress == 'credit_card':
                        new_name = "CEG-MQTAR-2018-" + new_name
                    else:
                        new_name = "CE-MQ-" + register.bank_id.exit_code + "-2018-" + register.bank_id.transfer_sequence_id.next_by_id()
                    register.update({'%s' % self.field_change.name: new_name})
                    if register.move_id:
                        register.move_id.update({'name': new_name})

    name = fields.Char('Nombre', default='Cambio')
    model_id = fields.Many2one('ir.model', 'Modelo', required=True, domain=[('transient', '=', False)])
    sequence_id = fields.Many2one('ir.sequence', 'Secuencia de cambio', required=True)
    sorty_by = fields.Many2one('ir.model.fields', 'Ordenar por', help="Campos de tipo fecha y fecha y hora.")
    field_change = fields.Many2one('ir.model.fields', 'Campo a cambiar', required=True)
    type_ordering = fields.Selection([('asc', 'Ascendente'), ('desc', 'Descendiente')], default='asc',
                                     string='Tipo de ordenamiento')
    model = fields.Char(related='model_id.model', store=True)
    payment_type_customize = fields.Selection([
        ('deposit', 'Depósito'),
        ('transfer', 'Transferencia'),
    ], string='Depósitos, transferencias')
    retention_type = fields.Selection([('sale', 'Venta'), ('purchase', 'Compra')], string='Retenciones')
    invoice_type = fields.Selection([
        ('out_invoice', 'FACC'),
        ('in_invoice', 'FAPL'),
        ('in_refund', 'NCPL'),
    ], string='Facturas')
    voucher_type = fields.Selection([
        ('sale', 'Sale'),
        ('purchase', 'Purchase')
    ], string='Voucher')
    type_egress = fields.Selection([
        ('cash', 'Efectivo'),
        ('bank', 'Cheque'),
        ('transfer', 'Transferencia'),
        ('credit_card', 'Tarjeta de crédito')
    ], string='Forma de pago', default='cash')
