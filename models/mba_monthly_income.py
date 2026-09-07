# -*- coding: utf-8 -*-
import calendar
from datetime import datetime, date, time, timedelta
from odoo import models, fields, api

class MbaMonthlyIncome(models.TransientModel):
    _name = 'mba.monthly.income'
    _description = 'Matriz Gerencial - Resumen Mensual de Ingresos MTD'

    @api.model
    def get_monthly_income_data(self, year=None, month=None):
        today = fields.Date.today()
        year = int(year) if year else today.year
        month = int(month) if month else today.month
        company = self.env.company

        # Rango del mes
        _, num_days = calendar.monthrange(year, month)
        date_from = date(year, month, 1)
        date_to = date(year, month, num_days)

        days_list = [date_from + timedelta(days=i) for i in range(num_days)]
        day_keys = [d.strftime('%Y-%m-%d') for d in days_list]

        day_headers = []
        dias_semana_es = {
            'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié',
            'Thu': 'Jue', 'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom'
        }
        for d in days_list:
            day_headers.append({
                'key': d.strftime('%Y-%m-%d'),
                'day_num': d.day,
                'day_name': dias_semana_es.get(d.strftime('%a'), d.strftime('%a')),
                'is_today': (d == today),
                'is_weekend': (d.weekday() in (5, 6))
            })

        concepts = [
            {'code': 'efectivo', 'name': 'Efectivo', 'icon': 'fa-money', 'color': 'success', 'informative': False},
            {'code': 'clave', 'name': 'Tarjeta Clave (Débito)', 'icon': 'fa-credit-card', 'color': 'info', 'informative': False},
            {'code': 'visa_masterd', 'name': 'Visa / Mastercard (Crédito)', 'icon': 'fa-cc-visa', 'color': 'primary', 'informative': False},
            {'code': 'ach_directo', 'name': 'ACH / Transferencia Directa', 'icon': 'fa-university', 'color': 'secondary', 'informative': False},
            {'code': 'cobros_cxc', 'name': 'Cobros CxC (Recibos / Abonos)', 'icon': 'fa-check-circle', 'color': 'dark', 'informative': False},
            {'code': 'facturas_credito', 'name': 'Facturas a Crédito (Emitidas)', 'icon': 'fa-file-text-o', 'color': 'warning', 'informative': True},
        ]

        # Inicializar matrices
        matrix = {c['code']: {dk: 0.0 for dk in day_keys} for c in concepts}
        daily_totals = {dk: 0.0 for dk in day_keys}

        # 1. Facturas a crédito emitidas en el rango (Informativo, no suma a flujo de caja directo)
        invoices = self.env['account.move'].search([
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
        ])

        for inv in invoices:
            dk = inv.invoice_date.strftime('%Y-%m-%d')
            if dk not in matrix['facturas_credito']:
                continue

            # Determinar si la factura es a crédito
            is_credit = False
            term = inv.invoice_payment_term_id
            if term:
                tname = (term.name or '').lower()
                if any(kw in tname for kw in ('crédito', 'credito', '30', '60', '90', '120', 'días', 'dias')):
                    is_credit = True
                elif any(l.nb_days > 0 for l in term.line_ids):
                    is_credit = True

            if is_credit:
                sign = 1 if inv.move_type == 'out_invoice' else -1
                matrix['facturas_credito'][dk] += (inv.amount_total or 0.0) * sign

        # 2. Pagos bancarios y de caja registrados en el sistema
        payments = self.env['account.payment'].search([
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('payment_type', '=', 'inbound'),
            ('state', 'in', ('in_process', 'paid')),
            ('company_id', '=', company.id),
        ])

        CARD_CLAVE = ('clave', 'débito', 'debito')
        CARD_CREDIT = ('visa', 'master', 'card', 'tarjeta', 'datafast')

        for p in payments:
            dk = p.date.strftime('%Y-%m-%d')
            if dk not in matrix['efectivo']:
                continue

            amount = p.amount or 0.0
            journal = p.journal_id
            jtype = journal.type if journal else ''
            jname = (journal.name or '').lower()

            # Clasificar si es cobro de factura previa (CxC)
            is_cxc = False
            receivable_lines = p.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
            )
            for line in receivable_lines:
                for partial in line.matched_debit_ids:
                    inv_move = partial.debit_move_id.move_id
                    if inv_move.is_invoice() and inv_move.invoice_date < p.date:
                        is_cxc = True
                        break
                if is_cxc:
                    break

            if is_cxc:
                matrix['cobros_cxc'][dk] += amount
                daily_totals[dk] += amount
            else:
                if jtype == 'cash':
                    matrix['efectivo'][dk] += amount
                    daily_totals[dk] += amount
                elif jtype == 'bank':
                    if any(kw in jname for kw in CARD_CLAVE):
                        matrix['clave'][dk] += amount
                    elif any(kw in jname for kw in CARD_CREDIT):
                        matrix['visa_masterd'][dk] += amount
                    else:
                        matrix['ach_directo'][dk] += amount
                    daily_totals[dk] += amount

        # 3. Ventas de caja directa de Punto de Venta (POS) si está instalado
        if 'pos.order' in self.env:
            pos_date_start = datetime.combine(date_from, time.min)
            pos_date_end = datetime.combine(date_to, time.max)
            pos_orders = self.env['pos.order'].search([
                ('date_order', '>=', pos_date_start),
                ('date_order', '<=', pos_date_end),
                ('state', 'in', ('paid', 'done', 'invoiced')),
                ('company_id', '=', company.id),
            ])

            for order in pos_orders:
                d_local = fields.Datetime.context_timestamp(self, order.date_order).date()
                dk = d_local.strftime('%Y-%m-%d')
                if dk not in matrix['efectivo']:
                    continue

                for pp in order.payment_ids:
                    amount = pp.amount or 0.0
                    method = pp.payment_method_id
                    mtype = method.type
                    mname = (method.name or '').lower()

                    if mtype == 'cash':
                        matrix['efectivo'][dk] += amount
                        daily_totals[dk] += amount
                    elif mtype == 'bank':
                        if any(kw in mname for kw in CARD_CLAVE):
                            matrix['clave'][dk] += amount
                        elif any(kw in mname for kw in CARD_CREDIT):
                            matrix['visa_masterd'][dk] += amount
                        else:
                            matrix['ach_directo'][dk] += amount
                        daily_totals[dk] += amount

        # 4. Totales por concepto acumulados
        concept_totals = {}
        total_income_collected = 0.0

        for c in concepts:
            code = c['code']
            c_sum = sum(matrix[code].values())
            concept_totals[code] = c_sum
            if not c['informative']:
                total_income_collected += c_sum

        meses_es = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]

        return {
            'year': year,
            'month': month,
            'month_name': f"{meses_es[month]} {year}",
            'day_headers': day_headers,
            'concepts': concepts,
            'matrix': matrix,
            'daily_totals': daily_totals,
            'concept_totals': concept_totals,
            'total_income_collected': total_income_collected,
            'total_credit_sales': concept_totals.get('facturas_credito', 0.0),
        }
