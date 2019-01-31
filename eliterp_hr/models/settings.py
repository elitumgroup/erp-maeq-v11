# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models, api


class ConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_wage = fields.Float(
        'Sueldo básico unficado',
        default_model='hr.employee',
        default=394
    )
    default_test_days = fields.Integer(
        'Días de período de prueba',
        default_model='hr.contract',
        default=90
    )
    default_advance_days = fields.Integer(
        'Días para ADQ',
        default_model='eliterp.advance.payment',
        default=10
    )



