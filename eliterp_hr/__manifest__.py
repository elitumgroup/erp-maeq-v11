# -*- coding: utf-8 -*-
# Copyright 2018 Elitumdevelop S.A, Ing. Mario Rangel
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    'name': "Módulo de RRHH",
    'summary': "RRHH.",
    'author': "Ing. Mario Rangel, Elitumgroup S.A",
    'website': "http://www.elitumgroup.com",
    'category': "Personalization",
    'license': "LGPL-3",
    'version': "1.0",
    'depends': [
        'base',
        'eliterp_management',
        'eliterp_accounting',
        'hr',
        'hr_contract',
        'hr_payroll',
        'hr_payroll_account',
        'hr_holidays',
        'hr_attendance',
        'mail'
    ],
    'data': [
        'data/sequences.xml',
        'data/hr_data.xml',
        'security/hr_security.xml',
        'security/ir.model.access.csv',
        'views/setting_views.xml',
        'views/employee_views.xml',
        'views/contract_views.xml',
        'views/advance_payment_views.xml',
        'views/payslip_views.xml',
        'views/payslip_run_views.xml',
        'views/payroll_provisions_views.xml',
        'views/holiday_views.xml',
        'views/attendance_views.xml',
        'views/extra_hours_views.xml',
        'reports/reports_views.xml',
        'reports/hr_reports.xml',
        'views/dashboard.xml',
        'views/assets.xml',
        'views/menus.xml',
        'views/memo_views.xml',
        'views/contract_term.xml',
        'views/term_contract.xml',
        'views/resignation_employment.xml'
    ],
    'init_xml': [],
    'update_xml': [],
    'installable': True,
    'active': False,
}
