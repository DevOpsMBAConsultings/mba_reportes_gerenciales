# -*- coding: utf-8 -*-
from datetime import datetime, date, time, timedelta
from odoo import models, fields, api

class MbaPuntoPagoReport(models.TransientModel):
    _name = 'mba.punto.pago.report'
    _description = 'Reporte Gerencial de Órdenes y Pagos Punto Pago'

    @api.model
    def get_punto_pago_data(self, date_from=None, date_to=None):
        today = fields.Date.today()
        if not date_from:
            target_from = today
        else:
            target_from = fields.Date.from_string(date_from)

        if not date_to:
            target_to = today
        else:
            target_to = fields.Date.from_string(date_to)

        company = self.env.company

        # 1. Búsqueda de Diarios / Métodos de Pago relacionados con "Punto Pago"
        punto_pago_journals = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            '|', '|',
            ('name', 'ilike', 'punto pago'),
            ('name', 'ilike', 'puntopago'),
            ('code', 'ilike', 'PP'),
        ])

        # 1.A. Pagos directos en diario Punto Pago
        payment_domain = [
            ('date', '>=', target_from),
            ('date', '<=', target_to),
            ('company_id', '=', company.id),
            ('payment_type', '=', 'inbound'),
            ('state', 'in', ('in_process', 'paid')),
        ]
        if punto_pago_journals:
            payment_domain.append(('journal_id', 'in', punto_pago_journals.ids))
        else:
            payment_domain.append(('journal_id.name', 'ilike', 'punto pago'))

        direct_payments = self.env['account.payment'].search(payment_domain)

        # 1.B. Pagos conciliados con facturas que tienen término de pago o referencia 'Punto Pago'
        pp_invoices = self.env['account.move'].search([
            ('company_id', '=', company.id),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            '|', '|',
            ('invoice_payment_term_id.name', 'ilike', 'punto pago'),
            ('payment_reference', 'ilike', 'punto pago'),
            ('ref', 'ilike', 'punto pago'),
        ])

        reconciled_payment_ids = set()
        for inv in pp_invoices:
            for line in inv.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable'):
                for partial in (line.matched_debit_ids | line.matched_credit_ids):
                    p_obj = partial.debit_move_id.payment_id or partial.credit_move_id.payment_id
                    if p_obj and p_obj.date and target_from <= p_obj.date <= target_to and p_obj.state in ('in_process', 'paid'):
                        reconciled_payment_ids.add(p_obj.id)

        all_payments = direct_payments | self.env['account.payment'].browse(reconciled_payment_ids)
        payments = all_payments.sorted(key=lambda p: (p.date, p.id), reverse=True)

        total_pagado = 0.0
        transacciones = []

        for p in payments:
            amt = p.amount or 0.0
            total_pagado += amt

            # Buscar facturas asociadas a este pago
            invoices_info = []
            receivable_lines = p.move_id.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
            for line in receivable_lines:
                for partial in (line.matched_debit_ids | line.matched_credit_ids):
                    inv_move = partial.debit_move_id.move_id if partial.debit_move_id.move_id != p.move_id else partial.credit_move_id.move_id
                    if inv_move.is_invoice():
                        invoices_info.append(inv_move.name)

            transacciones.append({
                'id': p.id,
                'type': 'payment',
                'reference': p.name,
                'date': p.date.strftime('%Y-%m-%d'),
                'partner_name': p.partner_id.name if p.partner_id else 'Cliente General',
                'journal_name': p.journal_id.name if p.journal_id else 'Punto Pago',
                'amount': amt,
                'state': dict(p._fields['state'].selection).get(p.state, p.state),
                'invoices': ', '.join(set(invoices_info)) if invoices_info else (p.memo or 'Sin factura vinculada'),
            })

        # 2. Órdenes de Venta relacionadas con Punto Pago
        # Detectadas por payment_term, método o notas
        so_domain = [
            ('date_order', '>=', datetime.combine(target_from, time.min)),
            ('date_order', '<=', datetime.combine(target_to, time.max)),
            ('company_id', '=', company.id),
            ('state', 'in', ('sale', 'done')),
        ]
        
        # Filtramos órdenes que hagan referencia a Punto Pago
        so_orders = self.env['sale.order'].search(so_domain, order='date_order desc')
        punto_pago_orders = []
        total_ordenes_monto = 0.0

        for so in so_orders:
            term_name = (so.payment_term_id.name or '').lower() if so.payment_term_id else ''
            client_ref = (so.client_order_ref or '').lower()
            note = (so.note or '').lower()

            # Si el término de pago o notas mencionan punto pago
            is_pp = ('punto pago' in term_name or 'punto de pago' in term_name or 
                     'puntopago' in term_name or 'punto pago' in client_ref or 'punto pago' in note)
            
            # Verificación de pagos si woocommerce o módulos de pago tienen payment_method
            if not is_pp and hasattr(so, 'woocommerce_payment_method'):
                w_pm = str(getattr(so, 'woocommerce_payment_method') or '').lower()
                w_title = str(getattr(so, 'woocommerce_payment_method_title') or '').lower()
                if 'punto' in w_pm or 'puntopago' in w_pm or 'punto' in w_title:
                    is_pp = True

            if is_pp:
                amt = so.amount_total or 0.0
                total_ordenes_monto += amt
                punto_pago_orders.append({
                    'id': so.id,
                    'name': so.name,
                    'date_order': fields.Datetime.context_timestamp(self, so.date_order).strftime('%Y-%m-%d %H:%M'),
                    'partner_name': so.partner_id.name if so.partner_id else 'Sin Cliente',
                    'amount_total': amt,
                    'invoice_status': dict(so._fields['invoice_status'].selection).get(so.invoice_status, so.invoice_status),
                    'payment_term': so.payment_term_id.name if so.payment_term_id else 'Inmediato',
                })

        # 3. Pagos de Punto de Venta (POS) si está instalado
        pos_punto_pago_total = 0.0
        pos_transactions = []
        if 'pos.payment' in self.env:
            pos_domain = [
                ('payment_date', '>=', datetime.combine(target_from, time.min)),
                ('payment_date', '<=', datetime.combine(target_to, time.max)),
                ('company_id', '=', company.id),
                '|',
                ('payment_method_id.name', 'ilike', 'punto pago'),
                ('payment_method_id.name', 'ilike', 'puntopago'),
            ]
            pos_payments = self.env['pos.payment'].search(pos_domain, order='payment_date desc')
            for pp in pos_payments:
                amt = pp.amount or 0.0
                pos_punto_pago_total += amt
                pos_transactions.append({
                    'id': pp.id,
                    'order_name': pp.pos_order_id.name if pp.pos_order_id else 'Ticket POS',
                    'partner_name': pp.pos_order_id.partner_id.name if (pp.pos_order_id and pp.pos_order_id.partner_id) else 'Consumidor Final',
                    'date': fields.Datetime.context_timestamp(self, pp.payment_date).strftime('%Y-%m-%d %H:%M'),
                    'method_name': pp.payment_method_id.name,
                    'amount': amt,
                })

        gran_total_recaudado = total_pagado + pos_punto_pago_total

        return {
            'date_from': target_from.strftime('%Y-%m-%d'),
            'date_to': target_to.strftime('%Y-%m-%d'),
            'is_single_day': (target_from == target_to),
            'date_display': f"{target_from.strftime('%d/%m/%Y')} - {target_to.strftime('%d/%m/%Y')}" if target_from != target_to else target_from.strftime('%d/%m/%Y'),
            'count_payments': len(transacciones) + len(pos_transactions),
            'count_orders': len(punto_pago_orders),
            'total_recaudado': gran_total_recaudado,
            'total_pagos_facturas': total_pagado,
            'total_pagos_pos': pos_punto_pago_total,
            'total_ordenes_monto': total_ordenes_monto,
            'transacciones_pagos': transacciones,
            'transacciones_pos': pos_transactions,
            'ordenes_venta': punto_pago_orders,
        }
