sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "../model/formatter",
    "sap/ui/core/routing/History",
    "sap/m/MessageBox"
], function (BaseController, JSONModel, formatter, History, MessageBox) {
    "use strict";

    return BaseController.extend("com.sap.pm.pmanalyzerfiori.controller.Object", {

        formatter: formatter,

        onInit: function () {
            this.getView().setModel(new JSONModel(), "timeline");
            this.getView().setModel(new JSONModel({
                busy: false,
                score: 0,
                problems: [],
                summary: ""
            }), "analysis");

            const oRouter = this.getRouter();
            oRouter.getRoute("object").attachPatternMatched(this._onObjectMatched, this);
        },

        onNavBack: function () {
            const oHistory = History.getInstance();
            const sPreviousHash = oHistory.getPreviousHash();

            if (sPreviousHash !== undefined) {
                window.history.go(-1);
            } else {
                this.getRouter().navTo("worklist", {}, true);
            }
        },

        _onObjectMatched: function (oEvent) {
            const sNotificationId = oEvent.getParameter("arguments").notificationId;
            const oModel = this.getOwnerComponent().getModel();

            oModel.dataLoaded().then(() => {
                const aNotifications = oModel.getProperty("/Notifications") || [];
                const iObjectIndex = aNotifications.findIndex(
                    (notif) => notif.NotificationId === sNotificationId
                );

                if (iObjectIndex !== -1) {
                    const sObjectPath = `/Notifications/${iObjectIndex}`;
                    this.getView().bindElement({ path: sObjectPath });
                    const oNotification = aNotifications[iObjectIndex];
                    this._buildTimelines(oNotification);
                    this._triggerAnalysis(oNotification.LongText); // Initial analysis
                } else {
                    this.getRouter().navTo("worklist");
                }
            });
        },

        _buildTimelines: function (oNotification) {
            const oTimelineModel = this.getView().getModel("timeline");
            
            const sNotifStatus = oNotification.SystemStatus;
            const oNotifTimelineData = this._createTimelineData(
                ["OSDN", "REL", "NOCO"],
                ["Outstanding", "Released", "Closed"],
                sNotifStatus
            );
            oTimelineModel.setProperty("/notification", oNotifTimelineData);

            if (oNotification.WorkOrder) {
                const sOrderStatus = oNotification.WorkOrder.SystemStatus;
                const oOrderTimelineData = this._createTimelineData(
                    ["CRTD", "REL", "TECO", "CLSD"],
                    ["Created", "Released", "Technically Completed", "Business Closed"],
                    sOrderStatus
                );
                oTimelineModel.setProperty("/workOrder", oOrderTimelineData);
            } else {
                oTimelineModel.setProperty("/workOrder", []);
            }
        },

        _createTimelineData: function (aStatusIds, aStatusNames, sCurrentStatusId) {
            const aSteps = [];
            const iCurrentIndex = aStatusIds.indexOf(sCurrentStatusId);

            aStatusIds.forEach((sId, i) => {
                let sStatusType = "future";
                if (i < iCurrentIndex) {
                    sStatusType = "completed";
                } else if (i === iCurrentIndex) {
                    sStatusType = "current";
                }
                aSteps.push({ text: aStatusNames[i], status: sStatusType });
            });
            return aSteps;
        },

        onReanalyze: function () {
            const sLongText = this.getView().byId("longTextForAnalysis").getValue();
            this._triggerAnalysis(sLongText);
        },

        _triggerAnalysis: async function (sTextToAnalyze) {
            const oAnalysisModel = this.getView().getModel("analysis");
            oAnalysisModel.setProperty("/busy", true);

            try {
                const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                const response = await fetch("/api/analyze", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: sTextToAnalyze, language: sLanguage })
                });

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const result = await response.json();
                oAnalysisModel.setProperty("/score", result.score);
                oAnalysisModel.setProperty("/problems", result.problems);
                oAnalysisModel.setProperty("/summary", result.summary);

            } catch (error) {
                MessageBox.error(error.message);
            } finally {
                oAnalysisModel.setProperty("/busy", false);
            }
        }
    });
});
