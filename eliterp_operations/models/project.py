# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models, fields, api, _
import json


class Location(models.Model):
    _name = 'eliterp.location'

    _description = 'Ubicaciones'

    @api.model
    def name_get(self):
        result = []
        for data in self:
            if data.project_id:
                result.append((data.id, "%s [%s]" % (data.name, data.project_id.name)))
            else:
                result.append((data.id, data.name))
        return result

    name = fields.Char('Nombre ubicación', required=True)
    project_id = fields.Many2one('eliterp.project', string='Proyecto')


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    project_id = fields.Many2one('eliterp.project', 'Proyecto', readonly=True, track_visibility='onchange',
                                 states={'draft': [('readonly', False)]})

    @api.multi
    def finalize_invoice_move_lines(self, move_lines):
        for r in move_lines:  # Si son la misma fila actualizar proyecto
            for line in self.invoice_line_ids:
                if r[2]['analytic_account_id'] == line.account_analytic_id.id and line.project_id:
                    r[2].update({'project_id': line.project_id.id})
        return move_lines


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    project_id = fields.Many2one('eliterp.project', 'Proyecto', track_visibility='onchange')
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo", track_visibility='onchange')


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_id = fields.Many2one('eliterp.project', 'Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, required=True, track_visibility='onchange')
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo", track_visibility='onchange')


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    project_id = fields.Many2one('eliterp.project', 'Proyecto', track_visibility='onchange')
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo", track_visibility='onchange')


class TravelAllowanceRequest(models.Model):
    _inherit = 'eliterp.travel.allowance.request'

    project_id = fields.Many2one('eliterp.project', 'Proyecto', required=True, track_visibility='onchange')


class EliterpProject(models.Model):
    _name = 'eliterp.project'

    _description = 'Proyecto'

    @api.multi
    def name_get(self):
        res = []
        for data in self:
            res.append((data.id, "%s [%s]" % (data.code, data.name)))
        return res

    name = fields.Char('Nombre de proyecto', required=True)
    code = fields.Char('Código', required=True)
    reference = fields.Char('Referencia')
    customer = fields.Many2one('res.partner', string="Cliente",
                               domain=[('is_contact', '=', False), ('customer', '=', True)])
    lines_location = fields.One2many('eliterp.location', 'project_id', string='Ubicaciones')

    _sql_constraints = [
        ('code_unique', 'unique (code)', "El Código del proyecto debe ser único.")
    ]


class StatusResultsReport(models.TransientModel):
    _inherit = 'eliterp.status.results.report'

    project_id = fields.Many2one('eliterp.project', 'Proyecto')
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo")

# Manejar esto por MAEQ (Línea dónde se selecciona la cuenta)
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    project_id = fields.Many2one('eliterp.project', 'Proyecto')


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    project_id = fields.Many2one('eliterp.project', 'Proyecto')


class LinesDepositsCheck(models.Model):
    _inherit = 'eliterp.lines.deposits.check'

    project_id = fields.Many2one('eliterp.project', 'Proyecto')
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo")


class LinesDepositsCash(models.Model):
    _inherit = 'eliterp.lines.deposits.cash'

    project_id = fields.Many2one('eliterp.project', 'Proyecto')
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo")


class LineDepositsChecksExternal(models.Model):
    _inherit = 'eliterp.lines.deposits.checks.external'

    project_id = fields.Many2one('eliterp.project', 'Proyecto')
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo")


class LinesAccount(models.Model):
    _inherit = 'eliterp.lines.account'

    project_id = fields.Many2one('eliterp.project', 'Proyecto')
    account_analytic_id = fields.Many2one('account.analytic.account', domain=[('usage', '=', 'movement')],
                                          string="Centro de costo")


class PayWizard(models.TransientModel):
    _inherit = 'eliterp.pay.wizard'

    project_id = fields.Many2one('eliterp.project', string='Proyecto')
    account_analytic_id = fields.Many2one('account.analytic.account', string='Centro de costo')


class PayOrder(models.Model):
    _inherit = 'eliterp.pay.order'

    project_id = fields.Many2one('eliterp.project', string='Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')


class PaymentRequest(models.Model):
    _inherit = 'eliterp.payment.request'

    project_id = fields.Many2one('eliterp.project', string='Proyecto', required=True, track_visibility='onchange')


class LiquidationSettlement(models.Model):
    _inherit = 'eliterp.liquidation.settlement'

    project_id = fields.Many2one('eliterp.project', string='Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, required=True, track_visibility='onchange')
    account_analytic_id = fields.Many2one('account.analytic.account', string='Centro de costo', readonly=True,
                                          states={'draft': [('readonly', False)]}, track_visibility='onchange')


class Attendance(models.Model):
    _inherit = 'eliterp.attendance'

    project_id = fields.Many2one('eliterp.project', string='Proyecto', readonly=True,
                                 states={'draft': [('readonly', False)]}, track_visibility='onchange')


class PayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    project_id = fields.Many2one('eliterp.project', string='Proyecto', track_visibility='onchange')


class AdvancePayment(models.Model):
    _inherit = 'eliterp.advance.payment'

    project_id = fields.Many2one('eliterp.project', string='Proyecto', track_visibility='onchange')
