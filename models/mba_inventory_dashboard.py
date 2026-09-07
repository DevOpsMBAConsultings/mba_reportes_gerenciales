# -*- coding: utf-8 -*-
from odoo import models, fields, api

class MbaInventoryDashboard(models.TransientModel):
    _name = 'mba.inventory.dashboard'
    _description = 'Tablero Gerencial - Control Operativo de Inventario y Abastecimiento'

    @api.model
    def get_inventory_dashboard_data(self):
        company_id = self.env.company.id
        cid_str = str(company_id)

        # 1. Cuatro Totales Principales de Inventario
        self.env.cr.execute("""
            SELECT 
                -- Físico en Bodega (Stock > 0)
                COALESCE((
                    SELECT SUM(sq.quantity * COALESCE((pp.standard_price->>%s)::numeric, (pp.standard_price->>'1')::numeric, 0.0))
                    FROM stock_quant sq 
                    JOIN stock_location sl ON sl.id = sq.location_id
                    JOIN product_product pp ON pp.id = sq.product_id
                    WHERE sl.usage = 'internal' AND sq.quantity > 0 AND sq.company_id = %s
                ), 0.0) AS fisico,

                -- Déficit Ventas Negativas (< 0)
                COALESCE((
                    SELECT SUM(abs(sq.quantity) * COALESCE((pp.standard_price->>%s)::numeric, (pp.standard_price->>'1')::numeric, 0.0))
                    FROM stock_quant sq 
                    JOIN stock_location sl ON sl.id = sq.location_id
                    JOIN product_product pp ON pp.id = sq.product_id
                    WHERE sl.usage = 'internal' AND sq.quantity < 0 AND sq.company_id = %s
                ), 0.0) AS deficit,

                -- Compras en Tránsito
                COALESCE((
                    SELECT SUM((pol.product_qty - COALESCE(pol.qty_received, 0.0)) * pol.price_unit)
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON po.id = pol.order_id
                    WHERE po.state IN ('purchase', 'done')
                      AND po.company_id = %s
                      AND (pol.product_qty - COALESCE(pol.qty_received, 0.0)) > 0
                ), 0.0) AS transito
        """, (cid_str, company_id, cid_str, company_id, company_id))

        row = self.env.cr.fetchone()
        fisico = float(row[0] or 0.0)
        deficit = float(row[1] or 0.0)
        transito = float(row[2] or 0.0)
        proyectado = fisico - deficit + transito

        # 2. Desglose de Déficit por Ventas Negativas
        self.env.cr.execute("""
            SELECT 
                pp.id AS product_id,
                COALESCE(pt.name->>'es_PA', pt.name->>'en_US', pt.name->>'es_ES', 'Producto') AS product_name,
                pp.default_code AS default_code,
                sl.complete_name AS location_name,
                abs(sq.quantity) AS negative_qty,
                COALESCE((pp.standard_price->>%s)::numeric, (pp.standard_price->>'1')::numeric, 0.0) AS cost,
                abs(sq.quantity) * COALESCE((pp.standard_price->>%s)::numeric, (pp.standard_price->>'1')::numeric, 0.0) AS deficit_value,
                (
                    SELECT string_agg(DISTINCT so.name, ', ')
                    FROM (
                        SELECT so2.name
                        FROM stock_move sm
                        JOIN stock_location sld ON sld.id = sm.location_dest_id
                        JOIN sale_order_line sol ON sol.id = sm.sale_line_id
                        JOIN sale_order so2 ON so2.id = sol.order_id
                        WHERE sm.product_id = sq.product_id 
                          AND sm.state = 'done' 
                          AND sld.usage = 'customer'
                        ORDER BY sm.date DESC 
                        LIMIT 3
                    ) so
                ) AS sale_orders,
                (
                    SELECT sm.date::date
                    FROM stock_move sm
                    JOIN stock_location sld ON sld.id = sm.location_dest_id
                    WHERE sm.product_id = sq.product_id 
                          AND sm.state = 'done' 
                          AND sld.usage = 'customer'
                        ORDER BY sm.date DESC 
                        LIMIT 1
                ) AS move_date
            FROM stock_quant sq
            JOIN stock_location sl ON sl.id = sq.location_id
            JOIN product_product pp ON pp.id = sq.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE sl.usage = 'internal'
              AND sq.quantity < 0
              AND sq.company_id = %s
            ORDER BY deficit_value DESC
        """, (cid_str, cid_str, company_id))

        deficit_list = []
        for r in self.env.cr.dictfetchall():
            deficit_list.append({
                'product_id': r['product_id'],
                'default_code': r['default_code'] or '',
                'product_name': r['product_name'],
                'location_name': r['location_name'],
                'sale_orders': r['sale_orders'] or '',
                'date': str(r['move_date'] or ''),
                'negative_qty': float(r['negative_qty']),
                'cost': float(r['cost']),
                'deficit_value': float(r['deficit_value']),
            })

        # 3. Desglose de Compras en Tránsito
        self.env.cr.execute("""
            SELECT 
                po.name AS po_name,
                rp.name AS partner_name,
                COALESCE(pt.name->>'es_PA', pt.name->>'en_US', pt.name->>'es_ES', 'Producto') AS product_name,
                pol.product_qty AS product_qty,
                (pol.product_qty - COALESCE(pol.qty_received, 0.0)) AS qty_pending,
                pol.price_unit AS price_unit,
                (pol.product_qty - COALESCE(pol.qty_received, 0.0)) * pol.price_unit AS transit_value,
                pol.date_planned::date AS date_planned
            FROM purchase_order_line pol
            JOIN purchase_order po ON po.id = pol.order_id
            JOIN res_partner rp ON rp.id = po.partner_id
            JOIN product_product pp ON pp.id = pol.product_id
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE po.state IN ('purchase', 'done')
              AND po.company_id = %s
              AND (pol.product_qty - COALESCE(pol.qty_received, 0.0)) > 0
            ORDER BY pol.date_planned ASC, transit_value DESC
        """, (company_id,))

        transit_list = []
        for r in self.env.cr.dictfetchall():
            transit_list.append({
                'po_name': r['po_name'],
                'partner_name': r['partner_name'] or 'Sin Proveedor',
                'product_name': r['product_name'],
                'product_qty': float(r['product_qty']),
                'qty_pending': float(r['qty_pending']),
                'price_unit': float(r['price_unit']),
                'transit_value': float(r['transit_value']),
                'date_planned': str(r['date_planned'] or '-'),
            })

        return {
            'fisico': fisico,
            'deficit': deficit,
            'transito': transito,
            'proyectado': proyectado,
            'deficit_list': deficit_list,
            'transit_list': transit_list,
        }
