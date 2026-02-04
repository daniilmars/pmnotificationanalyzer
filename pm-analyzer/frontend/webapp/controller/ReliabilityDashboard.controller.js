sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/m/MessageToast",
    "sap/ui/core/BusyIndicator"
], function (Controller, JSONModel, MessageBox, MessageToast, BusyIndicator) {
    "use strict";

    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.ReliabilityDashboard", {

        onInit: function () {
            // Initialize reliability model
            var oReliabilityModel = new JSONModel({
                busy: false,
                selectedPeriod: "365",
                summary: {
                    totalEquipment: 0,
                    averageReliabilityScore: 0,
                    averageAvailability: 0,
                    criticalRiskCount: 0,
                    highRiskCount: 0
                },
                equipmentList: [],
                attentionRequired: [],
                fmeaHighlights: [],
                selectedEquipment: null
            });
            this.getView().setModel(oReliabilityModel, "reliability");

            // Load dashboard data
            this._loadDashboardData();
        },

        onNavBack: function () {
            var oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("worklist", {}, true);
        },

        onPeriodChange: function () {
            this._loadDashboardData();
        },

        onRefresh: function () {
            this._loadDashboardData();
        },

        formatPercent: function (value) {
            if (value === undefined || value === null) {
                return "0";
            }
            return Math.round(value * 100);
        },

        _loadDashboardData: async function () {
            var oModel = this.getView().getModel("reliability");
            var sPeriod = oModel.getProperty("/selectedPeriod");
            oModel.setProperty("/busy", true);

            try {
                // Load dashboard data
                var response = await fetch("/api/reliability/dashboard?period_days=" + sPeriod);

                if (!response.ok) {
                    throw new Error("Failed to load reliability dashboard: " + response.statusText);
                }

                var data = await response.json();

                // Process and set dashboard data
                this._processDashboardData(data);

            } catch (error) {
                MessageBox.error("Failed to load reliability dashboard: " + error.message);
            } finally {
                oModel.setProperty("/busy", false);
            }
        },

        _processDashboardData: function (data) {
            var oModel = this.getView().getModel("reliability");

            // Set summary data
            if (data.summary) {
                oModel.setProperty("/summary", {
                    totalEquipment: data.summary.total_equipment || 0,
                    averageReliabilityScore: Math.round(data.summary.average_reliability_score || 0),
                    averageAvailability: Math.round(data.summary.average_availability || 0),
                    criticalRiskCount: data.summary.critical_risk_count || 0,
                    highRiskCount: data.summary.high_risk_count || 0
                });
            }

            // Set equipment list
            oModel.setProperty("/equipmentList", data.equipment_list || []);

            // Set attention required list
            oModel.setProperty("/attentionRequired", data.attention_required || []);

            // Process FMEA highlights
            var fmeaHighlights = (data.fmea_highlights || []).map(function (item) {
                return {
                    failure_mode: item.failure_mode,
                    severity: item.severity,
                    occurrence: item.occurrence || 5,
                    detection: item.detection || 5,
                    rpn: item.rpn,
                    recommended_action: item.recommended_action
                };
            });
            oModel.setProperty("/fmeaHighlights", fmeaHighlights);
        },

        onEquipmentPress: function (oEvent) {
            var oContext = oEvent.getSource().getBindingContext("reliability");
            var sEquipmentId = oContext.getProperty("equipment_id");

            // Show equipment details in a dialog
            this._showEquipmentDetails(sEquipmentId);
        },

        _showEquipmentDetails: async function (sEquipmentId) {
            var oModel = this.getView().getModel("reliability");
            var sPeriod = oModel.getProperty("/selectedPeriod");

            BusyIndicator.show(0);

            try {
                // Fetch detailed equipment metrics in parallel
                var [mtbfResponse, mttrResponse, availabilityResponse, predictiveResponse, weibullResponse] = await Promise.all([
                    fetch("/api/reliability/equipment/" + encodeURIComponent(sEquipmentId) + "/mtbf?period_days=" + sPeriod),
                    fetch("/api/reliability/equipment/" + encodeURIComponent(sEquipmentId) + "/mttr?period_days=" + sPeriod),
                    fetch("/api/reliability/equipment/" + encodeURIComponent(sEquipmentId) + "/availability?period_days=" + sPeriod),
                    fetch("/api/reliability/equipment/" + encodeURIComponent(sEquipmentId) + "/predictive?period_days=" + sPeriod),
                    fetch("/api/reliability/equipment/" + encodeURIComponent(sEquipmentId) + "/weibull?period_days=" + sPeriod)
                ]);

                var mtbfData = await mtbfResponse.json();
                var mttrData = await mttrResponse.json();
                var availabilityData = await availabilityResponse.json();
                var predictiveData = await predictiveResponse.json();
                var weibullData = await weibullResponse.json();

                // Create and show dialog with equipment details
                this._createEquipmentDialog(sEquipmentId, {
                    mtbf: mtbfData,
                    mttr: mttrData,
                    availability: availabilityData,
                    predictive: predictiveData,
                    weibull: weibullData
                });

            } catch (error) {
                MessageBox.error("Failed to load equipment details: " + error.message);
            } finally {
                BusyIndicator.hide();
            }
        },

        _createEquipmentDialog: function (sEquipmentId, data) {
            var that = this;

            // Create dialog content
            var oContent = new sap.m.VBox({
                items: [
                    // MTBF Section
                    new sap.m.Panel({
                        headerText: this._getText("mtbfMetrics"),
                        content: [
                            new sap.m.HBox({
                                justifyContent: "SpaceBetween",
                                items: [
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("mtbfHours") }),
                                            new sap.m.ObjectNumber({
                                                number: Math.round(data.mtbf.mtbf_hours || 0),
                                                unit: "hrs"
                                            })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("mtbfDays") }),
                                            new sap.m.ObjectNumber({
                                                number: Math.round(data.mtbf.mtbf_days || 0),
                                                unit: "days"
                                            })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("failureCount") }),
                                            new sap.m.ObjectNumber({
                                                number: data.mtbf.failure_count || 0
                                            })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("trend") }),
                                            new sap.m.ObjectStatus({
                                                text: data.mtbf.trend || "stable",
                                                state: data.mtbf.trend === "improving" ? "Success" :
                                                    (data.mtbf.trend === "degrading" ? "Error" : "None")
                                            })
                                        ]
                                    })
                                ]
                            }).addStyleClass("sapUiSmallMargin")
                        ]
                    }),

                    // MTTR Section
                    new sap.m.Panel({
                        headerText: this._getText("mttrMetrics"),
                        content: [
                            new sap.m.HBox({
                                justifyContent: "SpaceBetween",
                                items: [
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("avgRepairTime") }),
                                            new sap.m.ObjectNumber({
                                                number: Math.round(data.mttr.mttr_hours * 10) / 10 || 0,
                                                unit: "hrs"
                                            })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("minRepairTime") }),
                                            new sap.m.ObjectNumber({
                                                number: Math.round(data.mttr.min_repair_time * 10) / 10 || 0,
                                                unit: "hrs"
                                            })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("maxRepairTime") }),
                                            new sap.m.ObjectNumber({
                                                number: Math.round(data.mttr.max_repair_time * 10) / 10 || 0,
                                                unit: "hrs"
                                            })
                                        ]
                                    })
                                ]
                            }).addStyleClass("sapUiSmallMargin")
                        ]
                    }),

                    // Availability Section
                    new sap.m.Panel({
                        headerText: this._getText("availabilityMetrics"),
                        content: [
                            new sap.m.HBox({
                                justifyContent: "SpaceBetween",
                                items: [
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("availability") }),
                                            new sap.m.ObjectNumber({
                                                number: Math.round(data.availability.availability_percent * 10) / 10 || 0,
                                                unit: "%",
                                                state: data.availability.availability_percent >= 95 ? "Success" :
                                                    (data.availability.availability_percent >= 90 ? "Warning" : "Error")
                                            })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("uptimeHours") }),
                                            new sap.m.ObjectNumber({
                                                number: Math.round(data.availability.uptime_hours || 0),
                                                unit: "hrs"
                                            })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("unplannedDowntime") }),
                                            new sap.m.ObjectNumber({
                                                number: Math.round(data.availability.unplanned_downtime_hours || 0),
                                                unit: "hrs",
                                                state: "Error"
                                            })
                                        ]
                                    })
                                ]
                            }).addStyleClass("sapUiSmallMargin")
                        ]
                    }),

                    // Weibull Analysis Section
                    new sap.m.Panel({
                        headerText: this._getText("weibullAnalysis"),
                        content: [
                            new sap.m.HBox({
                                justifyContent: "SpaceBetween",
                                items: [
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("failurePattern") }),
                                            new sap.m.ObjectStatus({
                                                text: this._formatFailurePattern(data.weibull.failure_pattern),
                                                state: data.weibull.failure_pattern === "wear_out" ? "Error" :
                                                    (data.weibull.failure_pattern === "infant_mortality" ? "Warning" : "None")
                                            })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("shapeParameter") }),
                                            new sap.m.Text({ text: "β = " + (data.weibull.shape_parameter || 1).toFixed(2) })
                                        ]
                                    }),
                                    new sap.m.VBox({
                                        items: [
                                            new sap.m.Label({ text: this._getText("scaleParameter") }),
                                            new sap.m.Text({ text: "η = " + Math.round(data.weibull.scale_parameter || 0) + " hrs" })
                                        ]
                                    })
                                ]
                            }).addStyleClass("sapUiSmallMargin")
                        ]
                    }),

                    // Predictive Maintenance Section
                    new sap.m.Panel({
                        headerText: this._getText("predictiveMaintenance"),
                        content: [
                            new sap.m.VBox({
                                items: [
                                    new sap.m.HBox({
                                        justifyContent: "SpaceBetween",
                                        items: [
                                            new sap.m.VBox({
                                                items: [
                                                    new sap.m.Label({ text: this._getText("failureProbability30Days") }),
                                                    new sap.m.ObjectNumber({
                                                        number: Math.round((data.predictive.predicted_failure_probability || 0) * 100),
                                                        unit: "%",
                                                        state: data.predictive.predicted_failure_probability > 0.5 ? "Error" :
                                                            (data.predictive.predicted_failure_probability > 0.3 ? "Warning" : "Success")
                                                    })
                                                ]
                                            }),
                                            new sap.m.VBox({
                                                items: [
                                                    new sap.m.Label({ text: this._getText("estimatedRemainingLife") }),
                                                    new sap.m.ObjectNumber({
                                                        number: Math.round(data.predictive.estimated_remaining_life_days || 0),
                                                        unit: "days"
                                                    })
                                                ]
                                            }),
                                            new sap.m.VBox({
                                                items: [
                                                    new sap.m.Label({ text: this._getText("urgency") }),
                                                    new sap.m.ObjectStatus({
                                                        text: data.predictive.urgency || "monitor",
                                                        state: data.predictive.urgency === "immediate" ? "Error" :
                                                            (data.predictive.urgency === "soon" ? "Warning" : "None")
                                                    })
                                                ]
                                            })
                                        ]
                                    }).addStyleClass("sapUiSmallMargin"),
                                    new sap.m.MessageStrip({
                                        text: data.predictive.recommended_action || "",
                                        type: data.predictive.urgency === "immediate" ? "Error" :
                                            (data.predictive.urgency === "soon" ? "Warning" : "Information"),
                                        showIcon: true
                                    }).addStyleClass("sapUiSmallMargin")
                                ]
                            })
                        ]
                    })
                ]
            });

            // Create dialog
            var oDialog = new sap.m.Dialog({
                title: this._getText("equipmentDetails") + ": " + sEquipmentId,
                contentWidth: "700px",
                content: oContent,
                beginButton: new sap.m.Button({
                    text: this._getText("close"),
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

        _formatFailurePattern: function (pattern) {
            switch (pattern) {
                case "infant_mortality":
                    return "Infant Mortality (β < 1)";
                case "wear_out":
                    return "Wear-Out (β > 1)";
                case "random":
                default:
                    return "Random (β ≈ 1)";
            }
        },

        _getText: function (sKey) {
            return this.getOwnerComponent().getModel("i18n").getResourceBundle().getText(sKey);
        },

        onFilterFMEA: async function () {
            var oModel = this.getView().getModel("reliability");
            var sPeriod = oModel.getProperty("/selectedPeriod");
            var sThreshold = this.byId("rpnThresholdInput").getValue() || "100";

            BusyIndicator.show(0);

            try {
                var response = await fetch("/api/reliability/fmea?period_days=" + sPeriod);

                if (!response.ok) {
                    throw new Error("Failed to load FMEA data");
                }

                var data = await response.json();

                // Filter by RPN threshold
                var filteredItems = (data.fmea_items || []).filter(function (item) {
                    return item.rpn >= parseInt(sThreshold, 10);
                });

                oModel.setProperty("/fmeaHighlights", filteredItems);

                MessageToast.show(filteredItems.length + " failure modes with RPN >= " + sThreshold);

            } catch (error) {
                MessageBox.error("Failed to filter FMEA data: " + error.message);
            } finally {
                BusyIndicator.hide();
            }
        },

        onExportReport: async function () {
            var oModel = this.getView().getModel("reliability");
            var sPeriod = oModel.getProperty("/selectedPeriod");

            BusyIndicator.show(0);

            try {
                var response = await fetch("/api/reliability/export?period_days=" + sPeriod);

                if (!response.ok) {
                    throw new Error("Export failed: " + response.statusText);
                }

                var blob = await response.blob();
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement("a");
                a.href = url;
                a.download = "reliability_report_" + new Date().toISOString().split("T")[0] + ".csv";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);

                MessageToast.show("Report exported successfully");

            } catch (error) {
                MessageBox.error("Failed to export report: " + error.message);
            } finally {
                BusyIndicator.hide();
            }
        }
    });
});
