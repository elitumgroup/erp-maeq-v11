# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo.exceptions import UserError
from odoo import api, fields, models, _
from datetime import date, datetime
import calendar
from odoo.osv import expression

YEARS = [
    (2015, '2015'),
    (2016, '2016'),
    (2017, '2017'),
    (2018, '2018'),
    (2019, '2019'),
    (2020, '2020'),
    (2021, '2021'),
    (2022, '2022'),
    (2023, '2023'),
    (2024, '2024'),
    (2025, '2025'),
]


class AccountTemplate(models.Model):
    _inherit = 'account.account.template'

    account_type = fields.Selection([
        ('view', 'Vista'),
        ('movement', 'Movimiento'),
    ], 'Tipo de cuenta', required=True, default='movement')


class LinesAccountPeriod(models.Model):
    _name = 'eliterp.lines.account.period'

    _description = 'Líneas de Período contable'

    @api.depends('closing_date')
    @api.one
    def _get_status(self):
        """
        Validamos si período está activo
        """
        self.active = datetime.strptime(self.closing_date, '%Y-%m-%d').date() > datetime.today().date()

    name = fields.Char('Nombre')
    month = fields.Char('Mes')
    code = fields.Integer('Código')
    start_date = fields.Date('Fecha inicio')
    closing_date = fields.Date('Fecha cierre')
    active = fields.Boolean('Activo?', compute='_get_status')
    period_id = fields.Many2one('eliterp.account.period', 'Año contable')


class AccountPeriod(models.Model):
    _name = 'eliterp.account.period'
    _description = 'Período contable'

    @api.multi
    def load_months(self):
        """
        Generamos Líneas de período contable
        :return: self
        """
        global_functions = self.env['eliterp.global.functions']
        if len(self.lines_period) >= 12:
            raise UserError("No puede asignar más meses al año Contable.")
        list = []
        for x in range(1, 13):
            list.append([0, 0, {
                'code': x,
                'name': global_functions._get_month_name(x) + " del " + str(self.year_accounting),
                'month': global_functions._get_month_name(x),
                'start_date': date(int(self.year_accounting), x, 1),
                'closing_date': global_functions._get_last_day_month(date(int(self.year_accounting), x, 1))
            }])
        return self.update({'lines_period': list, 'name': 'Año [%s]' % self.year_accounting})

    @api.onchange('year_accounting')
    def _onchange_year_accounting(self):
        """
        Generamos un rango de fechas por defecto
        :return: self
        """
        if self.year_accounting:
            self.start_date = date(self.year_accounting, 1, 1)
            self.closing_date = date(self.year_accounting, 12, 31)

    name = fields.Char('Nombre')
    year_accounting = fields.Selection(YEARS, string='Año contable', required=True)
    start_date = fields.Date('Fecha inicio', required=True)
    closing_date = fields.Date('Fecha cierre', required=True)
    lines_period = fields.One2many('eliterp.lines.account.period', 'period_id', string='Líneas de Período contable')


class AccountAccountType(models.Model):
    _inherit = 'account.account.type'

    # Campo modificado
    type = fields.Selection(selection_add=[('bank', 'Banco')])


class AccountAccount(models.Model):
    _inherit = 'account.account'

    @api.multi
    @api.depends('name', 'code', 'description')
    def name_get(self):
        result = []
        for account in self:
            if account.description:
                name = '%s %s [%s]' % (account.code, account.name, account.description)
            else:
                name = account.code + ' ' + account.name
            result.append((account.id, name))
        return result

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', ('code', '=ilike', name + '%'), ('name', operator, name),
                      ('description', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        accounts = self.search(domain + args, limit=limit)
        return accounts.name_get()

    account_type = fields.Selection([
        ('view', 'Vista'),
        ('movement', 'Movimiento'),
    ], 'Tipo de cuenta', required=True, default='movement')
    description = fields.Char('Descripción')


class AccountCommonReport(models.TransientModel):
    _inherit = "account.common.report"

    # CM
    target_move = fields.Selection([('posted', 'All Posted Entries'),
                                    ('all', 'All Entries'),
                                    ], string='Target Moves', required=True, default='all')


class WebPlanner(models.Model):
    _inherit = 'web.planner'

    def _prepare_planner_account_data(self):
        """
        MM
        :return: dict
        """
        values = {
            'company_id': self.env.user.company_id,
            'is_coa_installed': bool(self.env['account.account'].search_count([])),
            'payment_term': self.env['account.payment.term'].search([])
        }
        return values


class Bank(models.Model):
    _inherit = 'res.bank'

    @api.one
    def _create_check_sequence(self):
        """
        Creamos la secuencia de cheques del banco
        :return:
        """
        self.check_sequence_id = self.env['ir.sequence'].sudo().create({
            'name': "Secuencia de cheque: " + self.name,
            'implementation': 'no_gap',
            'padding': self.padding,
            'number_increment': 1,
            'number_next_actual': self.start,
            'company_id': self.env.user.company_id.id,
        })

    @api.model
    def create(self, vals):
        rec = super(Bank, self).create(vals)
        if not rec.check_sequence_id and rec.type_use == 'payments':  # Soló para bancos de pago se crea secuencia de cheque
            rec._create_check_sequence()
        return rec

    @api.one
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """
        Al copiar creamos la secuencia del cheque si es tipo pago
        :param default:
        :return:
        """
        rec = super(Bank, self).copy(default)
        if rec.type_use == 'payments':
            rec._create_check_sequence()
        return rec

    @api.multi
    def write(self, vals):
        """
        Cambiar consecutivo de cheque al modificar el inicio
        :param vals:
        :return:
        """
        if 'start' in vals:
            self.check_sequence_id.sudo().update({'number_next_actual': vals['start']})
        return super(Bank, self).write(vals)

    check_sequence_id = fields.Many2one('ir.sequence', 'Secuencia de cheque', copy=False)
    check_next_number = fields.Integer('Siguiente número de cheque', related="check_sequence_id.number_next_actual",
                                       help="Siguiente número qué se va a mostrar en pagos.")

    type_use = fields.Selection([('charges', 'Cobros'), ('payments', 'Pagos'), ('employees', 'Empleados')],
                                string='Tipo de uso', required=True,
                                default='charges')
    account_id = fields.Many2one('account.account', string='Cuenta contable',
                                 domain=[('account_type', '=', 'movement')], copy=False)
    account_number = fields.Char('No. Cuenta', copy=False)
    start = fields.Integer('Inicio', default=1, copy=False)
    padding = fields.Integer('Dígitos', default=6, help="Cantidad de dígitos en el talonario de la chequera")
    state_id = fields.Many2one("res.country.state", string='Provincia')
    code = fields.Char('Código', size=2, help='Campo qué sirve para generación de archivo SAT.', copy=False)
    transfer_sequence_id = fields.Many2one('ir.sequence', 'Secuencia de transferencia', copy=False)
    exit_code = fields.Char('Código de egreso', help='Código para identificación en egresos (Cheques, Transferencias).',
                            size=3)

    _sql_constraints = [
        ('code_exit_code', 'unique (exit_code)', "El código de egreso es único!")
    ]


class AssetAsset(models.Model):
    _inherit = 'account.asset.asset'

    def _compute_board_amount(self, sequence, residual_amount, amount_to_depr, undone_dotation_number,
                              posted_depreciation_line_ids, total_days, depreciation_date):
        amount = 0
        if sequence == undone_dotation_number:
            amount = residual_amount
        else:
            if self.method == 'linear':
                amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
                if self.fixed_amount and self.prorata:
                    amount = self.amount
                elif self.prorata:
                    amount = amount_to_depr / self.method_number
                    if sequence == 1:  # Se cambió por porrateo de MAEQ (Verónica Mora)
                        if self.method_period % 12 != 0:
                            date = datetime.strptime(self.date, '%Y-%m-%d')
                            month_days = 30
                            days = month_days - date.day
                            amount = (amount_to_depr / self.method_number) / month_days * days
                        else:
                            days = (self.company_id.compute_fiscalyear_dates(depreciation_date)[
                                        'date_to'] - depreciation_date).days + 1
                            amount = (amount_to_depr / self.method_number) / total_days * days
            elif self.method == 'degressive':
                amount = residual_amount * self.method_progress_factor
                if self.prorata:
                    if sequence == 1:
                        if self.method_period % 12 != 0:
                            date = datetime.strptime(self.date, '%Y-%m-%d')
                            month_days = calendar.monthrange(date.year, date.month)[1]
                            days = month_days - date.day + 1
                            amount = (residual_amount * self.method_progress_factor) / month_days * days
                        else:
                            days = (self.company_id.compute_fiscalyear_dates(depreciation_date)[
                                        'date_to'] - depreciation_date).days + 1
                            amount = (residual_amount * self.method_progress_factor) / total_days * days
        return amount

    fixed_amount = fields.Boolean('Monto fijo?', defualt=False)
    amount = fields.Float('Monto')
