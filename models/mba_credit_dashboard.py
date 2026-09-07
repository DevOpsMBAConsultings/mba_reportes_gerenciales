# -*- coding: utf-8 -*-
import calendar
from datetime import date
from odoo import models, fields, api

class MbaCreditDashboard(models.TransientModel):
    _name = 'mba.credit.dashboard'
    _description = 'Tablero Gerencial - Ventas a Crédito vs Expectativa de Cobro'

    @api.model
    def get_dashboard_data(self, year=None, month=None):
        today = fields.Date.today()
        year = int(year) if year else today.year
        month = int(month) if month else today.month
        company = self.env.company

        # Días del mes seleccionado
        _, num_days = calendar.monthrange(year, month)
        date_start = date(year, month, 1)
        date_end = date(year, month, num_days)

        # 1. Ventas Totales y Desglose Crédito vs Contado por Semanas (1-7, 8-15, 16-23, 24-31)
        # Separando Facturas Brutas (Crédito / Contado) y Notas de Crédito de forma agnóstica
        self.env.cr.execute("""
            SELECT 
                CASE 
                    WHEN EXTRACT(DAY FROM m.invoice_date) BETWEEN 1 AND 7 THEN 1
                    WHEN EXTRACT(DAY FROM m.invoice_date) BETWEEN 8 AND 15 THEN 2
                    WHEN EXTRACT(DAY FROM m.invoice_date) BETWEEN 16 AND 23 THEN 3
                    ELSE 4
                END AS week_idx,
                -- Total Neto (Facturas - Notas de Crédito)
                COUNT(m.id) AS count_total,
                COALESCE(SUM(CASE WHEN m.move_type = 'out_refund' THEN -m.amount_total ELSE m.amount_total END), 0.0) AS total_sales,
                -- Facturas Brutas a Crédito (detectadas por plazo con días > 0 o nombre que indique crédito)
                COALESCE(SUM(CASE 
                    WHEN m.move_type = 'out_invoice' AND (
                        EXISTS (SELECT 1 FROM account_payment_term_line l WHERE l.payment_id = t.id AND l.nb_days > 0)
                        OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%crédito%%'
                        OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%credito%%'
                    ) THEN m.amount_total ELSE 0.0 END), 0.0) AS credit_sales,
                COUNT(CASE 
                    WHEN m.move_type = 'out_invoice' AND (
                        EXISTS (SELECT 1 FROM account_payment_term_line l WHERE l.payment_id = t.id AND l.nb_days > 0)
                        OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%crédito%%'
                        OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%credito%%'
                    ) THEN m.id END) AS count_credit,
                -- Facturas Brutas de Contado (o sin plazo de crédito)
                COALESCE(SUM(CASE 
                    WHEN m.move_type = 'out_invoice' AND NOT (
                        EXISTS (SELECT 1 FROM account_payment_term_line l WHERE l.payment_id = t.id AND l.nb_days > 0)
                        OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%crédito%%'
                        OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%credito%%'
                    ) THEN m.amount_total ELSE 0.0 END), 0.0) AS cash_sales,
                COUNT(CASE 
                    WHEN m.move_type = 'out_invoice' AND NOT (
                        EXISTS (SELECT 1 FROM account_payment_term_line l WHERE l.payment_id = t.id AND l.nb_days > 0)
                        OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%crédito%%'
                        OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%credito%%'
                    ) THEN m.id END) AS count_cash,
                -- Notas de Crédito Emitidas
                COALESCE(SUM(CASE WHEN m.move_type = 'out_refund' THEN m.amount_total ELSE 0.0 END), 0.0) AS refund_sales,
                COUNT(CASE WHEN m.move_type = 'out_refund' THEN m.id END) AS count_refund
            FROM account_move m
            LEFT JOIN account_payment_term t ON t.id = m.invoice_payment_term_id
            WHERE m.move_type IN ('out_invoice', 'out_refund')
              AND m.state = 'posted'
              AND m.company_id = %s
              AND m.invoice_date BETWEEN %s AND %s
            GROUP BY 1
            ORDER BY 1
        """, (company.id, date_start, date_end))

        sales_by_week = {}
        for row in self.env.cr.fetchall():
            sales_by_week[row[0]] = {
                'count': row[1],
                'amount': float(row[2]),
                'credit': float(row[3]),
                'count_credit': row[4],
                'cash': float(row[5]),
                'count_cash': row[6],
                'refund': float(row[7]),
                'count_refund': row[8],
            }

        # 2. Pagos Reales Efectivamente Cobrados en el Mes (Crédito + Contado) con desglose por Diario / Método
        self.env.cr.execute("""
            SELECT 
                CASE 
                    WHEN EXTRACT(DAY FROM pay.date) BETWEEN 1 AND 7 THEN 1
                    WHEN EXTRACT(DAY FROM pay.date) BETWEEN 8 AND 15 THEN 2
                    WHEN EXTRACT(DAY FROM pay.date) BETWEEN 16 AND 23 THEN 3
                    ELSE 4
                END AS pay_week_idx,
                COUNT(DISTINCT pay.id) AS count_payments,
                COALESCE(SUM(apr.amount), 0.0) AS total_paid,
                COALESCE(SUM(CASE 
                    WHEN (EXISTS (
                        SELECT 1 FROM account_payment_term_line l WHERE l.payment_id = t.id AND l.nb_days > 0
                    ) OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%crédito%%'
                      OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%credito%%'
                    ) THEN apr.amount ELSE 0.0 END), 0.0) AS paid_credit,
                COALESCE(SUM(CASE 
                    WHEN NOT (EXISTS (
                        SELECT 1 FROM account_payment_term_line l WHERE l.payment_id = t.id AND l.nb_days > 0
                    ) OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%crédito%%'
                      OR LOWER(COALESCE(t.name->>'es_PA', t.name->>'es_ES', t.name->>'en_US', '')) LIKE '%%credito%%'
                    ) THEN apr.amount ELSE 0.0 END), 0.0) AS paid_cash
            FROM account_move m
            JOIN account_move_line aml ON aml.move_id = m.id
            JOIN account_account aa ON aa.id = aml.account_id
            LEFT JOIN account_payment_term t ON t.id = m.invoice_payment_term_id
            JOIN account_partial_reconcile apr ON (apr.debit_move_id = aml.id OR apr.credit_move_id = aml.id)
            JOIN account_move_line aml_pay ON (aml_pay.id = apr.credit_move_id OR aml_pay.id = apr.debit_move_id) AND aml_pay.id != aml.id
            JOIN account_payment pay ON pay.id = aml_pay.payment_id
            WHERE m.move_type = 'out_invoice'
              AND aa.account_type = 'asset_receivable'
              AND m.company_id = %s
              AND pay.date BETWEEN %s AND %s
            GROUP BY 1
            ORDER BY 1
        """, (company.id, date_start, date_end))
        
        paid_by_week = {}
        for row in self.env.cr.fetchall():
            paid_by_week[row[0]] = {
                'count': row[1],
                'amount': float(row[2]),
                'paid_credit': float(row[3]),
                'paid_cash': float(row[4]),
                'by_journal': {}
            }

        # Desglose de cobros por diario/método por semana
        self.env.cr.execute("""
            SELECT 
                CASE 
                    WHEN EXTRACT(DAY FROM pay.date) BETWEEN 1 AND 7 THEN 1
                    WHEN EXTRACT(DAY FROM pay.date) BETWEEN 8 AND 15 THEN 2
                    WHEN EXTRACT(DAY FROM pay.date) BETWEEN 16 AND 23 THEN 3
                    ELSE 4
                END AS pay_week_idx,
                j.name AS journal_name,
                COALESCE(SUM(apr.amount), 0.0) AS journal_amount
            FROM account_move m
            JOIN account_move_line aml ON aml.move_id = m.id
            JOIN account_account aa ON aa.id = aml.account_id
            JOIN account_partial_reconcile apr ON (apr.debit_move_id = aml.id OR apr.credit_move_id = aml.id)
            JOIN account_move_line aml_pay ON (aml_pay.id = apr.credit_move_id OR aml_pay.id = apr.debit_move_id) AND aml_pay.id != aml.id
            JOIN account_payment pay ON pay.id = aml_pay.payment_id
            JOIN account_journal j ON j.id = pay.journal_id
            WHERE m.move_type = 'out_invoice'
              AND aa.account_type = 'asset_receivable'
              AND m.company_id = %s
              AND pay.date BETWEEN %s AND %s
            GROUP BY 1, 2
            ORDER BY 1, 3 DESC
        """, (company.id, date_start, date_end))

        for row in self.env.cr.fetchall():
            w_idx, j_name, j_amount = row[0], row[1], float(row[2])
            if w_idx not in paid_by_week:
                paid_by_week[w_idx] = {'count': 0, 'amount': 0.0, 'paid_credit': 0.0, 'paid_cash': 0.0, 'by_journal': {}}
            paid_by_week[w_idx]['by_journal'][j_name] = j_amount

        # 3. Proyección de Vencimientos y Rollover de Mora (Crédito y Vencidos)
        current_week_idx = 1 if today.day <= 7 else (2 if today.day <= 15 else (3 if today.day <= 23 else 4))
        is_current_month = (year == today.year and month == today.month)
        is_past_month = (year < today.year or (year == today.year and month < today.month))
        is_future_month = (year > today.year or (year == today.year and month > today.month))

        self.env.cr.execute("""
            SELECT 
                aml.id,
                aml.date_maturity,
                aml.balance,
                aml.amount_residual,
                CASE 
                    WHEN EXTRACT(DAY FROM aml.date_maturity) BETWEEN 1 AND 7 THEN 1
                    WHEN EXTRACT(DAY FROM aml.date_maturity) BETWEEN 8 AND 15 THEN 2
                    WHEN EXTRACT(DAY FROM aml.date_maturity) BETWEEN 16 AND 23 THEN 3
                    ELSE 4
                END AS original_week_idx
            FROM account_move_line aml
            JOIN account_move m ON m.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            LEFT JOIN account_payment_term t ON t.id = m.invoice_payment_term_id
            WHERE aa.account_type = 'asset_receivable'
              AND m.state = 'posted'
              AND m.move_type = 'out_invoice'
              AND m.company_id = %s
              AND (
                  (aml.date_maturity BETWEEN %s AND %s)
                  OR (aml.date_maturity < %s AND aml.amount_residual > 0 AND %s = TRUE)
              )
        """, (company.id, date_start, date_end, date_start, is_current_month))

        collections = {
            1: {'expected': 0.0, 'residual': 0.0, 'paid': paid_by_week.get(1, {}).get('amount', 0.0), 'paid_credit': paid_by_week.get(1, {}).get('paid_credit', 0.0), 'paid_cash': paid_by_week.get(1, {}).get('paid_cash', 0.0), 'by_journal': paid_by_week.get(1, {}).get('by_journal', {}), 'rollover': 0.0},
            2: {'expected': 0.0, 'residual': 0.0, 'paid': paid_by_week.get(2, {}).get('amount', 0.0), 'paid_credit': paid_by_week.get(2, {}).get('paid_credit', 0.0), 'paid_cash': paid_by_week.get(2, {}).get('paid_cash', 0.0), 'by_journal': paid_by_week.get(2, {}).get('by_journal', {}), 'rollover': 0.0},
            3: {'expected': 0.0, 'residual': 0.0, 'paid': paid_by_week.get(3, {}).get('amount', 0.0), 'paid_credit': paid_by_week.get(3, {}).get('paid_credit', 0.0), 'paid_cash': paid_by_week.get(3, {}).get('paid_cash', 0.0), 'by_journal': paid_by_week.get(3, {}).get('by_journal', {}), 'rollover': 0.0},
            4: {'expected': 0.0, 'residual': 0.0, 'paid': paid_by_week.get(4, {}).get('amount', 0.0), 'paid_credit': paid_by_week.get(4, {}).get('paid_credit', 0.0), 'paid_cash': paid_by_week.get(4, {}).get('paid_cash', 0.0), 'by_journal': paid_by_week.get(4, {}).get('by_journal', {}), 'rollover': 0.0}
        }

        for line in self.env.cr.dictfetchall():
            mat_date = line['date_maturity']
            res = float(line['amount_residual'])
            bal = float(line['balance'])
            orig_week = line['original_week_idx']

            if is_past_month:
                pass
            elif is_current_month:
                if mat_date < date_start:
                    # Venció en mes anterior y sigue impago -> Se arrastra a la semana actual viva
                    target_week = current_week_idx
                    collections[target_week]['rollover'] += res
                    collections[target_week]['residual'] += res
                    collections[target_week]['expected'] += res
                else:
                    if mat_date < today and res > 0:
                        target_week = current_week_idx
                        if target_week != orig_week:
                            collections[target_week]['rollover'] += res
                        collections[target_week]['residual'] += res
                        collections[target_week]['expected'] += res
                    else:
                        collections[orig_week]['expected'] += bal
                        collections[orig_week]['residual'] += res
            else:
                collections[orig_week]['expected'] += bal
                collections[orig_week]['residual'] += res

        if is_past_month:
            for idx in (1, 2, 3, 4):
                collections[idx]['expected'] = collections[idx]['paid']

        month_names = [
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]

        weeks_data = []
        labels = [('Días 1-7', 1), ('Días 8-15', 2), ('Días 16-23', 3), ('Días 24-31', 4)]
        
        total_sales_month = 0.0
        total_credit_sales_month = 0.0
        total_cash_sales_month = 0.0
        total_refund_sales_month = 0.0
        total_expected_month = 0.0
        total_residual_month = 0.0
        total_paid_month = 0.0
        total_paid_credit_month = 0.0
        total_paid_cash_month = 0.0
        month_journals = {}

        for label, idx in labels:
            sw = sales_by_week.get(idx, {'count': 0, 'amount': 0.0, 'credit': 0.0, 'cash': 0.0, 'count_credit': 0, 'count_cash': 0, 'refund': 0.0, 'count_refund': 0})
            cw = collections[idx]
            
            total_sales_month += sw['amount']
            total_credit_sales_month += sw['credit']
            total_cash_sales_month += sw['cash']
            total_refund_sales_month += sw['refund']
            total_expected_month += cw['expected']
            total_residual_month += cw['residual']
            total_paid_month += cw['paid']
            total_paid_credit_month += cw.get('paid_credit', 0.0)
            total_paid_cash_month += cw.get('paid_cash', 0.0)

            for jn, ja in cw.get('by_journal', {}).items():
                month_journals[jn] = month_journals.get(jn, 0.0) + ja

            is_current_week = (is_current_month and idx == current_week_idx)

            weeks_data.append({
                'index': idx,
                'label': label,
                'is_current': is_current_week,
                'sales': {
                    'count': sw['count'],
                    'amount': sw['amount'],
                    'credit': sw['credit'],
                    'cash': sw['cash'],
                    'count_credit': sw['count_credit'],
                    'count_cash': sw['count_cash'],
                    'refund': sw['refund'],
                    'count_refund': sw['count_refund'],
                },
                'collection': {
                    'expected': cw['expected'],
                    'residual': cw['residual'],
                    'paid': cw['paid'],
                    'paid_credit': cw['paid_credit'],
                    'paid_cash': cw['paid_cash'],
                    'by_journal': cw['by_journal'],
                    'rollover': cw['rollover'],
                }
            })

        quarter = (month - 1) // 3 + 1

        return {
            'year': year,
            'month': month,
            'month_name': month_names[month],
            'quarter': quarter,
            'is_current_month': is_current_month,
            'is_future_month': is_future_month,
            'totals': {
                'sales': total_sales_month,
                'credit_sales': total_credit_sales_month,
                'cash_sales': total_cash_sales_month,
                'refund_sales': total_refund_sales_month,
                'expected': total_expected_month,
                'residual': total_residual_month,
                'paid': total_paid_month,
                'paid_credit': total_paid_credit_month,
                'paid_cash': total_paid_cash_month,
                'by_journal': month_journals,
            },
            'weeks': weeks_data,
        }
