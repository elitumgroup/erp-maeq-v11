# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from itertools import groupby
from operator import itemgetter


class GangReportPdf(models.AbstractModel):
    _name = 'report.eliterp_operations.eliterp_report_gang_report'

    def _get_total_hectares(self, doc, g):
        gang = self.env['eliterp.gang'].search([('name', '=', g)])
        hectares = self.env['eliterp.production.hectares'].search([
            ('start_date', '>=', doc.start_date),
            ('start_date', '<=', doc.end_date),
            ('gang_id', '=', gang.id),
            ('ubication_id', '=', doc.ubication_id.id)
        ])
        total = 0.00
        for x in hectares:
            total += x.hectares
        return total

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        data = []
        arg = []
        arg.append(('date', '>=', doc.start_date))
        arg.append(('date', '<=', doc.end_date))
        arg.append(('state', '=', 'validate'))
        if doc.gang_ids:
            arg.append(('gang_id', 'in', doc.gang_ids.ids))
        if doc.ubication_id:
            arg.append(('ubication_id', '=', doc.ubication_id.id))
        cmc_ids = self.env['eliterp.cmc'].search(arg)
        cmcs = []
        for cmc in cmc_ids:
            if doc.struct_id:
                if cmc.operator.struct_id.id == doc.struct_id.id:
                    cmcs.append({
                        'gang': cmc.gang_id.name,
                        'name': cmc.operator.name,
                        'worked_hours': cmc.worked_hours,
                        'ubication_id': cmc.ubication_id.name
                    })
                if cmc.assistant:
                    if cmc.assistant.struct_id.id == doc.struct_id.id:
                        cmcs.append({
                            'gang': cmc.gang_id.name,
                            'name': cmc.assistant.name,
                            'worked_hours': cmc.worked_hours,
                            'ubication_id': cmc.ubication_id.name
                        })
            else:
                cmcs.append({
                    'gang': cmc.gang_id.name,
                    'name': cmc.operator.name,
                    'worked_hours': cmc.worked_hours,
                    'ubication_id': cmc.ubication_id.name
                })
                if cmc.assistant:
                    cmcs.append({
                        'gang': cmc.gang_id.name,
                        'name': cmc.assistant.name,
                        'worked_hours': cmc.worked_hours,
                        'ubication_id': cmc.ubication_id.name
                    })
        cmcs = sorted(cmcs, key=lambda a: a['gang'])
        for gang, records in groupby(cmcs, lambda l: l['gang']):
            total_hectares = self._get_total_hectares(doc, gang)
            new_records = sorted(records, key=lambda a: a['name'])
            summary = []
            for employee, new_cmcs in groupby(new_records, key=lambda x: x['name']):
                list_cmcs = list(new_cmcs)
                summary.append({
                    'name': employee,
                    'worked_hours': sum((x['worked_hours'] for x in list_cmcs)),
                    'count': len(list_cmcs)
                })
            average_summary = 0.00
            average_summary = round(sum(x['count'] for x in summary) / int(len(summary)), 3)
            average = 0.00
            if doc.type_report == 'production':
                average = round((total_hectares / int(len(summary))) / average_summary, 3)
            for x in summary:
                hectares = 0.00
                hectares = x['count'] * average
                x['hectares'] = hectares
                x['money'] = round(hectares * 120, 3)
            data.append({
                'gang': gang,
                'hectares': total_hectares,
                'average': average,
                'rows': summary
            })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.gang.report',
            'docs': self.env['eliterp.gang.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class GangReport(models.TransientModel):
    _name = 'eliterp.gang.report'

    _description = "Ventana para reporte de cuadrillas"

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_operations.eliterp_action_report_gang_report').report_action(self)

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte en EXCEL
        """
        self.ensure_one()
        return self.env.ref('eliterp_operations.eliterp_action_gang_report_xlsx').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', required=True, default=fields.Date.context_today)
    struct_id = fields.Many2one('hr.payroll.structure', string='Estructura salarial')
    ubication_id = fields.Many2one("eliterp.location", string='Ubicación')
    gang_ids = fields.Many2many("eliterp.gang", string='Cuadrillas')
    type_report = fields.Selection([
        ('production', 'Producción'),
        ('hours', 'Horas')
    ], default='production', string='Tipo de reporte', required=True)


class GangReportExcel(models.AbstractModel):
    _name = 'report.eliterp_operations.eliterp_action_gang_report_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, context):
        data = self.env['report.eliterp_operations.eliterp_report_gang_report']._get_lines(context)
        sheet = workbook.add_worksheet('REPORTE DE CUADRILLAS')
        # Formatos
        _right_format = workbook.add_format({'align': 'right', 'num_format': '#,##0.00'})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})

        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center'
        })
        title2 = workbook.add_format({
            'bold': True,
            'color': 'red'
        })
        # Columnas
        sheet.set_column("A:A", 40)
        sheet.set_column("B:B", 15)
        sheet.set_column("C:C", 8)
        sheet.set_column("D:D", 8)
        sheet.set_column("E:E", 15)
        # Filas
        sheet.set_default_row(15)
        # Datos
        sheet.merge_range('A1:D2', 'REPORTE DE CUADRILLAS', title)
        row = 2
        if context.type_report == "hours":
            for r in data:
                sheet.write(row, 0, "Cuadrilla", title2)
                sheet.write(row, 1, r['gang'])
                row += 1
                sheet.write(row, 0, "NOMBRE DE EMPLEADO")
                sheet.write(row, 1, "HORAS TRABAJADAS")
                for v in r['rows']:
                    row += 1
                    sheet.write(row, 0, v['name'])
                    sheet.write(row, 1, v['worked_hours'])
                    row += 1
        else:
            for r in data:
                sheet.write(row, 0, "Cuadrilla", title2)
                sheet.write(row, 1, r['gang'])
                row += 1
                sheet.write(row, 0, "NOMBRE DE EMPLEADO")
                sheet.write(row, 1, "DÍAS")
                sheet.write(row, 2, "HA * OPERADOR / DÍAS")
                sheet.write(row, 3, "VALOR HA TRABAJADAS * OPERADOR")
                for v in r['rows']:
                    row += 1
                    sheet.write(row, 0, v['name'])
                    sheet.write(row, 1, v['count'])
                    sheet.write(row, 2, v['hectares'])
                    sheet.write(row, 3, v['money'])
                    row += 1


class OperationsCmcReportPdf(models.AbstractModel):
    _name = 'report.eliterp_operations.eliterp_report_operations_cmc_report'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        where = """
        where a.date between '%s' AND '%s'
        and e.product_id = 96 
        """ % (doc.start_date, doc.end_date)
        if doc.project_id:
            where += "and a.project_id = %d" % doc.project_id.id
        if doc.gang_ids:
            gangs = ', '.join(map(str, doc.gang_ids._ids))
            where += "and a.gang_id in (%s)" % gangs
        sql = """
        select  
        b.name, c.name, d.name, sum(a.worked_hours), sum(a.lost_hours), sum(a.stop_time_1)
        , sum(a.stop_time_2), sum(a.stop_time_3), sum(a.stop_time_4), sum(a.stop_time_5), sum(e.product_quantity)
        from
        eliterp_supplies_cmc as e
        left join eliterp_cmc as a on a.id = e.cmc_id
        left join eliterp_gang as b on b.id = a.gang_id
        left join hr_employee as c on c.id = a.operator
        left join eliterp_machine as d on d.id = a.machine_id
        """
        sql += where
        sql += """
        group by 
        b.name, c.name, d.name
        order 
        by b.name, c.name;  
        """
        self.env.cr.execute(sql)
        query = self.env.cr.fetchall()
        data = []
        for gang, records in groupby(query, lambda x: x[0]):
            rows = []
            for r in records:
                rows.append({
                    'operator': r[1],
                    'machine': r[2],
                    'worked_hours': r[3],
                    'lost_hours': r[4],
                    'stop_1': r[5],
                    'stop_2': r[6],
                    'stop_3': r[7],
                    'stop_4': r[8],
                    'stop_5': r[9],
                    'diesel': r[10],
                })
            data.append({
                'gang': gang,
                'rows': rows
            })
        return data

    @api.model
    def get_report_values(self, docids, data=None):
        return {
            'doc_ids': docids,
            'doc_model': 'eliterp.operations.cmc.report',
            'docs': self.env['eliterp.operations.cmc.report'].browse(docids),
            'get_lines': self._get_lines,
            'data': data,
        }


class OperationsCmcXlsx(models.AbstractModel):
    _name = 'report.eliterp_operations.eliterp_operations_cmc_xlsx'

    _inherit = 'report.report_xlsx.abstract'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        where = """
                where a.date between '%s' AND '%s'
                and e.product_id = 96 
                """ % (doc.start_date, doc.end_date)
        if doc.project_id:
            where += "and a.project_id = %d" % doc.project_id.id
        if doc.gang_ids:
            gangs = ', '.join(map(str, doc.gang_ids._ids))
            where += "and a.gang_id in (%s)" % gangs
        sql = """
                select  
                b.name, c.name, d.name, sum(a.worked_hours), sum(a.lost_hours), sum(a.stop_time_1)
                , sum(a.stop_time_2), sum(a.stop_time_3), sum(a.stop_time_4), sum(a.stop_time_5), sum(e.product_quantity)
                from
                eliterp_supplies_cmc as e
                left join eliterp_cmc as a on a.id = e.cmc_id
                left join eliterp_gang as b on b.id = a.gang_id
                left join hr_employee as c on c.id = a.operator
                left join eliterp_machine as d on d.id = a.machine_id
                """
        sql += where
        sql += """
                group by 
                b.name, c.name, d.name
                order 
                by b.name, c.name;  
                """
        self.env.cr.execute(sql)
        query = self.env.cr.fetchall()
        return query

    def generate_xlsx_report(self, workbook, data, context):
        data = self._get_lines(context)
        sheet = workbook.add_worksheet('Operaciones')
        # Formatos
        bold = workbook.add_format({'align': 'center', 'bold': 1})
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        # Formatos de celda
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        # Cabeceras con filtro
        sheet.autofilter('A3:R3')
        sheet.write('A1', 'REPORTE DE OPERACIONES', title)
        sheet.write(2, 0, "CUADRILLA", bold)
        sheet.write(2, 1, "OPERADOR", bold)
        sheet.write(2, 2, "MÁQUINA", bold)

        sheet.merge_range(2, 3, 2, 5, "H. TRABAJADAS", bold)
        sheet.merge_range(2, 6, 2, 8, "H. NO TRABAJADAS", bold)
        sheet.merge_range(2, 9, 2, 10, "P. MAEQ", bold)
        sheet.merge_range(2, 11, 2, 12, "H. P. MECÁNICO", bold)
        sheet.merge_range(2, 13, 2, 14, "P. OPERADOR", bold)
        sheet.merge_range(2, 15, 2, 16, "P. CLIENTE", bold)
        sheet.write(2, 17, "P. NO/ID", bold)
        sheet.merge_range(2, 18, 2, 19, "DIESE (GL)", bold)

        row = 3
        col = 0
        for c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11 in (data):
            sheet.write(row, col, c1)
            sheet.write(row, col + 1, c2)
            sheet.write(row, col + 2, c3)
            sheet.merge_range(row, 3, row, 5, c4, number_format)
            sheet.merge_range(row, 6, row, 8, c5, number_format)
            sheet.merge_range(row, 9, row, 10, c6, number_format)
            sheet.merge_range(row, 11, row, 12, c7, number_format)
            sheet.merge_range(row, 13, row, 14, c8, number_format)
            sheet.merge_range(row, 15, row, 16, c9, number_format)
            sheet.write(row, 17, c10, number_format)
            sheet.merge_range(row, 18, row, 19, c11, number_format)
            row += 1


class OperationsCmcReportXlsx(models.AbstractModel):
    _name = 'report.eliterp_operations.eliterp_operations_cmc_report_xlsx'

    _inherit = 'report.report_xlsx.abstract'

    def _get_lines(self, doc):
        """
        Obtenemos líneas de reporte
        :param doc:
        :return: list
        """
        where = """
                where a.date between '%s' AND '%s'
                and e.product_id = 96 
                """ % (doc.start_date, doc.start_date)  # Misma fecha para el reporte diario
        if doc.project_id:
            where += "and a.project_id = %d" % doc.project_id.id
        if doc.gang_ids:
            gangs = ', '.join(map(str, doc.gang_ids._ids))
            where += "and a.gang_id in (%s)" % gangs
        sql = """
                select  
                b.name, c.name, f.name, d.name, sum(a.men_hours), sum(a.worked_hours), sum(a.stop_time_1)
                , sum(a.stop_time_2), sum(a.stop_time_3), sum(a.stop_time_4), sum(a.stop_time_5), sum(e.product_quantity), a.grease
                from
                eliterp_supplies_cmc as e
                left join eliterp_cmc as a on a.id = e.cmc_id
                left join eliterp_gang as b on b.id = a.gang_id
                left join hr_employee as c on c.id = a.operator
                left join hr_employee as f on f.id = a.assistant
                left join eliterp_machine as d on d.id = a.machine_id
                """
        sql += where
        sql += """
                group by 
                b.name, c.name, f.name, d.name, a.grease
                order 
                by b.name, c.name;  
                """
        self.env.cr.execute(sql)
        query = self.env.cr.fetchall()
        return query

    def generate_xlsx_report(self, workbook, data, context):
        data = self._get_lines(context)
        sheet = workbook.add_worksheet('IO-Diario')
        sheet.hide_gridlines(1)  # Ocultar rejillas
        # Formatos
        line = workbook.add_format({'bg_color': '#F78F1E'})
        bold = workbook.add_format({'bold': 1})
        content = workbook.add_format({
            'size': 8,
            'text_wrap': True
        })
        title = workbook.add_format({
            'bold': True,
            'border': 1,
            'size': 10,
            'text_wrap': True,
            'align': 'center',
            'valign': 'vcenter'
        })
        # Línea
        for c in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N']:
            sheet.write('%s2' % c, '', line)
        # Columnas
        sheet.set_column("A:A", 2)
        sheet.set_column("B:B", 7.57)
        sheet.set_column("C:C", 7.29)
        sheet.set_column("D:D", 27.29)
        sheet.set_column("E:E", 27.29)
        sheet.set_column("F:F", 6.57)
        sheet.set_column("G:G", 4.57)
        sheet.set_column("H:H", 4.71)
        sheet.set_column("I:I", 5.57)
        sheet.set_column("J:J", 5.71)
        sheet.set_column("K:K", 6)
        sheet.set_column("L:L", 5)
        sheet.set_column("M:M", 5.86)
        sheet.set_column("N:N", 5.57)
        # Formatos de celda
        _right_format = workbook.add_format({'num_format': '$#,##0.00'})
        content1 = workbook.add_format({
            'size': 8,
            'text_wrap': True,
            'align': 'center'
        })
        number_format = workbook.add_format({'num_format': '#,##0.00', 'align': 'center', 'size': 8})
        sheet.set_default_row(15)
        # Cabeceras con filtro
        sheet.autofilter('B7:D7')
        sheet.write('A1', 'INFORME DIARIO DE OPERACIONES', bold)
        sheet.set_row(1, 2)  # Pintar línea
        sheet.write('A4', 'PROYECTO', bold)
        sheet.write('C4', context['project_id'].name)
        sheet.write('A5', 'FECHA', bold)
        sheet.write('C5', context['start_date'])
        sheet.write('E5', 'CUADRILLAS', bold)
        sheet.write('F5', ', '.join(i.name for i in context.gang_ids))

        sheet.set_row(6, 22.5)
        sheet.write(6, 0, "#", title)
        sheet.write(6, 1, "Cuadrilla", title)
        sheet.write(6, 2, "Máquina", title)
        sheet.write(6, 3, "Operador", title)
        sheet.write(6, 4, "Ayudante", title)
        sheet.write(6, 5, "Horas Hombre", title)
        sheet.write(6, 6, "Horas Maq.", title)
        sheet.write(6, 7, "Paro Maeq", title)
        sheet.write(6, 8, "Paro Mecan.", title)
        sheet.write(6, 9, "Paro Oper.", title)
        sheet.write(6, 10, "Paro Cliente", title)
        sheet.write(6, 11, "Paro N/I", title)
        sheet.write(6, 12, "Comb. (Gl)", title)
        sheet.write(6, 13, "Grasa", title)
        row = 7
        con1 = 1
        for c1, c3, c2, c4, c5, c6, c7, c8, c9, c10, c11, c12, c13 in (data):
            sheet.write(row, 0, con1, content1)
            sheet.write(row, 1, c1, content1)
            sheet.write(row, 2, c4, content1)
            sheet.write(row, 3, c3, content)
            sheet.write(row, 4, c2 if c2 else '-', content)
            sheet.write(row, 5, c5, number_format)
            sheet.write(row, 6, c6, number_format)
            sheet.write(row, 7, c7, number_format)
            sheet.write(row, 8, c10, number_format)
            sheet.write(row, 9, c9, number_format)
            sheet.write(row, 10, c8, number_format)
            sheet.write(row, 11, c11, number_format)
            sheet.write(row, 12, c12, number_format)
            sheet.write(row, 13, 'Si' if c13 == 1 else 'No', content)
            row += 1
            con1 += 1
        row_chart = row
        # Sumar en horas
        _total = workbook.add_format({
            'bold': 1,
            'align': 'right'
        })
        _sums = workbook.add_format({
            'bold': 1,
            'border': 1
        })
        sum_columns = (
            ['F', 5], ['G', 6], ['H', 7], ['I', 8],
            ['J', 9], ['K', 10], ['L', 11], ['M', 12]
        )
        sheet.write(row, 3, "TOTAL", _total)
        for l, c in sum_columns:
            sum_ = '=SUM(%s7:%s%s)' % (l, l, str(row))  # Sumar columnas
            sheet.write(row, c, sum_, _sums)
        row += 2
        # Gráfica 1
        chart_1 = workbook.add_chart({'type': 'column', 'subtype': 'stacked'})
        chart_1.add_series({
            'name': "='IO-Diario'!$G$7",
            'categories': "='IO-Diario'!$C$8:$C$%d" % row_chart,
            'values': "='IO-Diario'!$G$8:$G$%d" % row_chart,
        })
        chart_1.add_series({
            'name': "='IO-Diario'!$H$7",
            'categories': "='IO-Diario'!$C$8:$C$%d" % row_chart,
            'values': "='IO-Diario'!$H$8:$H$%d" % row_chart,
        })
        chart_1.add_series({
            'name': "='IO-Diario'!$I$7",
            'categories': "='IO-Diario'!$C$8:$C$%d" % row_chart,
            'values': "='IO-Diario'!$I$8:$I$%d" % row_chart,
        })
        chart_1.add_series({
            'name': "='IO-Diario'!$J$7",
            'categories': "='IO-Diario'!$C$8:$C$%d" % row_chart,
            'values': "='IO-Diario'!$J$8:$J$%d" % row_chart,
        })
        chart_1.add_series({
            'name': "='IO-Diario'!$K$7",
            'categories': "='IO-Diario'!$C$8:$C$%d" % row_chart,
            'values': "='IO-Diario'!$K$8:$K$%d" % row_chart,
        })
        chart_1.set_title({'name': 'Horas Máquinas'})
        chart_1.set_x_axis({'name': 'Máquinas'})
        chart_1.set_y_axis({'name': 'Horas'})
        chart_1.set_style(10)
        sheet.insert_chart('A%d' % row, chart_1, {'x_offset': 5, 'y_offset': 5, 'x_scale': 0.84, 'y_scale': 1.42})
        # Gráfica 2
        chart_2 = workbook.add_chart({'type': 'bar'})
        chart_2.add_series({
            'name': "='IO-Diario'!$G$7",
            'categories': "='IO-Diario'!$C$8:$C$%d" % row_chart,
            'values': "='IO-Diario'!$G$8:$G$%d" % row_chart,
        })
        chart_2.add_series({
            'name': "='IO-Diario'!$M$7",
            'categories': "='IO-Diario'!$C$8:$C$%d" % row_chart,
            'values': "='IO-Diario'!$M$8:$M$%d" % row_chart,
        })
        chart_2.set_title({'name': 'Análisis Combustible'})
        chart_2.set_style(8)
        sheet.insert_chart('E%d' % row, chart_2, {'x_offset': 80, 'y_offset': 5, 'x_scale': 1.05, 'y_scale': 0.81})
        # Gráfica 3
        chart_3 = workbook.add_chart({'type': 'line'})
        chart_3.add_series({
            'name': "='IO-Diario'!$F$7",
            'categories': "='IO-Diario'!$D$8:$D$%d" % row_chart,
            'values': "='IO-Diario'!$F$8:$F$%d" % row_chart,
        })
        chart_3.add_series({
            'name': "='IO-Diario'!$G$7",
            'categories': "='IO-Diario'!$D$8:$D$%d" % row_chart,
            'values': "='IO-Diario'!$G$8:$G$%d" % row_chart,
        })
        chart_3.set_style(10)
        sheet.insert_chart('E%d' % (row + 12), chart_3,
                           {'x_offset': 80, 'y_offset': 0, 'x_scale': 1.05, 'y_scale': 0.61})
        o_row = row + 20
        sheet.write(o_row, 0, "Observaciones:", bold)
        merge_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })
        text = context.comments or "-"
        sheet.merge_range('A%d:N%d' % (o_row + 2, o_row + 5), text, merge_format)


class OperationsCmcReport(models.TransientModel):
    _name = 'eliterp.operations.cmc.report'

    _description = "Ventana para reporte de operaciones"

    @api.multi
    def print_report_xlsx(self):
        """
        Imprimimos reporte xlsx
        """
        self.ensure_one()
        return self.env.ref('eliterp_operations.eliterp_action_report_operations_cmc_xlsx').report_action(self)

    @api.multi
    def print_information(self):
        """
        Imprimimos informe diario
        """
        self.ensure_one()
        return self.env.ref('eliterp_operations.eliterp_action_report_operations_cmc_report_xlsx').report_action(self)

    @api.multi
    def print_report_pdf(self):
        """
        Imprimimos reporte en pdf
        """
        self.ensure_one()
        return self.env.ref('eliterp_operations.eliterp_action_report_operations_cmc_report').report_action(self)

    start_date = fields.Date('Fecha inicio', required=True)
    end_date = fields.Date('Fecha fin', default=fields.Date.context_today)
    project_id = fields.Many2one("eliterp.project", string='Proyecto', required=True)
    gang_ids = fields.Many2many("eliterp.gang", string='Cuadrillas')
    comments = fields.Text('Observaciones')
