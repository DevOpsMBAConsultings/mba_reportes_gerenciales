/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MbaCreditDashboard extends Component {
    static template = "mba_reportes_gerenciales.CreditDashboard";

    setup() {
        this.orm = useService("orm");
        const today = new Date();
        const currentYear = today.getFullYear();
        const currentMonth = today.getMonth() + 1;
        const currentQuarter = Math.floor((currentMonth - 1) / 3) + 1;

        this.state = useState({
            year: currentYear,
            month: currentMonth,
            quarter: currentQuarter,
            data: {
                year: currentYear,
                month: currentMonth,
                month_name: "",
                quarter: currentQuarter,
                totals: { sales: 0.0, expected: 0.0, residual: 0.0, paid: 0.0, by_journal: {} },
                weeks: [],
            },
            loading: true,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(
                "mba.credit.dashboard",
                "get_dashboard_data",
                [],
                { year: this.state.year, month: this.state.month }
            );
            this.state.data = res;
        } catch (error) {
            console.error("Error loading credit dashboard data:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async changeYear(offset) {
        this.state.year += offset;
        await this.loadData();
    }

    async selectQuarter(q) {
        this.state.quarter = q;
        this.state.month = (q - 1) * 3 + 1;
        await this.loadData();
    }

    async selectMonth(m) {
        this.state.month = m;
        this.state.quarter = Math.floor((m - 1) / 3) + 1;
        await this.loadData();
    }

    getQuarterLabel(q) {
        const labels = {
            1: "Ene - Mar",
            2: "Abr - Jun",
            3: "Jul - Sep",
            4: "Oct - Dic",
        };
        return labels[q] || "";
    }

    getMonthsForQuarter(q) {
        const monthsByQuarter = {
            1: [
                { number: 1, name: "Enero" },
                { number: 2, name: "Febrero" },
                { number: 3, name: "Marzo" },
            ],
            2: [
                { number: 4, name: "Abril" },
                { number: 5, name: "Mayo" },
                { number: 6, name: "Junio" },
            ],
            3: [
                { number: 7, name: "Julio" },
                { number: 8, name: "Agosto" },
                { number: 9, name: "Septiembre" },
            ],
            4: [
                { number: 10, name: "Octubre" },
                { number: 11, name: "Noviembre" },
                { number: 12, name: "Diciembre" },
            ],
        };
        return monthsByQuarter[q] || [];
    }

    formatMoney(val) {
        if (!val || val === 0) return "0.00";
        return Number(val).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    getCollectionPercent(w) {
        if (!w || !w.collection || w.collection.expected <= 0) {
            return w && w.collection && w.collection.paid > 0 ? 100 : 0;
        }
        const pct = (w.collection.paid / w.collection.expected) * 100;
        return Math.min(Math.round(pct), 100);
    }
}

registry.category("actions").add("mba_credit_dashboard", MbaCreditDashboard);
