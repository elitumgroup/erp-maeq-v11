# -*- coding: utf-8 -*-

from odoo import fields, models


class Partner(models.Model):
    _inherit = 'res.partner'

    email = fields.Char(required=True)


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
