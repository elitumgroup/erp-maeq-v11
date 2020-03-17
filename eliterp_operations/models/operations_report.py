# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
from odoo import api, fields, models, tools


class OperationsReport(models.Model):
    _name = "eliterp.operations.report"
    _description = "Informe de horas en CMC's"
    _auto = False
    _order = 'date desc'

    date = fields.Date('Fecha', readonly=True)
    project_id = fields.Many2one('eliterp.project', string='Proyecto', readonly=True)
    machine_id = fields.Many2one('eliterp.machine', string='Máquina', readonly=True)
    operator = fields.Many2one('hr.employee', string='Operador', readonly=True)
    worked_hours = fields.Float('Horas trabajadas', readonly=True, group_operator="sum")
    stop_time_1 = fields.Float('Paro MAEQ', readonly=True, group_operator="sum")
    stop_time_2 = fields.Float('Paro Cliente', readonly=True, group_operator="sum")
    stop_time_3 = fields.Float('Paro Operador', readonly=True, group_operator="sum")
    stop_time_4 = fields.Float('Paro Mecánico', readonly=True, group_operator="sum")
    stop_time_5 = fields.Float('Paro No/Id', readonly=True, group_operator="sum")
    stop_time_6 = fields.Float('Paro Ambiental', readonly=True, group_operator="sum")
    lost_hours = fields.Float('Horas no trabajadas', readonly=True, group_operator="sum")

    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'eliterp_operations_report')
        self.env.cr.execute("""
               CREATE OR REPLACE VIEW eliterp_operations_report AS (
                   SELECT
                       min(a.id) as id,
                       a.date as date,
                       b.id as project_id,
                       c.id as machine_id,
                       d.id as operator,
                       a.worked_hours as worked_hours,
                       a.stop_time_1 as stop_time_1,
                       a.stop_time_2 as stop_time_2,
                       a.stop_time_3 as stop_time_3,
                       a.stop_time_4 as stop_time_4,
                       a.stop_time_5 as stop_time_5,
                       a.stop_time_6 as stop_time_6,
                       a.lost_hours as lost_hours
                   FROM
                       eliterp_cmc as a
                       left join eliterp_project as b ON (b.id=a.project_id)
                       left join eliterp_machine as c ON (c.id=a.machine_id)
                       left join hr_employee as d ON (d.id=a.operator)
                   GROUP BY a.date, b.id, c.id, d.id, a.worked_hours, a.stop_time_1, a.stop_time_2, a.stop_time_3, 
                   a.stop_time_4, a.stop_time_5, a.stop_time_6, a.lost_hours
               )""")


class CmcSuppliesReport(models.Model):
    _name = "eliterp.cmc.supplies.report"
    _description = "Informe de insumos en CMC's"
    _auto = False
    _order = 'date desc'

    date = fields.Date('Fecha', readonly=True)
    project_id = fields.Many2one('eliterp.project', string='Proyecto', readonly=True)
    machine_id = fields.Many2one('eliterp.machine', string='Máquina', readonly=True)
    product_id = fields.Many2one('product.template', string='Insumo', readonly=True)
    worked_hours = fields.Float('Horas trabajadas', readonly=True, group_operator="sum")
    product_quantity = fields.Float('Cantidad', readonly=True, group_operator="sum")

    @api.model_cr
    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'eliterp_cmc_supplies_report')
        self.env.cr.execute("""
                CREATE OR REPLACE VIEW eliterp_cmc_supplies_report AS (
                    select 
                        min(a.id) as id,
	                    b.date as date,
                        c.id as project_id,
                        d.id as machine_id,
                        b.worked_hours as worked_hours,
                        p.id as product_id,
                        a.product_quantity as product_quantity
                    from 
                        eliterp_supplies_cmc as a
                        left join product_template as p ON (p.id=a.product_id)
                        left join eliterp_cmc as b on (b.id=a.cmc_id)
                        left join eliterp_project as c ON (c.id=b.project_id)
                        left join eliterp_machine as d ON (d.id=b.machine_id)
                    GROUP BY b.date, c.id, d.id, b.worked_hours, p.id, a.product_quantity
               )""")
