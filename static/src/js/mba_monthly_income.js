/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MbaMonthlyIncome extends Component {
    static template = "mba_reportes_gerenciales.MonthlyIncome";

    setup() {
        this.orm = useService("orm");
        const today = new Date();

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
            year: today.getFullYear(),
            month: today.getMonth() + 1,
            loading: true,
            data: null,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "mba.monthly.income",
                "get_monthly_income_data",
                [],
                {
                    year: this.state.year,
                    month: this.state.month,
                }
            );
            this.state.data = data;
        } catch (error) {
            console.error("Error al cargar datos de ingresos mensuales MTD:", error);
        } finally {
            this.state.loading = false;
        }
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
}

registry.category("actions").add("mba_monthly_income", MbaMonthlyIncome);
