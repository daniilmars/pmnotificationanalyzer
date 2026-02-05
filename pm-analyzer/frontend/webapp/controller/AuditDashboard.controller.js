sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/m/MessageToast",
    "sap/ui/core/BusyIndicator",
    "sap/ui/model/Filter",
    "sap/ui/model/FilterOperator"
], function (Controller, JSONModel, MessageBox, MessageToast, BusyIndicator, Filter, FilterOperator) {
    "use strict";

    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.AuditDashboard", {

        onInit: function () {
            // Calculate default date range (last 30 days)
            var oToday = new Date();
            var oFromDate = new Date();
            oFromDate.setDate(oFromDate.getDate() - 30);

            var sToDate = this._formatDateForApi(oToday);
            var sFromDate = this._formatDateForApi(oFromDate);

            // Initialize audit model
            var oAuditModel = new JSONModel({
                busy: false,
                fromDate: sFromDate,
                toDate: sToDate,
                filterObjectClass: "",
                filterUsername: "",
                filterObjectId: "",
                summary: {
                    totalChanges: 0,
                    objectsChanged: 0,
                    usersInvolved: 0,
                    inserts: 0,
                    updates: 0,
                    deletes: 0
                },
                byObjectClass: [],
                byUser: [],
                recentChanges: []
            });
            this.getView().setModel(oAuditModel, "audit");

            // Load dashboard data
            this._loadAuditData();
        },

        _formatDateForApi: function (oDate) {
            var sYear = oDate.getFullYear();
            var sMonth = String(oDate.getMonth() + 1).padStart(2, '0');
            var sDay = String(oDate.getDate()).padStart(2, '0');
            return sYear + sMonth + sDay;
        },

        onNavBack: function () {
            var oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("worklist", {}, true);
        },

        onDateChange: function () {
            this._loadAuditData();
        },

        onRefresh: function () {
            this._loadAuditData();
        },

        onFilterChange: function () {
            this._loadAuditData();
        },

        onClearFilter: function () {
            var oModel = this.getView().getModel("audit");
            oModel.setProperty("/filterObjectClass", "");
            oModel.setProperty("/filterUsername", "");
            oModel.setProperty("/filterObjectId", "");
            this._loadAuditData();
        },

        _loadAuditData: async function () {
            var oModel = this.getView().getModel("audit");
            oModel.setProperty("/busy", true);

            try {
                // Build query parameters
                var sFromDate = oModel.getProperty("/fromDate");
                var sToDate = oModel.getProperty("/toDate");
                var sObjectClass = oModel.getProperty("/filterObjectClass");
                var sUsername = oModel.getProperty("/filterUsername");

                var aParams = [];
                if (sFromDate) aParams.push("from_date=" + sFromDate);
                if (sToDate) aParams.push("to_date=" + sToDate);
                if (sObjectClass) aParams.push("object_class=" + sObjectClass);
                if (sUsername) aParams.push("username=" + encodeURIComponent(sUsername));

                var sQuery = aParams.length > 0 ? "?" + aParams.join("&") : "";

                // Load audit report
                var response = await fetch("/api/audit/report" + sQuery);

                if (!response.ok) {
                    throw new Error("Failed to load audit data: " + response.statusText);
                }

                var data = await response.json();

                // Process and set data
                this._processAuditData(data);

                // Load recent changes separately for more detail
                await this._loadRecentChanges();

            } catch (error) {
                MessageBox.error("Failed to load audit data: " + error.message);
            } finally {
                oModel.setProperty("/busy", false);
            }
        },

        _processAuditData: function (data) {
            var oModel = this.getView().getModel("audit");

            // Set summary
            if (data.summary) {
                oModel.setProperty("/summary", {
                    totalChanges: data.summary.total_changes || 0,
                    objectsChanged: data.summary.objects_changed || 0,
                    usersInvolved: data.summary.users_involved || 0,
                    inserts: data.summary.inserts || 0,
                    updates: data.summary.updates || 0,
                    deletes: data.summary.deletes || 0
                });
            }

            // Set breakdown data
            oModel.setProperty("/byObjectClass", data.by_object_class || []);
            oModel.setProperty("/byUser", data.by_user || []);
        },

        _loadRecentChanges: async function () {
            var oModel = this.getView().getModel("audit");

            try {
                var sFromDate = oModel.getProperty("/fromDate");
                var sToDate = oModel.getProperty("/toDate");
                var sObjectClass = oModel.getProperty("/filterObjectClass");
                var sUsername = oModel.getProperty("/filterUsername");
                var sObjectId = oModel.getProperty("/filterObjectId");

                var aParams = ["limit=100"];
                if (sFromDate) aParams.push("from_date=" + sFromDate);
                if (sToDate) aParams.push("to_date=" + sToDate);
                if (sObjectClass) aParams.push("object_class=" + sObjectClass);
                if (sUsername) aParams.push("username=" + encodeURIComponent(sUsername));
                if (sObjectId) aParams.push("object_id=" + encodeURIComponent(sObjectId));

                var response = await fetch("/api/audit/changes?" + aParams.join("&"));

                if (!response.ok) {
                    throw new Error("Failed to load changes");
                }

                var data = await response.json();
                oModel.setProperty("/recentChanges", data.changes || []);

            } catch (error) {
                console.error("Error loading recent changes:", error);
            }
        },

        formatTimestamp: function (sTimestamp) {
            if (!sTimestamp) return "";
            try {
                var oDate = new Date(sTimestamp);
                return oDate.toLocaleString();
            } catch (e) {
                return sTimestamp;
            }
        },

        formatFieldsChanged: function (aFields) {
            if (!aFields || !Array.isArray(aFields)) return "";
            if (aFields.length === 0) return "-";

            var aFieldNames = aFields.map(function (field) {
                return field.field || "";
            }).filter(function (name) {
                return name !== "";
            });

            if (aFieldNames.length <= 3) {
                return aFieldNames.join(", ");
            }
            return aFieldNames.slice(0, 3).join(", ") + " (+" + (aFieldNames.length - 3) + " more)";
        },

        onChangePress: function (oEvent) {
            var oContext = oEvent.getSource().getBindingContext("audit");
            var oChangeData = oContext.getObject();

            this._showChangeDetails(oChangeData);
        },

        _showChangeDetails: function (oChangeData) {
            var that = this;

            // Build field changes content
            var aFieldItems = [];
            if (oChangeData.fields_changed && oChangeData.fields_changed.length > 0) {
                oChangeData.fields_changed.forEach(function (field) {
                    aFieldItems.push(new sap.m.ColumnListItem({
                        cells: [
                            new sap.m.Text({ text: field.table || "-" }),
                            new sap.m.Text({ text: field.field || "-" }),
                            new sap.m.Text({ text: field.old_value || "(empty)" }),
                            new sap.m.Text({ text: field.new_value || "(empty)" })
                        ]
                    }));
                });
            }

            var oFieldsTable = new sap.m.Table({
                columns: [
                    new sap.m.Column({ header: new sap.m.Text({ text: "Table" }), width: "100px" }),
                    new sap.m.Column({ header: new sap.m.Text({ text: "Field" }), width: "120px" }),
                    new sap.m.Column({ header: new sap.m.Text({ text: "Old Value" }) }),
                    new sap.m.Column({ header: new sap.m.Text({ text: "New Value" }) })
                ],
                items: aFieldItems
            });

            var oContent = new sap.m.VBox({
                items: [
                    new sap.m.Label({ text: "Change Number:", design: "Bold" }),
                    new sap.m.Text({ text: oChangeData.change_number }),
                    new sap.m.Label({ text: "Timestamp:", design: "Bold" }).addStyleClass("sapUiSmallMarginTop"),
                    new sap.m.Text({ text: this.formatTimestamp(oChangeData.timestamp) }),
                    new sap.m.Label({ text: "User:", design: "Bold" }).addStyleClass("sapUiSmallMarginTop"),
                    new sap.m.Text({ text: oChangeData.user }),
                    new sap.m.Label({ text: "Object:", design: "Bold" }).addStyleClass("sapUiSmallMarginTop"),
                    new sap.m.Text({ text: oChangeData.object_type + " / " + oChangeData.object_id }),
                    new sap.m.Label({ text: "Change Type:", design: "Bold" }).addStyleClass("sapUiSmallMarginTop"),
                    new sap.m.ObjectStatus({
                        text: oChangeData.change_type,
                        state: oChangeData.change_type === "Created" ? "Success" :
                            (oChangeData.change_type === "Deleted" ? "Error" : "Warning")
                    }),
                    new sap.m.Label({ text: "Field-Level Changes:", design: "Bold" }).addStyleClass("sapUiSmallMarginTop"),
                    oFieldsTable
                ]
            }).addStyleClass("sapUiSmallMargin");

            var oDialog = new sap.m.Dialog({
                title: "Change Document Details",
                contentWidth: "700px",
                content: oContent,
                beginButton: new sap.m.Button({
                    text: "Close",
                    press: function () {
                        oDialog.close();
                    }
                }),
                afterClose: function () {
                    oDialog.destroy();
                }
            });

            oDialog.open();
        },

        onObjectIdPress: function (oEvent) {
            var oSource = oEvent.getSource();
            var oContext = oSource.getBindingContext("audit");
            var sObjectType = oContext.getProperty("object_type");
            var sObjectId = oContext.getProperty("object_id");

            // Navigate to the object if it's a notification
            if (sObjectType === "QMEL") {
                var oRouter = this.getOwnerComponent().getRouter();
                oRouter.navTo("object", {
                    notificationId: sObjectId
                });
            } else {
                MessageToast.show("Object: " + sObjectType + " / " + sObjectId);
            }
        },

        onSearchChanges: function (oEvent) {
            var sQuery = oEvent.getParameter("query");
            var oTable = this.byId("changesTable");
            var oBinding = oTable.getBinding("items");

            if (sQuery) {
                var aFilters = [
                    new Filter("change_number", FilterOperator.Contains, sQuery),
                    new Filter("user", FilterOperator.Contains, sQuery),
                    new Filter("object_id", FilterOperator.Contains, sQuery)
                ];
                oBinding.filter(new Filter({
                    filters: aFilters,
                    and: false
                }));
            } else {
                oBinding.filter([]);
            }
        },

        onExportReport: async function () {
            var oModel = this.getView().getModel("audit");
            var sFromDate = oModel.getProperty("/fromDate");
            var sToDate = oModel.getProperty("/toDate");
            var sObjectClass = oModel.getProperty("/filterObjectClass");
            var sUsername = oModel.getProperty("/filterUsername");

            BusyIndicator.show(0);

            try {
                var aParams = [];
                if (sFromDate) aParams.push("from_date=" + sFromDate);
                if (sToDate) aParams.push("to_date=" + sToDate);
                if (sObjectClass) aParams.push("object_class=" + sObjectClass);
                if (sUsername) aParams.push("username=" + encodeURIComponent(sUsername));

                var sQuery = aParams.length > 0 ? "?" + aParams.join("&") : "";

                var response = await fetch("/api/audit/export" + sQuery);

                if (!response.ok) {
                    throw new Error("Export failed: " + response.statusText);
                }

                var blob = await response.blob();
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement("a");
                a.href = url;
                a.download = "audit_report_" + new Date().toISOString().split("T")[0] + ".csv";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);

                MessageToast.show("Audit report exported successfully");

            } catch (error) {
                MessageBox.error("Failed to export report: " + error.message);
            } finally {
                BusyIndicator.hide();
            }
        }
    });
});
