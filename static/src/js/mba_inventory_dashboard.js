/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MbaInventoryDashboard extends Component {
    static template = "mba_reportes_gerenciales.InventoryDashboard";

    setup() {
        this.orm = useService("orm");

        this.state = useState({
            loading: true,
            data: null,
            activeAuditTab: 'deficit',
            deficitSortField: "deficit_value",
            deficitSortAsc: false,
            transitSortField: "date_planned",
            transitSortAsc: true,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    setAuditTab(tabName) {
        this.state.activeAuditTab = tabName;
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "mba.inventory.dashboard",
                "get_inventory_dashboard_data",
                []
            );
            this.state.data = data;
        } catch (error) {
            console.error("Error al cargar datos del tablero de inventario:", error);
        } finally {
            this.state.loading = false;
        }
    }

    get sortedDeficitList() {
        if (!this.state.data || !this.state.data.deficit_list) return [];
        const list = [...this.state.data.deficit_list];
        const field = this.state.deficitSortField;
        const asc = this.state.deficitSortAsc;

        return list.sort((a, b) => {
            let valA = a[field];
            let valB = b[field];

            if (typeof valA === "string") {
                valA = valA.toLowerCase();
                valB = (valB || "").toLowerCase();
                return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
            }
            return asc ? valA - valB : valB - valA;
        });
    }

    get sortedTransitList() {
        if (!this.state.data || !this.state.data.transit_list) return [];
        const list = [...this.state.data.transit_list];
        const field = this.state.transitSortField;
        const asc = this.state.transitSortAsc;

        return list.sort((a, b) => {
            let valA = a[field];
            let valB = b[field];

            if (typeof valA === "string") {
                valA = valA.toLowerCase();
                valB = (valB || "").toLowerCase();
                return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
            }
            return asc ? valA - valB : valB - valA;
        });
    }

    sortDeficit(field) {
        if (this.state.deficitSortField === field) {
            this.state.deficitSortAsc = !this.state.deficitSortAsc;
        } else {
            this.state.deficitSortField = field;
            this.state.deficitSortAsc = field === "product_name" || field === "default_code" || field === "sale_orders";
        }
    }

    sortTransit(field) {
        if (this.state.transitSortField === field) {
            this.state.transitSortAsc = !this.state.transitSortAsc;
        } else {
            this.state.transitSortField = field;
            this.state.transitSortAsc = true;
        }
    }

    getDeficitSortIcon(field) {
        if (this.state.deficitSortField !== field) return "fa-sort text-muted opacity-25";
        return this.state.deficitSortAsc ? "fa-sort-asc text-primary" : "fa-sort-desc text-primary";
    }

    getTransitSortIcon(field) {
        if (this.state.transitSortField !== field) return "fa-sort text-muted opacity-25";
        return this.state.transitSortAsc ? "fa-sort-asc text-transit" : "fa-sort-desc text-transit";
    }

    formatMoney(val) {
        if (!val || val === 0) return "0.00";
        return Number(val).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    formatNumber(val) {
        if (!val || val === 0) return "0";
        return Number(val).toLocaleString("en-US", {
            maximumFractionDigits: 2,
        });
    }
}

registry.category("actions").add("mba_inventory_dashboard", MbaInventoryDashboard);
