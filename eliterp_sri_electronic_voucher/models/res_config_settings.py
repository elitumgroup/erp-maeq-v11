# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    url_api = fields.Char('URL del API', default='http://70.32.30.240/api/apiofflinesri',
                          help="Url para autorizacion de CE al SRI.", config_parameter='electronic_voucher.api')

    @api.multi
    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        param = self.env['ir.config_parameter'].sudo()
        param.set_param('electronic_voucher.api', self.url_api)
        return res
