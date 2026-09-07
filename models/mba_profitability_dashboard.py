# -*- coding: utf-8 -*-
import calendar
from datetime import datetime, date, time, timedelta
from odoo import models, fields, api

class MbaProfitabilityDashboard(models.TransientModel):
    _name = 'mba.profitability.dashboard'
    _description = 'Tablero Gerencial - Cierre Diario y Cierre Mensual de Rentabilidad'

    @api.model
    def get_profitability_data(self, period_type='day', report_date=None, year=None, month=None):
        today = fields.Date.today()
        period_type = period_type or 'day'
        company = self.env.company

        if period_type == 'month':
            target_year = int(year) if year else today.year
            target_month = int(month) if month else today.month
            _, num_days = calendar.monthrange(target_year, target_month)
            date_start = date(target_year, target_month, 1)
            date_end = date(target_year, target_month, num_days)

            meses_es = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
            period_display = f"Cierre Mensual: {meses_es[target_month]} {target_year}"
        else:
            if not report_date:
                target_date = today
            else:
                target_date = fields.Date.from_string(report_date)
            date_start = target_date
            date_end = target_date
            dias_es = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            period_display = f"Cierre Diario: {dias_es[target_date.weekday()]}, {target_date.day}/{target_date.month}/{target_date.year}"

        # 1. Facturas de Ventas en el rango (excluyendo ventas originadas en POS para evitar doble conteo si aplica)
        domain = [
            ('invoice_date', '>=', date_start),
            ('invoice_date', '<=', date_end),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
        ]
        invoices = self.env['account.move'].search(domain)
        if 'pos_order_ids' in self.env['account.move']._fields:
            ventas_invoices = invoices.filtered(lambda i: not i.pos_order_ids)
        else:
            ventas_invoices = invoices

        total_ventas_facturas = 0.0
        ventas_por_categoria = {}
        costo_ventas_trazado = {}

        StockMove = self.env['stock.move']
        move_has_sale_line = 'sale_line_id' in StockMove._fields

        for inv in ventas_invoices:
            sign = 1 if inv.move_type == 'out_invoice' else -1
            for line in inv.invoice_line_ids:
                if line.display_type in ('line_section', 'line_note'):
                    continue
                if not line.product_id:
                    continue

                line_subtotal = (line.price_subtotal or 0.0) * sign
                total_ventas_facturas += line_subtotal
                categ = line.product_id.categ_id
                cid = categ.id if categ else 0
                cname = categ.complete_name if categ else 'Sin Categoría'

                if cid not in ventas_por_categoria:
                    ventas_por_categoria[cid] = {
                        'name': cname,
                        'ventas': 0.0,
                        'costo': 0.0,
                    }
                ventas_por_categoria[cid]['ventas'] += line_subtotal

                # Trazabilidad de Costo Real a la entrega de inventario
                pid = line.product_id.id
                sale_lines = line.sale_line_ids if 'sale_line_ids' in line._fields else self.env['sale.order.line']
                p_cost = None

                if move_has_sale_line and len(sale_lines) == 1:
                    moves = sale_lines.move_ids.filtered(
                        lambda m: m.state == 'done' and m.location_dest_id.usage == 'customer'
                    )
                    total_qty = sum(moves.mapped('quantity'))
                    total_move_cost = -sum(moves.stock_valuation_layer_ids.mapped('value'))
                    if total_qty > 0 and total_move_cost > 0:
                        unit_cost = total_move_cost / total_qty
                        p_cost = unit_cost * (line.quantity or 0.0) * sign

                if p_cost is None:
                    p_cost = (line.quantity or 0.0) * sign * (line.product_id.standard_price or 0.0)

                costo_ventas_trazado[pid] = costo_ventas_trazado.get(pid, 0.0) + p_cost
                ventas_por_categoria[cid]['costo'] += p_cost

        # 2. Ventas de Mostrador / POS (si está instalado)
        total_ventas_pos = 0.0
        costo_pos = 0.0

        if 'pos.order' in self.env:
            pos_start = datetime.combine(date_start, time.min)
            pos_end = datetime.combine(date_end, time.max)
            pos_orders = self.env['pos.order'].search([
                ('date_order', '>=', pos_start),
                ('date_order', '<=', pos_end),
                ('state', 'in', ('paid', 'done', 'invoiced')),
                ('company_id', '=', company.id),
            ])

            for order in pos_orders:
                for pline in order.lines:
                    p_sub = pline.price_subtotal or 0.0
                    total_ventas_pos += p_sub

                    categ = pline.product_id.categ_id
                    cid = categ.id if categ else 0
                    cname = categ.complete_name if categ else 'Sin Categoría'

                    if cid not in ventas_por_categoria:
                        ventas_por_categoria[cid] = {
                            'name': cname,
                            'ventas': 0.0,
                            'costo': 0.0,
                        }
                    ventas_por_categoria[cid]['ventas'] += p_sub

                    c_unit = pline.product_id.standard_price or 0.0
                    line_cost = (pline.qty or 0.0) * c_unit
                    costo_pos += line_cost
                    ventas_por_categoria[cid]['costo'] += line_cost

        # 3. Consolidación de Totales y Márgenes
        total_ventas = total_ventas_facturas + total_ventas_pos
        total_costo = sum(costo_ventas_trazado.values()) + costo_pos
        utilidad_bruta = total_ventas - total_costo
        margen_pct = (utilidad_bruta / total_ventas * 100.0) if total_ventas > 0 else 0.0

        # Formatear lista de categorías ordenada por mayor volumen de venta
        cat_list = []
        for cid, data in ventas_por_categoria.items():
            c_utilidad = data['ventas'] - data['costo']
            c_margen = (c_utilidad / data['ventas'] * 100.0) if data['ventas'] > 0 else 0.0
            cat_list.append({
                'id': cid,
                'name': data['name'],
                'ventas': data['ventas'],
                'costo': data['costo'],
                'utilidad': c_utilidad,
                'margen_pct': c_margen,
            })
        cat_list.sort(key=lambda x: x['ventas'], reverse=True)

        return {
            'period_type': period_type,
            'period_display': period_display,
            'report_date': date_start.strftime('%Y-%m-%d'),
            'year': year,
            'month': month,
            'total_ventas': total_ventas,
            'total_ventas_facturas': total_ventas_facturas,
            'total_ventas_pos': total_ventas_pos,
            'total_costo': total_costo,
            'utilidad_bruta': utilidad_bruta,
            'margen_pct': margen_pct,
            'categorias': cat_list,
        }
