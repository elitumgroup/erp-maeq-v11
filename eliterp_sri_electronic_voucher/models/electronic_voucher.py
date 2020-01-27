# -*- coding: utf-8 -*-

import base64
from datetime import datetime, date, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from . import utils
from OpenSSL.crypto import load_pkcs12
import requests
import json
import logging

_logger = logging.getLogger(__name__)

STD_FORMAT = '%d%m%Y'

STATES_CERTIFICATE = [
    ('draft', 'Borrador'),
    ('validate', 'Validado'),
    ('expired', 'Expirado')
]

HEAD_JSON = {
    '18': 'factura',
    '04': 'notaCredito',
    '07': 'comprobanteRetencion'
}

BODY_JSON = {
    '18': 'infoFactura',
    '04': 'infoNotaCredito',
    '07': 'infoCompRetencion'
}

DETAIL_JSON = {
    '18': 'detalles',
    '04': 'detalles',
    '07': 'impuestos'
}

TIMEOUT = 40

FIELD = {
    'account.invoice': 'reference',
    'eliterp.withhold': 'reference'
}


class DigitalCertificate(models.Model):
    _name = 'sri.digital.certificate'
    _inherit = ['mail.thread']
    _description = _("Certificado digital")

    @api.multi
    def unlink(self):
        if any(self.filtered(lambda x: x.state == 'validate')):
            raise UserError(_("No se puede eliminar certificados validados!"))
        return super(DigitalCertificate, self).unlink()

    @api.multi
    def button_validate(self):
        """
        Validamos la clave sea correcta para
        certificado digital.
        :return:
        """
        self.ensure_one()
        fileContent = base64.b64decode(self.digital_signature)  # Leer contenido de campo Binary
        try:
            load_pkcs12(fileContent, self.digital_electronic_signature)
            self.write({'state': 'validate'})
        except Exception as e:
            raise UserError("Error: " + (str(e)))

    name = fields.Char('Nombre de certificado', required=True)
    digital_signature = fields.Binary('Certificado digital', readonly=True,
                                      states={'draft': [('readonly', False)]}, attachment=True, copy=False,
                                      required=True)
    digital_signature_name = fields.Char('Nombre de certificado digital', copy=False)
    expiration_date = fields.Date('Fecha de expiración', readonly=True,
                                  states={'draft': [('readonly', False)]}, required=True, track_visibility='onchange',
                                  help="Fecha qué vence el certificado digital, por lo general son dos años desde su adquisición.")
    digital_electronic_signature = fields.Char(
        'Clave para certificado digital',
        readonly=True,
        states={'draft': [('readonly', False)]},
        required=True
    )
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.user.company_id)
    state = fields.Selection(STATES_CERTIFICATE, string="Estado",
                             default='draft', track_visibility='onchange')


class ElectronicVoucher(models.Model):
    _name = 'sri.electronic.voucher'
    _inherit = ['mail.thread']
    _description = _("Comprobante electrónico")
    _order = 'create_date asc'

    name = fields.Char('Clave de acceso', size=49, readonly=True)
    state = fields.Selection(utils.STATES, string='Estado de autorización', default='new',
                             track_visibility='onchange',
                             readonly=True)
    authorization_date = fields.Datetime(
        'Fecha autorización',
        readonly=True,
        track_visibility='onchange'
    )
    type_service = fields.Selection(
        [
            ('webservice', 'API (Servicio web)'),
            ('own', 'Propio')
        ],
        string='Tipo de servicio',
        readonly=True,
        required=True,
        default='webservice'
    )
    type_emission = fields.Selection(
        [
            ('1', 'Normal')
        ],
        string='Tipo de emisión',
        required=True,
        readonly=True
    )
    environment = fields.Selection(
        [
            ('1', 'Pruebas'),
            ('2', 'Producción')
        ],
        string='Entorno',
        required=True,
        readonly=True
    )
    document_id = fields.Reference(string='Documento', readonly=True,
                                   selection=[('account.invoice', ''), ('eliterp.withhold', '')],
                                   help="Técnico: Referencia del modelo origen y su ID.", required=True)
    authorized_voucher_id = fields.Many2one('eliterp.type.document', 'Tipo de comprobante', readonly=True,
                                            required=True)
    sri_authorization_id = fields.Many2one('eliterp.sri.authorization', string='Autorización SRI', readonly=True,
                                           copy=False,
                                           states={'draft': [('readonly', False)]})
    document_date = fields.Date('Fecha documento', required=True)
    document_number = fields.Char('No. Documento', required=True)

    xml_signed_file = fields.Binary('XML firmado')
    xml_signed_filename = fields.Char('Nombre de XML firmado', copy=False)
    xml_file = fields.Binary('XML')
    xml_filename = fields.Char('Nombre de XML', copy=False)
    ride_file = fields.Binary('RIDE')
    ride_filename = fields.Char('Nombre de RIDE', copy=False)
    comment = fields.Text('Notas', readonly=True)
    is_sent = fields.Boolean('Enviado', help="Técnico: especifica si fue enviado el correo a cliente!")
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)

    @api.multi
    def _cron_generated(self):
        for ve in self.search([('state', '=', 'new')]):
            try:
                ve.button_generated_api()
                self.env.cr.commit()
            except Exception as e:
                _logger.exception("Envío de CE's al API falló.")
                self.env.cr.rollback()

    @api.multi
    def run_scheduler_email(self):
        """
        Tarea programada para envío de correo de CE del SRI cuando
        esten autoizado.
        :return:
        """
        documents = self.search([
            ('state', '=', 'authorized_sri'),
            ('is_sent', '=', False)
        ])
        for document in documents:
            document.send_document()
        return True

    def _get_template(self):
        template = False
        code = self.authorized_voucher_id.code
        if code in ['18', '04']:
            template = self.env.ref("eliterp_sri_electronic_voucher.mail_template_electronic_invoice")
        if code == '07':
            template = self.env.ref("eliterp_sri_electronic_voucher.mail_template_electronic_retention")
        return template

    @api.one
    def _get_attachments(self):
        """
        Generamos documento a enviar a cliente
        :return object:
        """
        attach_1 = self.env['ir.attachment'].sudo().create(
            {
                'name': str(self.ride_filename),
                'datas': self.ride_file,
                'datas_fname': self.ride_filename,
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary'
            },
        )
        attach_2 = self.env['ir.attachment'].sudo().create(
            {
                'name': str(self.xml_filename),
                'datas': self.xml_file,
                'datas_fname': self.xml_filename,
                'res_model': self._name,
                'res_id': self.id,
                'type': 'binary'
            },
        )
        attachs = attach_1 | attach_2
        return attachs

    @api.multi
    def send_document(self):
        """
        Enviamos documento por correo electrónico al cliente
        :return:
        """
        self.ensure_one()
        mail_template = self._get_template()
        attachments = self._get_attachments()[0]
        mail_template.send_mail(
            self.document_id.id,
            email_values={'attachment_ids': [a.id for a in attachments]}
        )
        self.write({'is_sent': True})
        return True

    @api.multi
    def button_cancel(self):
        self.write({'state': 'cancel'})

    @api.multi
    def unlink(self):
        if any(self.filtered(lambda x: x.environment == '2')):
            raise UserError(_("No se puede eliminar comprobantes electrónicos del sistema!"))
        return super(ElectronicVoucher, self).unlink()

    @api.one
    def _get_digital_certificate(self):
        """
        Obtenemos certificado de la compañía.
        :return:
        """
        ObjectDC = self.env['sri.digital.certificate']
        digital_certificate = ObjectDC.search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'validate')
        ], limit=1)
        return digital_certificate or False

    def _get_vals_information_company(self):
        """
        Información sobre la compañía
        :return:
        """
        company = self.company_id
        code = utils.table3[self.authorized_voucher_id.code]
        vals = {
            'ambiente': self.environment,
            'tipoEmision': self.type_emission,
            'razonSocial': company.name,
            'nombreComercial': company.name,
            'ruc': company.vat,
            'claveAcceso': "0",  # API con 0
            'codDoc': code,
            'estab': self.document_number[:3],
            'ptoEmi': self.document_number[4:7],
            'secuencial': self.document_number[8:],
            'dirMatriz': company.street
        }
        return vals

    def _get_new_authorization(self, name):
        """
        Obtenemos los valores para la creacion de autorizacion electronica.
        :param name:
        :return:
        """
        vals = {}
        object_authorization = self.env['eliterp.sri.authorization']
        authorized_voucher = self.authorized_voucher_id.id
        vals['initial_number'] = int(self.document_number[8:])
        vals['final_number'] = int(self.document_number[8:])
        vals['authorization'] = name
        vals['type_document'] = authorized_voucher
        vals['expiration_date'] = date.today()
        vals['is_electronic'] = True
        vals['point_printing_id'] = self.document_id.point_printing_id.id
        vals['company_id'] = self.company_id.id
        return object_authorization.create(vals)

    @api.multi
    def _update_document(self, data):
        self.ensure_one()
        authorization = data['autorizaciones'][0]
        name = authorization['numeroAutorizacion']
        xml = authorization['comprobante']
        ride = data['ride']
        new_authorization = self._get_new_authorization(name)
        date_authorization = datetime.strptime(authorization['fechaAutorizacion'], DEFAULT_SERVER_DATETIME_FORMAT) + \
                                timedelta(hours=5)
        self.document_id.update({'sri_authorization_id': new_authorization.id})
        return {
            'name': data['claveAccesoConsultada'],
            'sri_authorization_id': new_authorization.id,
            'environment': '1' if authorization['ambiente'] == 'PRUEBAS' else '2',
            'authorization_date': date_authorization,
            'state': 'authorized_sri',
            'comment': False,
            'xml_filename': name + '.xml',
            'xml_file': base64.b64encode(bytes(xml, 'utf-8')),
            'ride_filename': name + '.pdf',
            'ride_file': ride
        }

    # Operaciones

    def _get_data_json(self, code):
        """
        Datos de cada documento del sistema
        :param code:
        :return:
        """
        # Datos administrativos de cada documento.
        data_document = False
        data_detail = False
        # account.invoice, eliterp.withhold
        document = self.document_id
        type_document = HEAD_JSON[code]
        if code == '18':
            data_document = document._get_vals_information()
        elif code == '04':
            data_document = document._get_vals_information_refund()
        elif code == '07':
            data_document = document._get_vals_information()
            data_detail = document._get_vals_taxes()
        if code in ['18', '04']:
            data_detail = document._get_vals_details()
        return {
            type_document: {
                "infoTributaria": self._get_vals_information_company(),
                BODY_JSON[code]: data_document,
                DETAIL_JSON[code]: data_detail
            }
        }

    def _get_json(self, certificate):
        self.ensure_one()
        data_json = {}
        logo = self.company_id.logo
        code = self.authorized_voucher_id.code
        data = self._get_data_json(code)
        partner = self.document_id.partner_id  # partner_id siempre en todos
        # los documentos de facturación electrónica.
        data_json.update(data)
        data_json.update({
            'info': {
                'logo': logo.decode('utf-8'),
                'email': partner.email or 'N.A',
                'celular': partner.mobile if partner.mobile else 'N.A',
                'detail': 'N.A',
                'obligado': "SI",
                'especialn': "-",
                'p12': certificate.digital_signature.decode('utf-8'),
                'clavep12': certificate.digital_electronic_signature
            }
        })
        _logger.critical(data_json)  # Test
        return data_json

    @api.multi
    def button_generated(self):
        self.filtered(lambda x: x.type_service == 'webservice').button_generated_api()
        return True

    @staticmethod
    def _get_messages_receiver_sri(response):
        errors = []
        for c in response['comprobantes']:
            for m in c['mensaje']:
                one_message = '[{0}] - {1} ({2})'.format(m['identificador'],
                                                         m['mensaje'],
                                                         m['tipo'])
                if 'informacionAdicional' in m:
                    one_message += ', %s' % m['informacionAdicional']
                if m['identificador'] == '43':
                    one_message += ' => ' + c['claveAcceso']
                errors.append(one_message)
        return errors

    @staticmethod
    def _get_messages_sri(messages):
        new_message = []
        if not messages:
            return new_message
        for m in messages[0]['mensajes']:
            one_message = '[{0}] - {1} ({2})'.format(m['identificador'],
                                                     m['mensaje'],
                                                     m['informacionAdicional'])
            new_message.append(one_message)
        return new_message

    def _get_response(self, message):
        values = {}
        if not message['receptor']['isRecibida'] and not message['autenticador']['isAutorizado']:
            values['comment'] = ', '.join(self._get_messages_receiver_sri(message['receptor']))
        elif message['autenticador']['isAutorizado']:
            values = self._update_document(message['autenticador'])
        else:
            messages = message['autenticador']['autorizaciones']
            values['state'] = 'not_authorized_sri'
            values['comment'] = ', '.join(self._get_messages_sri(messages))
        return values

    def _get_url_api(self):
        """
        Obtenemos la URL del API configurada.
        :return:
        """
        return self.env['ir.config_parameter'].sudo().get_param(
            'electronic_voucher.api',
            default='http://70.32.30.240/api/apiofflinesri'
        )

    @api.multi
    def button_generated_api(self):
        """
        Proceso con webservice (API), no se necesita
        firmado, proveedor realiza proceso.
        :return:
        """
        url = self._get_url_api()
        documents = self.filtered(lambda d: d.state in ['new', 'not_authorized_sri'])
        for document in documents:
            certificate = document._get_digital_certificate()
            if not certificate[0]:
                document.write({
                    'comment': utils.MESSAGE_CERTIFICATE
                })
                break
            try:
                response = requests.post(
                    url,
                    data=json.dumps(document._get_json(certificate[0])),
                    headers={'Content-Type': 'application/json'}
                )
                if response.status_code == 404:
                    document.write({'comment': _(utils.MESSAGE_404)})
                    continue
                if response.status_code == 500:
                    document.write({'comment': _(utils.MESSAGE_500)})
                    continue
                if response.status_code == 200:
                    message = json.loads(response.text)['respuestas']
                    document.write(self._get_response(message))
            except Exception as e:
                document.write({'comment': str(e)})
                continue
        return True
