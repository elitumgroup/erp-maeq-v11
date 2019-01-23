# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import models
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


class ProductReportXlsx(models.AbstractModel):
    _name = 'report.eliterp_inventory.eliterp_report_product_report_xlsx'

    _inherit = 'report.report_xlsx.abstract'

    @staticmethod
    def _get_type(type):
        """
        Tipo de producto
        :return: string
        """
        data = ''
        if type == 'consu':
            data = 'CONSUMIBLE'
        elif type == 'service':
            data = 'SERVICIO'
        else:
            data = 'ALMACENABLE'
        return data

    def _get_lines(self, doc):
        data = []
        arg = []
        if doc.type == 'purchase':
            arg.append(('purchase_ok', '=', True))
        if doc.type == 'sale':
            arg.append(('sale_ok', '=', True))
        if doc.category != 'all':
            arg.append(('categ_id', '=', doc.category_id.id))
        products = self.env['product.template'].search(arg)
        for product in products.sorted(key=lambda r: r.categ_id.name):
            row = []
            row.append(product.create_uid)
            row.append(self._get_type(product.type))
            row.append(product.categ_id.name)
            row.append(product.name)
            row.append(product.default_code)
            row.append(product.categ_id.property_account_income_categ_id.code + " " + product.categ_id.property_account_income_categ_id.name if product.categ_id.property_account_income_categ_id else '-')
            row.append(product.categ_id.property_account_expense_categ_id.code + " " + product.categ_id.property_account_expense_categ_id.name if product.categ_id.property_account_expense_categ_id else '-')
            row.append(product.uom_id.name)
            row.append(product.uom_po_id.name)
            row.append(product.list_price if product.list_price > 0 else '-')
            row.append(product.standard_price if product.standard_price > 0 else '-')
            data.append(row)
        return tuple(data)

    def generate_xlsx_report(self, workbook, data, context):
        data = self._get_lines(context)
        sheet = workbook.add_worksheet('Productos')
        # Formatos
        bold = workbook.add_format({'bold': 1})
        title = workbook.add_format({
            'bold': True,
            'border': 1
        })
        # Formatos de celda
        money_format = workbook.add_format({'num_format': '#,##0.00'})
        # Cabeceras con filtro
        sheet.autofilter('A3:H3')
        sheet.write('A1', 'REPORTE DE PRODUCTOS', title)
        sheet.write(2, 0, "CREADO POR", bold)
        sheet.write(2, 1, "TIPO DE PRODUCTO", bold)
        sheet.write(2, 2, "CATEGORÍA", bold)
        sheet.write(2, 3, "NOMBRE", bold)
        sheet.write(2, 4, "CÓDIGO PRODUCTO", bold)
        sheet.write(2, 5, "C. INGRESO", bold)
        sheet.write(2, 6, "C. GASTO", bold)
        sheet.write(2, 7, "U. MEDIDA", bold)
        sheet.write(2, 8, "U. MEDIDA/COMPRA", bold)
        sheet.write(2, 9, "PRECIO VENTA", bold)
        sheet.write(2, 10, "PRECIO COMPRA", bold)
        row = 3
        col = 0
        for c1, c2, c3, c4, c5, c6, c7, c8, c9, c10, c11 in (data):
            sheet.write(row, col, c1)
            sheet.write(row, col + 1, c2)
            sheet.write(row, col + 2, c3)
            sheet.write(row, col + 3, c4)
            sheet.write(row, col + 4, c5)
            sheet.write(row, col + 5, c6)
            sheet.write(row, col + 6, c7)
            sheet.write(row, col + 7, c8)
            sheet.write(row, col + 8, c9)
            sheet.write(row, col + 9, c10, money_format)
            sheet.write(row, col + 10, c11, money_format)
            row += 1

