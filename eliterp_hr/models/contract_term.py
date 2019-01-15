# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models, fields, api
from odoo.exceptions import UserError

STATES = [
    ('draft', 'Borrador'),
    ('validate', 'Validado'),
    ('cancel', 'Anulado')
]


class ContractTerm(models.Model):
    _name = 'eliterp.contract.term'

    _description = 'Termino de contrato'

    @api.multi
    def unlink(self):
        for payment in self:
            if payment.state != 'draft':
                raise UserError("No se puede eliminar un termino de contrato diferente a estado borrador.")
        return super(ContractTerm, self).unlink()

    @api.multi
    def validate(self):
        new_name = self.env['ir.sequence'].next_by_code('hr.contractter')
        self.write({
            'state': 'validate',
            'name': new_name
        })

    @api.model
    def _get_wage_letters(self):
        """
        Obtenemos el monto en letras
        """
        amount_text = self.env['report.eliterp_treasury.eliterp_report_check_voucher_xlsx']
        dollar = amount_text.get_amount_to_word(self.renumbering)
        return dollar.upper()

    @api.model
    def _get_date_formatlarge(self):
        return self.env['eliterp.global.functions'].get_date_format_invoice1(self.admission_date)

    @api.model
    def _get_date_formatlarges(self):
        return self.env['eliterp.global.functions'].get_date_format_invoicesindia(self.admission_date)

    @api.multi
    def imprimir_contract_term(self):
        """
        Imprimimo Termino de contrato
        """
        self.ensure_one()
        return self.env.ref('eliterp_hr.eliterp_action_report_contract_term').report_action(self)

    @api.onchange('employee')
    def _onchange_employee(self):
        if self.employee:
            self.renumbering = self.employee.wage

    date = fields.Date('Fecha documento', default=fields.Date.context_today, required=True, readonly=True,
                       states={'draft': [('readonly', False)]})
    name = fields.Char('No. Documento')
    employee = fields.Many2one('hr.employee', string='Empleado', readonly=True,
                               required=True,
                               states={'draft': [('readonly', False)]})
    renumbering = fields.Float(string='Remuneración')
    identification_id = fields.Char(related='employee.identification_id', string='No. identificación')
    admission_date = fields.Date(related='employee.admission_date', string='Fecha de ingreso')
    state = fields.Selection(STATES, string='Estado', default='draft')
    comment = fields.Text('Texto Libre')
    number_hectares = fields.Char(string = 'Nº hectáreas')
