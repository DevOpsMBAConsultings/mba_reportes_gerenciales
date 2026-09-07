/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MbaProfitabilityDashboard extends Component {
    static template = "mba_reportes_gerenciales.ProfitabilityDashboard";

    setup() {
        this.orm = useService("orm");
        const today = new Date();
        const todayStr = today.toISOString().split("T")[0];

        this.monthsList = [
            { number: 1, name: "Enero" },
            { number: 2, name: "Febrero" },
            { number: 3, name: "Marzo" },
            { number: 4, name: "Abril" },
            { number: 5, name: "Mayo" },
            { number: 6, name: "Junio" },
            { number: 7, name: "Julio" },
            { number: 8, name: "Agosto" },
            { number: 9, name: "Septiembre" },
            { number: 10, name: "Octubre" },
            { number: 11, name: "Noviembre" },
            { number: 12, name: "Diciembre" },
        ];

        this.state = useState({
            periodType: "day", // 'day' | 'month'
            reportDate: todayStr,
            year: today.getFullYear(),
            month: today.getMonth() + 1,
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
                "mba.profitability.dashboard",
                "get_profitability_data",
                [],
                {
                    period_type: this.state.periodType,
                    report_date: this.state.reportDate,
                    year: this.state.year,
                    month: this.state.month,
                }
            );
            this.state.data = data;
        } catch (error) {
            console.error("Error al cargar datos de rentabilidad:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async setPeriodType(type) {
        if (this.state.periodType !== type) {
            this.state.periodType = type;
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

    async onDateChange(newDate) {
        if (newDate && this.state.reportDate !== newDate) {
            this.state.reportDate = newDate;
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

    async selectMonth(m) {
        if (this.state.month !== m) {
            this.state.month = m;
            await this.loadData();
        }
    }

    async changeYear(offset) {
        this.state.year += offset;
        await this.loadData();
    }

    formatMoney(val) {
        if (!val || val === 0) return "0.00";
        return Number(val).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    formatNumber(val) {
        if (!val || val === 0) return "0.0";
        return Number(val).toFixed(1);
    }
}

registry.category("actions").add("mba_profitability_dashboard", MbaProfitabilityDashboard);
