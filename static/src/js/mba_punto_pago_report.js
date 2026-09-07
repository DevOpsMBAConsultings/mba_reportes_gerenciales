/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MbaPuntoPagoReport extends Component {
    static template = "mba_reportes_gerenciales.PuntoPagoReport";

    setup() {
        this.orm = useService("orm");
        const today = new Date();
        const todayStr = today.toISOString().split("T")[0];

        this.state = useState({
            dateFrom: todayStr,
            dateTo: todayStr,
            activeTab: 'pagos', // 'pagos' | 'ordenes'
            loading: true,
            data: null,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    get isToday() {
        const todayStr = new Date().toISOString().split("T")[0];
        return this.state.dateFrom === todayStr && this.state.dateTo === todayStr;
    }

    get isYesterday() {
        const y = new Date();
        y.setDate(y.getDate() - 1);
        const yStr = y.toISOString().split("T")[0];
        return this.state.dateFrom === yStr && this.state.dateTo === yStr;
    }

    get isCurrentMonth() {
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split("T")[0];
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split("T")[0];
        return this.state.dateFrom === firstDay && this.state.dateTo === lastDay;
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "mba.punto.pago.report",
                "get_punto_pago_data",
                [],
                {
                    date_from: this.state.dateFrom,
                    date_to: this.state.dateTo,
                }
            );
            this.state.data = data;
        } catch (error) {
            console.error("Error al cargar datos del reporte Punto Pago:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async onDateFromChange(newDate) {
        if (newDate && this.state.dateFrom !== newDate) {
            this.state.dateFrom = newDate;
            await this.loadData();
        }
    }

    async onDateToChange(newDate) {
        if (newDate && this.state.dateTo !== newDate) {
            this.state.dateTo = newDate;
            await this.loadData();
        }
    }

    async setToday() {
        const todayStr = new Date().toISOString().split("T")[0];
        this.state.dateFrom = todayStr;
        this.state.dateTo = todayStr;
        await this.loadData();
    }

    async setYesterday() {
        const y = new Date();
        y.setDate(y.getDate() - 1);
        const yStr = y.toISOString().split("T")[0];
        this.state.dateFrom = yStr;
        this.state.dateTo = yStr;
        await this.loadData();
    }

    async setThisMonth() {
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split("T")[0];
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().split("T")[0];
        this.state.dateFrom = firstDay;
        this.state.dateTo = lastDay;
        await this.loadData();
    }

    formatMoney(val) {
        if (!val || val === 0) return "0.00";
        return Number(val).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }
}

registry.category("actions").add("mba_punto_pago_report", MbaPuntoPagoReport);
