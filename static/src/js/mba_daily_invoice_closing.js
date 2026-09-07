/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MbaDailyInvoiceClosing extends Component {
    static template = "mba_reportes_gerenciales.DailyInvoiceClosing";

    setup() {
        this.orm = useService("orm");
        const todayStr = new Date().toISOString().split("T")[0];

        this.state = useState({
            reportDate: todayStr,
            loading: true,
            data: null,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    get isToday() {
        const todayStr = new Date().toISOString().split("T")[0];
        return this.state.reportDate === todayStr;
    }

    get isYesterday() {
        const y = new Date();
        y.setDate(y.getDate() - 1);
        const yStr = y.toISOString().split("T")[0];
        return this.state.reportDate === yStr;
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "mba.daily.invoice.closing",
                "get_closing_data",
                [],
                { report_date: this.state.reportDate }
            );
            this.state.data = data;
        } catch (error) {
            console.error("Error al cargar datos de cierre de facturación:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async onDateChange(newDate) {
        if (newDate && this.state.reportDate !== newDate) {
            this.state.reportDate = newDate;
            await this.loadData();
        }
    }

    async setToday() {
        const todayStr = new Date().toISOString().split("T")[0];
        if (this.state.reportDate !== todayStr) {
            this.state.reportDate = todayStr;
            await this.loadData();
        }
    }

    async setYesterday() {
        const y = new Date();
        y.setDate(y.getDate() - 1);
        const yStr = y.toISOString().split("T")[0];
        if (this.state.reportDate !== yStr) {
            this.state.reportDate = yStr;
            await this.loadData();
        }
    }

    async changeDay(offset) {
        const current = new Date(this.state.reportDate + "T00:00:00");
        current.setDate(current.getDate() + offset);
        const nextDateStr = current.toISOString().split("T")[0];
        this.state.reportDate = nextDateStr;
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

registry.category("actions").add("mba_daily_invoice_closing", MbaDailyInvoiceClosing);
