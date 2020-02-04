# -*- coding: utf-8 -*-

from odoo import api, models, fields
from . import utils
from datetime import datetime


class Retention(models.Model):
    _inherit = 'eliterp.withhold'

    @api.model
    def create(self, values):
        res = super(Retention, self).create(values)
        if res.type == 'purchase' and res.is_electronic and not res.withhold_number:
            res.withhold_number = res.point_printing_id.name + '-' + res.reference
        return res

    @api.multi
    def confirm_purchase(self):
        res = super(Retention, self).confirm_purchase()
        for retention in self.filtered(lambda x: x.is_electronic):
            retention.action_electronic_voucher()
            retention.point_printing_id.next("retention")
        return res

    @staticmethod
    def fix_date(date_document):
        d = date_document.split('-')
        date = datetime(int(d[0]), int(d[1]), int(d[2]))
        return date.strftime('%d/%m/%Y')

    @staticmethod
    def fix_date_other(date_document):
        d = date_document.split('-')
        date = datetime(int(d[0]), int(d[1]), int(d[2]))
        return date.strftime('%m/%Y')

    def _get_electronic_voucher(self):
        """
        Creamos documento electrónico desde 'eliterp.withhold'
        con la clave de acceso generada.
        :return:
        """
        company = self.company_id
        ObjectVoucher = self.env['sri.electronic.voucher']
        authorized_voucher = self.env['eliterp.type.document'].search([('code', '=', '07')])[0]
        access_key = False
        if company.type_service == 'own':
            access_key = ObjectVoucher._get_access_key(
                company,
                [
                    self.point_printing_id,
                    self.date_withhold,
                    authorized_voucher.code,
                    self.reference
                ]
            )
        vals = {
            'name': access_key,
            'document_id': '{0},{1}'.format('eliterp.withhold', str(self.id)),
            'type_emission': company.type_emission,
            'environment': company.environment,
            'authorized_voucher_id': authorized_voucher.id,
            'document_date': self.date_withhold,
            'document_number': self.withhold_number,
            'company_id': company.id
        }
        new_object = ObjectVoucher.sudo().create(vals)
        return new_object

    def _get_vals_information(self):
        """
        Devolvemos la información necesaria
        para el documento XML.
        :return:
        """
        company = self.company_id
        partner = self.partner_id
        informationRetention = {
            'fechaEmision': self.fix_date(self.date_withhold),
            'dirEstablecimiento': company.street,
            'obligadoContabilidad': 'SI',
            'tipoIdentificacionSujetoRetenido': partner.type_documentation,
            'razonSocialSujetoRetenido': partner.name,
            'identificacionSujetoRetenido': partner.documentation_number,
            'periodoFiscal': self.fix_date_other(self.date_withhold)
        }
        return informationRetention

    @staticmethod
    def _get_code_purchase(code):
        if code == '04':
            code_purchase = '01'
        elif code == '05':
            code_purchase = '02'
        else:
            code_purchase = '06'
        return code_purchase

    def _get_vals_taxes(self):
        """
        Detalle de la retención(Líneas)
        :return dict:
        """
        taxes = []
        invoice = self.invoice_id
        for line in self.lines_withhold:
            tax = line.tax_id
            detail = {
                'codigo': utils.table19[line.retention_type],
                'codigoRetencion': tax.code if line.retention_type == 'rent' else utils.table20[tax.amount],
                'baseImponible': '{:.2f}'.format(line.base_taxable),
                'porcentajeRetener': int(tax.amount),
                'valorRetenido': '{:.2f}'.format(line.amount),
                'codDocSustento': invoice.authorized_voucher_id.code,
                'numDocSustento': invoice.invoice_number.replace('-', ''),
                'fechaEmisionDocSustento': self.fix_date(invoice.date_invoice)
            }
            taxes.append(detail)
        return {'impuesto': taxes}

    @api.multi
    def action_electronic_voucher(self):
        self.ensure_one()
        electronic_voucher = self._get_electronic_voucher()
        self.write({
            'electronic_voucher_id': electronic_voucher.id
        })

    electronic_voucher_id = fields.Many2one('sri.electronic.voucher', string='Comprobante electrónico', readonly=True,
                                            copy=False)
    authorization_date = fields.Datetime(
        'Fecha autorización',
        related='electronic_voucher_id.authorization_date', store=True
    )
    authorization_status = fields.Selection(utils.STATES, related='electronic_voucher_id.state', store=True)

    @api.one
    @api.depends('is_sequential', 'point_printing_id')
    def _compute_is_electronic(self):
        self.is_electronic = self.is_sequential and self.point_printing_id.allow_electronic_retention
