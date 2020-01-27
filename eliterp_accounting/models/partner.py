# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from odoo.exceptions import ValidationError

list_type_documentation = [
    ('04', 'RUC'),
    ('05', 'Cédula'),
    ('06', 'Pasaporte'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """
        Cambiamos en vista lista el label de columnas
        :param view_id:
        :param view_type:
        :param toolbar:
        :param submenu:
        :return: object
        """
        res = super(ResPartner, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                      submenu=submenu)
        if view_type == 'tree':
            context = self._context.copy()
            if 'search_default_customer' in context:
                res['fields']['display_name'].update({'string': 'Cliente'})
            if 'search_default_supplier' in context:
                res['fields']['display_name'].update({'string': 'Proveedor'})
        return res

    @api.onchange('documentation_number')
    def _onchange_documentation_number(self):
        """
        Actualizamos el campo vat(NIF) al cambiar No. Identificación
        :return: object
        """
        vat = ""
        res = {}
        if self.documentation_number:
            vat = "EC" + self.documentation_number
        res = {'value': {'vat': vat}}
        return res

    @api.constrains('documentation_number')
    def _check_documentation_number(self):
        """
        Verificar la longitud del documento
        10: Cédula
        13: RUC, Pasaporte
        """
        if not self.documentation_number:
            return True
        if self.documentation_number and len(self.documentation_number) not in [10, 13]:
            raise ValidationError('Debe ingresar 10 o 13 dígitos según el documento.')

    @api.model
    def create(self, vals):
        context = dict(self._context or {})
        if 'if_freelance_sale' in context:
            vals.update({'if_freelance': True})
        if 'parent_id' in vals:
            if vals['parent_id']:
                vals.update({'is_contact': True})
        if 'no_users' in context:
            vals.update({'customer': False, 'supplier': False})
        if not 'no_users' in context:
            partner = self.env['res.partner'].search([('documentation_number', '=', vals['documentation_number'])])
            if partner:
                raise ValidationError("Ya existe No. Identificación en registros.")
        return super(ResPartner, self).create(vals)

    type_documentation = fields.Selection(list_type_documentation, string='Tipo de identificación')
    documentation_number = fields.Char('No. Identificación')
    canton = fields.Many2one('eliterp.canton', string='Cantón')

    parish = fields.Many2one('eliterp.parish', string='Parroquia')
    sex = fields.Selection([('m', 'Masculino'),
                            ('f', 'Femenino'), ], string='Sexo')

    civil_status = fields.Selection([('s', 'Soltero'),
                                     ('c', 'Casado'),
                                     ('d', 'Divorciado'),
                                     ('u', 'Unión libre'),
                                     ('v', 'Viudo'), ], string='Estado civil')
    related_party = fields.Selection([('si', 'Si'),
                                      ('no', 'No')], string='Parte relacionada', default='no')

    @api.model
    def default_get(self, default_fields):
        """
        TODO: Hacemos esto para qué se deba elegir la cuenta de pago o cobro
        :param default_fields:
        :return:
        """
        res = super(ResPartner, self).default_get(default_fields)
        if 'default_supplier' in self._context:
            res['property_account_payable_id'] = False
        else:
            res['property_account_receivable_id'] = False
        return res

    def _default_account_advance(self):
        """
        Por el momento, para generar a la misma cuenta
        """
        if 'default_supplier' in self._context:
            account = self.env['account.account'].search([('name', '=', 'ANTICIPOS A PROVEEDORES')])
        else:
            account = self.env['account.account'].search([('name', '=', 'ANTICIPOS DE CLIENTES')])
        if account:
            return account[0].id

    property_account_advance_id = fields.Many2one('account.account', 'Cuenta de anticipo',
                                                  default=lambda self: self._default_account_advance(),
                                                  domain=[('account_type', '=', 'movement')])

    property_account_receivable_id = fields.Many2one('account.account',
                                                     string='Cuenta a cobrar',
                                                     domain=[('account_type', '=', 'movement')])
