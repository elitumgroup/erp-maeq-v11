# -*- coding: utf-8 -*-

from odoo import fields, models


class Users(models.Model):
    _inherit = 'res.users'

    def __init__(self, pool, cr):
        """Colocamos punto de impresiòn por defecto en preferencias."""
        init_res = super(Users, self).__init__(pool, cr)
        # duplicate list to avoid modifying the original reference
        type(self).SELF_WRITEABLE_FIELDS = list(self.SELF_WRITEABLE_FIELDS)
        type(self).SELF_WRITEABLE_FIELDS.extend(['my_point_printing'])
        # duplicate list to avoid modifying the original reference
        type(self).SELF_READABLE_FIELDS = list(self.SELF_READABLE_FIELDS)
        type(self).SELF_READABLE_FIELDS.extend(['my_point_printing'])
        return init_res

    my_point_printing = fields.Many2one('sri.point.printing', 'Punto de impresión')
    point_printing_ids = fields.Many2many('sri.point.printing', string='Puntos de impresión',
                                          help="Puntos de impresión habilitados para usuario!")
