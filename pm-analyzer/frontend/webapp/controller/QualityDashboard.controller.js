sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/m/MessageToast",
    "sap/ui/core/BusyIndicator"
], function (Controller, JSONModel, MessageBox, MessageToast, BusyIndicator) {
    "use strict";

    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.QualityDashboard", {

        onInit: function () {
            // Initialize dashboard model
            var oDashboardModel = new JSONModel({
                busy: false,
                selectedPeriod: "30",
                summary: {
                    averageScore: 0,
                    scoreTrend: 0,
                    period: "",
                    totalAnalyzed: 0,
                    avgCompleteness: 0,
                    avgAccuracy: 0,
                    avgTimeliness: 0,
                    avgConsistency: 0,
                    alcoaCompliance: 0
                },
                trend: {
                    dataPoints: []
                },
                distribution: {
                    excellent: 0,
                    good: 0,
                    needsImprovement: 0
                },
                alcoaPrinciples: [],
                commonIssues: [],
                recommendations: []
            });
            this.getView().setModel(oDashboardModel, "dashboard");

            // Load dashboard data
            this._loadDashboardData();
        },

        onNavBack: function () {
            var oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("worklist", {}, true);
        },

        onPeriodChange: function (oEvent) {
            this._loadDashboardData();
        },

        onRefresh: function () {
            this._loadDashboardData();
        },

        _loadDashboardData: async function () {
            var oModel = this.getView().getModel("dashboard");
            var sPeriod = oModel.getProperty("/selectedPeriod");
            oModel.setProperty("/busy", true);

            try {
                // Load dashboard summary and trend data in parallel
                var [dashboardData, trendData] = await Promise.all([
                    this._fetchDashboardSummary(sPeriod),
                    this._fetchTrendData(sPeriod)
                ]);

                // Process and set dashboard summary
                this._processDashboardData(dashboardData);

                // Process and set trend data
                this._processTrendData(trendData);

            } catch (error) {
                MessageBox.error("Failed to load quality dashboard: " + error.message);
            } finally {
                oModel.setProperty("/busy", false);
            }
        },

        _fetchDashboardSummary: async function (sPeriod) {
            var response = await fetch("/api/quality/dashboard?days=" + sPeriod);
            if (!response.ok) {
                throw new Error("Failed to load dashboard data: " + response.statusText);
            }
            return response.json();
        },

        _fetchTrendData: async function (sPeriod) {
            var response = await fetch("/api/quality/trend?days=" + sPeriod + "&granularity=daily");
            if (!response.ok) {
                throw new Error("Failed to load trend data: " + response.statusText);
            }
            return response.json();
        },

        _processDashboardData: function (data) {
            var oModel = this.getView().getModel("dashboard");

            // Calculate period label
            var sPeriod = oModel.getProperty("/selectedPeriod");
            var sPeriodLabel = sPeriod + " Days";

            // Set summary data
            oModel.setProperty("/summary", {
                averageScore: Math.round(data.average_score || 0),
                scoreTrend: data.score_trend || 0,
                period: sPeriodLabel,
                totalAnalyzed: data.total_notifications || 0,
                avgCompleteness: Math.round(data.avg_completeness || 0),
                avgAccuracy: Math.round(data.avg_accuracy || 0),
                avgTimeliness: Math.round(data.avg_timeliness || 0),
                avgConsistency: Math.round(data.avg_consistency || 0),
                alcoaCompliance: Math.round(data.alcoa_compliance_rate || 0)
            });

            // Set distribution data
            oModel.setProperty("/distribution", {
                excellent: data.distribution?.excellent || 0,
                good: data.distribution?.good || 0,
                needsImprovement: data.distribution?.needs_improvement || 0
            });

            // Process ALCOA+ principles
            var aAlcoaPrinciples = this._getAlcoaPrinciples(data.alcoa_breakdown || {});
            oModel.setProperty("/alcoaPrinciples", aAlcoaPrinciples);

            // Process common issues
            var aIssues = (data.common_issues || []).map(function (issue) {
                return {
                    description: issue.description,
                    field: issue.field,
                    severity: issue.severity,
                    count: issue.count,
                    percentage: Math.round((issue.count / (data.total_notifications || 1)) * 100)
                };
            });
            oModel.setProperty("/commonIssues", aIssues);

            // Process recommendations
            var aRecommendations = (data.recommendations || []).map(function (rec) {
                return {
                    title: rec.title,
                    description: rec.description,
                    priority: rec.priority,
                    impact: rec.expected_impact
                };
            });
            oModel.setProperty("/recommendations", aRecommendations);
        },

        _getAlcoaPrinciples: function (breakdown) {
            var aPrinciples = [
                {
                    principle: "Attributable",
                    description: "Data can be traced to its source",
                    rate: breakdown.attributable || 0
                },
                {
                    principle: "Legible",
                    description: "Data is readable and understandable",
                    rate: breakdown.legible || 0
                },
                {
                    principle: "Contemporaneous",
                    description: "Data recorded at time of activity",
                    rate: breakdown.contemporaneous || 0
                },
                {
                    principle: "Original",
                    description: "Data is the first-hand record",
                    rate: breakdown.original || 0
                },
                {
                    principle: "Accurate",
                    description: "Data is correct and precise",
                    rate: breakdown.accurate || 0
                },
                {
                    principle: "Complete",
                    description: "All required data is present",
                    rate: breakdown.complete || 0
                },
                {
                    principle: "Consistent",
                    description: "Data follows established patterns",
                    rate: breakdown.consistent || 0
                },
                {
                    principle: "Enduring",
                    description: "Data is preserved properly",
                    rate: breakdown.enduring || 0
                },
                {
                    principle: "Available",
                    description: "Data is accessible when needed",
                    rate: breakdown.available || 0
                }
            ];
            return aPrinciples;
        },

        _processTrendData: function (data) {
            var oModel = this.getView().getModel("dashboard");

            // Convert trend data to chart format
            var aDataPoints = (data.data_points || []).map(function (point) {
                return {
                    label: point.date,
                    value: Math.round(point.average_score || 0)
                };
            });

            oModel.setProperty("/trend/dataPoints", aDataPoints);
        },

        onExportReport: async function () {
            var oModel = this.getView().getModel("dashboard");
            var sPeriod = oModel.getProperty("/selectedPeriod");

            BusyIndicator.show(0);

            try {
                var response = await fetch("/api/quality/export?days=" + sPeriod + "&format=csv");
                if (!response.ok) {
                    throw new Error("Export failed: " + response.statusText);
                }

                var blob = await response.blob();
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement("a");
                a.href = url;
                a.download = "quality_report_" + new Date().toISOString().split("T")[0] + ".csv";
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
        },

        onTilePress: function (oEvent) {
            // Navigate to detailed view or show more info
            MessageToast.show("Detailed quality metrics view coming soon");
        }
    });
});
