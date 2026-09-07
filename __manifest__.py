# -*- coding: utf-8 -*-
{
    'name': 'Reportes Gerenciales y Centro de Mando Ejecutivo',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Analytics',
    'summary': 'Suite Ejecutiva de Reportes Gerenciales y Tableros Dinámicos: Ventas, Cobranza, Rentabilidad, Cierre Fiscal, Inventario y Órdenes Punto Pago | MBA Consultings',
    'description': """
Módulo Agnóstico de Reportes Gerenciales y Centro de Mando
===========================================================
Desarrollado por MBA Consultings para ofrecer reportería interactiva de alto nivel en Odoo 18.0:

1. Ventas a Crédito vs Expectativa de Cobranza (Semanal, Rollover de mora y detalle de caja)
2. Resumen Mensual de Ingresos (MTD) (Matriz diaria de cobros por método y facturas emitidas)
3. Cierre y Rentabilidad Real (Cierre diario y mensual con trazabilidad de costo SVL y POS)
4. Cierre Diario de Facturación y Arqueo Fiscal (Contado vs Crédito, desglose ITBMS y arqueo de pagos)
5. Control Operativo de Inventario y Abastecimiento (Stock físico, déficit por órdenes de venta en negativo y compras en tránsito)
6. Reporte de Órdenes Punto Pago (Conciliación de pagos y órdenes bajo método Punto Pago)
    """,
    'author': 'MBA Consultings',
    'website': 'https://mbaconsultings.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'sale',
        'stock',
        'purchase',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/mba_dashboard_views.xml',
        'views/mba_menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mba_reportes_gerenciales/static/src/scss/mba_dashboard.scss',
            'mba_reportes_gerenciales/static/src/xml/mba_credit_dashboard.xml',
            'mba_reportes_gerenciales/static/src/js/mba_credit_dashboard.js',
            'mba_reportes_gerenciales/static/src/xml/mba_monthly_income.xml',
            'mba_reportes_gerenciales/static/src/js/mba_monthly_income.js',
            'mba_reportes_gerenciales/static/src/xml/mba_profitability_dashboard.xml',
            'mba_reportes_gerenciales/static/src/js/mba_profitability_dashboard.js',
            'mba_reportes_gerenciales/static/src/xml/mba_daily_invoice_closing.xml',
            'mba_reportes_gerenciales/static/src/js/mba_daily_invoice_closing.js',
            'mba_reportes_gerenciales/static/src/xml/mba_inventory_dashboard.xml',
            'mba_reportes_gerenciales/static/src/js/mba_inventory_dashboard.js',
            'mba_reportes_gerenciales/static/src/xml/mba_punto_pago_report.xml',
            'mba_reportes_gerenciales/static/src/js/mba_punto_pago_report.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
