# -*- coding: utf-8 -*-

{
    'name': "Módulo de Comprobantes Electrónicos Eliterp",
    'author': "Elitumdevelop S.A.",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'base',
        'web',
        'mail',
        'eliterp_treasury'
    ],
    'data': [
        'security/electronic_voucher.xml',
        'data/electronic_voucher_data.xml',
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/electronic_voucher_views.xml',
        'views/config_settings_views.xml',
        'views/company_views.xml',
        'views/point_printing_views.xml',
        'views/invoice_views.xml',
        'views/retention_views.xml'
    ],
    'qweb': [
        'static/src/xml/dashboard_templates.xml',
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
