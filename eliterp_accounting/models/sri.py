# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models, _
from datetime import date, datetime
from odoo.exceptions import UserError, ValidationError
import re


class TypeDocument(models.Model):
    _name = 'eliterp.type.document'
    _description = 'Tipos de documento'

    @api.multi
    def name_get(self):
        res = []
        for data in self:
            res.append((data.id, "%s [%s]" % (data.name, data.code)))
        return res

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código', size=2, required=True)
    tax_support_ids = fields.Many2many('eliterp.tax.support',
                                       'relation_type_document_tax_support_ids',
                                       'type_document_id',
                                       'tax_support_id',
                                       string='Sustentos tributarios')
    have_authorization = fields.Boolean('Tiene autorización?', default=False,
                                        help='Marcar si el Tipo de documento tiene Autorización del SRI')
    _sql_constraints = [
        ('code_unique', 'unique (code)', 'El Código del Tipo de documento debe ser único.')
    ]


class TaxSupport(models.Model):
    _name = 'eliterp.tax.support'
    _description = 'Sustento tributario'
    _order = "code asc"

    @api.multi
    def name_get(self):
        res = []
        for data in self:
            res.append((data.id, "%s [%s]" % (data.name, data.code)))
        return res

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código', size=2, required=True)

    _sql_constraints = [
        ('code_unique', 'unique (code)', 'El Código del Sustento tributario debe ser único.')
    ]


class SriPointPrinting(models.Model):
    _name = 'sri.point.printing'
    _description = _("Punto de impresión SRI")

    @api.one
    def _get_authorization(self, type_voucher=None):
        """
        Verificamos si tiene autorización del SRI y seleccionamos la primer qué encuentre
        esste método sirve para asegurarnos de qué exista al menos una (físicas).
        :param type_voucher:
        :return:
        """
        sri_authorization = self.env['eliterp.sri.authorization'].search([
            ('point_printing_id', '=', self.id),
            ('type_document.code', '=', type_voucher),
            ('is_valid', '=', True)
        ], limit=1)
        if not sri_authorization:
            raise UserError(_(
                'No ha configurado la autorización del SRI para este punto de impresión (%s). O la misma puede estar '
                'vencida.' %
                self.name))
        else:
            return sri_authorization

    @api.constrains('name')
    def _check_name(self):
        """
        Verificamos qué número de serie de proveedores sea correcto
        :return:
        """
        if not re.match("\d{3,}-\d{3,}", self.name):
            raise ValidationError("Nº de punto de impresión debe tener formato 001-001.")

    name = fields.Char('Punto de impresión', size=7, default='001-001', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.user.company_id)

    _sql_constraints = [
        ('name_unique', 'unique(name, company_id)',
         "El punto de impresión debe ser único por compañía!")
    ]


class SriAuthorization(models.Model):
    _name = 'eliterp.sri.authorization'
    _description = 'Autorizaciones del SRI'

    @api.multi
    def set_not_active(self):
        """
        Desactivamos
        """
        self.active = False

    @api.multi
    def name_get(self):
        res = []
        for data in self:
            res.append((data.id, "Comprobante %s [%s]" % (data.type_document.code, data.authorization)))
        return res

    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self, values):
        if values['is_electronic']:
            return super(SriAuthorization, self).create(values)
        result = self.search([
            ('company_id', '=', values['company_id']),
            ('type_document', '=', values['type_document']),
            ('point_printing_id', '=', values['point_printing_id']),
            ('is_electronic', '=', False),
            ('active', '=', True)
        ])
        if result:
            MESSAGE = 'Ya existe una Autorización activa parámetros ingresados.'
            raise UserError(_(MESSAGE))
        partner_id = self.env.user.company_id.partner_id.id
        if values['company_id'] == partner_id:
            authorization = values['authorization']
            number_next = values['initial_number']
            new_sequence = self.env['ir.sequence'].sudo().create({
                'name': "Secuencia de autorización " + authorization,
                'number_next': number_next,
                'code': authorization,
                'prefix': values['point_printing_id'],
                'padding': 9
            })
            values.update({'sequence_id': new_sequence.id})
        return super(SriAuthorization, self).create(values)

    @api.one
    @api.depends('expiration_date')
    def _get_status(self):
        """
        Confirmamos si la Autorización del SRI está vencida
        :return: self
        """
        if not self.expiration_date and not self.is_electronic:
            return
        self.active = date.today() < datetime.strptime(self.expiration_date, '%Y-%m-%d').date()

    @api.multi
    def unlink(self):
        """
        Al borrar Autorización verificar no existan documentos asociados
        """
        invoices = self.env['account.invoice']
        for record in self:
            result = invoices.search([('sri_authorization_id', '=', record.id)])
            if result:
                raise ValidationError("Está autorización %s está relacionada a un documento." % record.authorization)
        return super(SriAuthorization, self).unlink()

    def _get_company(self):
        return self.env.user.company_id

    def is_valid_number(self, number):
        """
        Verificar si el número de la secuencia es válido
        :param number:
        :return: boolean
        """
        if self.initial_number <= number <= self.final_number:
            return True
        return False

    establishment = fields.Char('No. Establecimiento', size=3, default='001', required=True)
    emission_point = fields.Char('Punto emisión', size=3, default='001', required=True)
    initial_number = fields.Integer('No. inicial', default=1, required=True)
    final_number = fields.Integer('No. final', required=True)
    authorization = fields.Char('No. Autorización', required=True)
    type_document = fields.Many2one('eliterp.type.document', 'Tipo de documento',
                                    domain=[('have_authorization', '=', True)], required=True)
    code = fields.Char(related='type_document.code', string='Código de documento')
    expiration_date = fields.Date('Fecha de expiración', required=True)
    active = fields.Boolean('Activo?', compute='_get_status', store=True)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=_get_company)
    sequence_id = fields.Many2one('ir.sequence', 'Secuencia')
    point_printing_id = fields.Many2one('sri.point.printing', string='Punto de impresión', required=True)
    is_electronic = fields.Boolean('Electrónica', default=False,
                                   help="Técnico: Campo determina si es autorización electrónica.")

    _sql_constraints = [(
        'sri_authorization_unique',
        'CHECK(1=1)',
        'Ya existe una Autorización activa del SRI para estos parámetros.'
    )]


class WayPay(models.Model):
    _name = 'eliterp.way.pay'
    _description = 'Forma de pago'
    _order = "code asc"

    @api.multi
    def name_get(self):
        res = []
        for data in self:
            res.append((data.id, "%s [%s]" % (data.name, data.code)))
        return res

    name = fields.Char('Nombre', required=True)
    code = fields.Char('Código', size=2, required=True)

    _sql_constraints = [
        ('code_unique', 'unique (code)', 'El Código de Forma de pago debe ser único.')
    ]


class ResCompany(models.Model):
    _inherit = 'res.company'

    authorization_ids = fields.One2many(
        'eliterp.sri.authorization',
        'company_id',
        string='Autorizaciones del SRI'
    )

    @api.multi
    def _get_authorisation(self, type_document):
        """
        Obtenemos la autorización del SRI por código de documento
        :param type_document:
        """
        map_type = {
            'out_refund': '04',
            'retention_in_invoice': '07',
            'out_invoice': '18',
        }
        code = map_type[type_document]
        for authorisation in self.authorization_ids:
            if authorisation.active and authorisation.code == code:
                return authorisation
        return False


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    ISSUANCE_DOCUMENTS = ['out_invoice', 'out_refund']  # Factura de venta, Nota de crédito en venta...

    @api.onchange('journal_id', 'sri_authorization_id')
    def _onchange_journal_id(self):
        """
        Obtener la el número de la secuencia del documento
        :return: self
        """
        super(AccountInvoice, self)._onchange_journal_id()
        if self.journal_id and self.type in self.ISSUANCE_DOCUMENTS:
            authorisation = self.env.user.company_id._get_authorisation(self.type)
            if authorisation:
                if self.type == 'out_invoice':
                    self.sri_authorization_id = authorisation.id
                elif self.type == 'out_refund':
                    self.sri_authorization_id = authorisation.id
                self.authorization = not self.sri_authorization_id.is_electronic and self.sri_authorization_id.authorization
                number = '{0}'.format(str(self.sri_authorization_id.sequence_id.number_next_actual).zfill(9))
                self.reference = number
        else:
            self.sri_authorization_id = False

    @api.one
    @api.depends('sri_authorization_id', 'reference')
    def _compute_invoice_number(self):
        """
        Calcular el número de documento
        :return: self
        """
        if self.reference:
            self.invoice_number = '{0}-{1}-{2}'.format(
                self.sri_authorization_id.establishment if self.sri_authorization_id else self.establishment,
                self.sri_authorization_id.emission_point if self.sri_authorization_id else self.emission_point,
                self.reference
            )
        else:
            self.invoice_number = False

    @api.onchange('reference')
    def _onchange_reference(self):
        """
        Validar número para rango de Autorización
        """
        if self.reference:
            self.reference = self.reference.zfill(9)
            if not self.sri_authorization_id.is_valid_number(
                    int(self.reference)) and self.type in self.ISSUANCE_DOCUMENTS:
                return {
                    'value': {
                        'reference': ''
                    },
                    'warning': {
                        'title': 'Error',
                        'message': 'Número no coincide con la autorización ingresada.'
                    }
                }

    @api.constrains('authorization')
    def _check_authorization(self):
        """
        Verificar la longitud de la autorización
        10: Documento físico
        35: Documento electrónico, online
        49: Documento electrónico, offline
        """
        if self.type not in ['in_invoice']:
            return
        if self.authorization and len(self.authorization) not in [10, 35, 49]:
            raise ValidationError('Debe ingresar 10, 35 o 49 dígitos según el documento.')

    def _default_way_pay(self):
        """
        Obtenemos forma de pago por defecto 20
        """
        return self.env['eliterp.way.pay'].search([('code', '=', '20')])[0].id

    def _default_tax_support(self):
        """
        Obtenemos sustento tributario por defecto
        """
        dtype = self._context.get('type')
        if dtype in ['in_invoice', 'in_refund']:
            return self.env['eliterp.tax.support'].search([])[0].id

    @api.model
    def _default_authorized_voucher(self):
        context = dict(self._context or {})
        object_voucher = self.env['eliterp.type.document']
        voucher = False
        if context.get('type') and not context.get('default_authorized_voucher'):
            DocumentType = context.get('type')
            if DocumentType == 'in_invoice':
                code = '01'
            elif DocumentType == 'out_invoice':
                code = '18'
            elif DocumentType == 'in_refund':
                code = '04'
            else:
                code = '04'
            voucher = object_voucher.search([('code', '=', code)])
        elif context.get('default_authorized_voucher'):
            voucher = object_voucher.search([
                ('code', '=', context.get('default_authorized_voucher'))
            ])
        return voucher.id if voucher else False

    way_pay_id = fields.Many2one('eliterp.way.pay', string='Forma de pago',
                                 default=lambda self: self._default_way_pay())
    authorized_voucher_id = fields.Many2one('eliterp.type.document', 'Tipo de comprobante',
                                            readonly=True, states={'draft': [('readonly', False)]},
                                            default=_default_authorized_voucher)
    point_printing_id = fields.Many2one('sri.point.printing', string='Punto de impresión', readonly=True,
                                        states={'draft': [('readonly', False)]})
    sri_authorization_id = fields.Many2one('eliterp.sri.authorization', string='Autorización del SRI', copy=False,
                                           readonly=True,
                                           states={'draft': [('readonly', False)]})
    authorization = fields.Char('No. Autorización', readonly=True,
                                states={'draft': [('readonly', False)]})
    invoice_number = fields.Char('No. Factura', compute='_compute_invoice_number', store=True, readonly=True,
                                 copy=False)
    tax_support_id = fields.Many2one('eliterp.tax.support', string='Sustento tributario',
                                     default=lambda self: self._default_tax_support())
    # Campos para documentos no emitidos por Companía
    establishment = fields.Char('No. Establecimiento', size=3, default='001', readonly=True,
                                states={'draft': [('readonly', False)]})
    emission_point = fields.Char('Punto emisión', size=3, default='001', readonly=True,
                                 states={'draft': [('readonly', False)]})

    _sql_constraints = [(
        'invoice_unique', 'CHECK(1=1)',
        'El No. Factura es único por autorización y empresa.'
    )]


class TributaryCredit(models.Model):
    _name = 'eliterp.tributary.credit'

    _description = 'Crédito tributario'

    @api.depends('name')
    def _compute_year(self):
        """
        Obtenemos el año
        """
        for record in self:
            record.year = record.name.period_id.year_accounting

    name = fields.Many2one('eliterp.lines.account.period', string='Período', domain=[('active', '=', True
                                                                                      )])
    month = fields.Integer('Mes', related='name.code', readonly=True, store=True)
    year = fields.Integer('Año contable', compute='_compute_year', store=True)
    amount_iva = fields.Float("Valor IVA", required=True)
    amount_rent = fields.Float("Valor retención", required=True)

    _sql_constraints = [(
        'tributary_credit_unique', 'unique (name)',
        'Ya se registró crédito tributario correspondiente a este período.'
    )]
