# -*- coding: utf-8 -*-
from datetime import datetime, date, time
from odoo import models, fields, api

class MbaDailyInvoiceClosing(models.TransientModel):
    _name = 'mba.daily.invoice.closing'
    _description = 'Tablero Gerencial - Cierre Diario de Facturación y Arqueo Fiscal'

    @api.model
    def get_closing_data(self, report_date=None):
        today = fields.Date.today()
        if not report_date:
            target_date = today
        else:
            target_date = fields.Date.from_string(report_date)

        company = self.env.company

        # Facturas del día
        domain = [
            ('invoice_date', '=', target_date),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
        ]
        invoices = self.env['account.move'].search(domain, order='name asc')

        total_facturado = 0.0
        total_gravado = 0.0
        total_exento = 0.0
        total_itbms = 0.0
        total_contado = 0.0
        total_credito = 0.0

        facturas_list = []

        for inv in invoices:
            sign = 1 if inv.move_type == 'out_invoice' else -1
            amt_total = (inv.amount_total or 0.0) * sign
            amt_untaxed = (inv.amount_untaxed or 0.0) * sign
            amt_tax = (inv.amount_tax or 0.0) * sign

            total_facturado += amt_total
            total_itbms += amt_tax

            # Identificar gravado vs exento en líneas
            gravado_inv = 0.0
            exento_inv = 0.0
            for line in inv.invoice_line_ids:
                if line.display_type in ('line_section', 'line_note'):
                    continue
                sub = (line.price_subtotal or 0.0) * sign
                if line.tax_ids:
                    gravado_inv += sub
                else:
                    exento_inv += sub

            total_gravado += gravado_inv
            total_exento += exento_inv

            # Condición de crédito vs contado agnóstica
            is_credit = False
            term = inv.invoice_payment_term_id
            if term:
                tname = (term.name or '').lower()
                if any(kw in tname for kw in ('crédito', 'credito', '30', '60', '90', '120', 'días', 'dias')):
                    is_credit = True
                elif any(l.nb_days > 0 for l in term.line_ids):
                    is_credit = True

            if is_credit:
                total_credito += amt_total
                tipo_pago = 'Crédito'
            else:
                total_contado += amt_total
                tipo_pago = 'Contado'

            facturas_list.append({
                'id': inv.id,
                'name': inv.name,
                'partner_name': inv.partner_id.name if inv.partner_id else 'Consumidor Final',
                'move_type': inv.move_type,
                'tipo_pago': tipo_pago,
                'is_credit': is_credit,
                'amount_untaxed': amt_untaxed,
                'amount_tax': amt_tax,
                'amount_total': amt_total,
                'payment_state': inv.payment_state,
            })

        # Arqueo de pagos registrados hoy en el sistema
        payments_today = self.env['account.payment'].search([
            ('date', '=', target_date),
            ('payment_type', '=', 'inbound'),
            ('state', 'in', ('in_process', 'paid')),
            ('company_id', '=', company.id),
        ])

        cobros = {
            'efectivo': 0.0,
            'clave': 0.0,
            'credito_card': 0.0,
            'ach': 0.0,
            'total_cobrado': 0.0,
        }

        CARD_CLAVE = ('clave', 'débito', 'debito')
        CARD_CREDIT = ('visa', 'master', 'card', 'tarjeta', 'datafast')

        for p in payments_today:
            amt = p.amount or 0.0
            cobros['total_cobrado'] += amt
            jname = (p.journal_id.name or '').lower() if p.journal_id else ''
            jtype = p.journal_id.type if p.journal_id else ''

            if jtype == 'cash' or 'efectivo' in jname:
                cobros['efectivo'] += amt
            elif any(kw in jname for kw in CARD_CLAVE):
                cobros['clave'] += amt
            elif any(kw in jname for kw in CARD_CREDIT):
                cobros['credito_card'] += amt
            else:
                cobros['ach'] += amt

        dias_es = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        dia_semana_nombre = dias_es[target_date.weekday()]

        return {
            'report_date': target_date.strftime('%Y-%m-%d'),
            'date_display': f"{dia_semana_nombre}, {target_date.day}/{target_date.month}/{target_date.year}",
            'is_today': (target_date == today),
            'count_invoices': len(facturas_list),
            'total_facturado': total_facturado,
            'total_gravado': total_gravado,
            'total_exento': total_exento,
            'total_itbms': total_itbms,
            'total_contado': total_contado,
            'total_credito': total_credito,
            'cobros': cobros,
            'facturas': facturas_list,
        }
