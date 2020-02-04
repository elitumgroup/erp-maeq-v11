# -*- coding: utf-8 -*-

import re
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

EMAIL_PATTERN = '([^ ,;<@]+@[^> ,;]+)'


class Partner(models.Model):
    _inherit = 'res.partner'

    @api.constrains('email')
    def _check_email(self):
        if not re.match(EMAIL_PATTERN, self.email):
            raise ValidationError(_("Email esta en un formato inválido!"))

    @api.constrains('email_optional')
    def _check_email_optional(self):
        if self.email_optional and not re.match(EMAIL_PATTERN, self.email_optional):
            raise ValidationError(_("Email opcional esta en un formato inválido!"))

    email = fields.Char(required=True)
    email_optional = fields.Char('Email opcional',
                                 help="Campo de email opcional para el envío del RIDE.")


class Company(models.Model):
    _inherit = 'res.company'

    type_service = fields.Selection(
        [
            ('webservice', 'API (Servicio web)'),
            ('own', 'Propio')
        ],
        string='Tipo de servicio',
        required=True,
        default='webservice'
    )
    # Off-line no necesita ('2', 'Indisponibilidad')
    type_emission = fields.Selection(
        [
            ('1', 'Normal')
        ],
        string='Tipo de emisión',
        required=True,
        default='1'
    )
    environment = fields.Selection(
        [
            ('1', 'Pruebas'),
            ('2', 'Producción')
        ],
        string='Entorno',
        required=True,
        default='1'
    )
    email_voucher_electronic = fields.Char('Correo para facturación electrónica',
                                           help="Técnico: si no se coloca correo toma el configurado en compañía.")

    @api.constrains('email_voucher_electronic')
    def _check_email_voucher_electronic(self):
        if not re.match(EMAIL_PATTERN, self.email_voucher_electronic):
            raise ValidationError(_("Email opcional esta en un formato inválido!"))
