sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/ui/core/routing/History"
], function (Controller, JSONModel, MessageBox, History) {
    "use strict";
 
    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.Object", {
        
        onInit: function () {
            const oAnalysisModel = new JSONModel({
                busy: false,
                resultsVisible: false,
                score: 0,
                problems: [],
                summary: ""
            });
            this.getView().setModel(oAnalysisModel, "analysis");

            const oRouter = this.getOwnerComponent().getRouter();
            oRouter.getRoute("object").attachPatternMatched(this._onObjectMatched, this);
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
                    this.getView().bindElement({ path: `/Notifications/${iObjectIndex}` });
                }
                // Reset wizard to the first step whenever a new object is matched
                this.byId("analysisWizard").discardProgress(this.byId("dataStep"));
            }); 
        },

        onNavBack: function () {
            const oHistory = History.getInstance();
            const sPreviousHash = oHistory.getPreviousHash();

            if (sPreviousHash !== undefined) {
                window.history.go(-1);
            } else {
                const oRouter = this.getOwnerComponent().getRouter();
                oRouter.navTo("worklist", {}, true);
            }
        },
        
        formatProblems: function(aProblems) {
            if (!aProblems || aProblems.length === 0) {
                const oResourceBundle = this.getOwnerComponent().getModel("i18n").getResourceBundle();
                return oResourceBundle.getText("noProblemsFound");
            }
            return aProblems.join("\n\n"); 
        },
        
        // Handles moving between wizard steps
        validateAndNext: function() {
            const oView = this.getView();
            const sLongText = oView.byId("longText").getValue();
            
            if (!sLongText || sLongText.trim() === "") {
                MessageBox.error("Please provide a long text before proceeding.");
                return;
            }
            
            this.byId("analysisWizard").nextStep();
            this._triggerAnalysis(); // Automatically trigger analysis on next step
        },
 
        // Renamed and now called by the wizard handler
        _triggerAnalysis: async function () {
            const oView = this.getView();
            const oAnalysisModel = oView.getModel("analysis");
            const oNotification = oView.getBindingContext().getObject();

            // We use getValue() because the view has editable TextAreas in the first step
            const sHeaderText = `Functional Location: ${oNotification.FunctionalLocation}\nEquipment: ${oNotification.EquipmentNumber}\nDescription: ${oNotification.Description}`;
            const sLongText = oView.byId("longText").getValue();
            const sActivities = oView.byId("activitiesText").getValue();
            const sTextToAnalyze = `${sHeaderText}\n\nLong Text:\n${sLongText}\n\nActivities:\n${sActivities}`;
 
            this._setAnalysisState(true);
 
            try {
                const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                const response = await this._callAnalysisApi(sTextToAnalyze, sLanguage);
                const result = await response.json();
                
                if (result.error) {
                    throw new Error(result.error.message || "An unknown error occurred during analysis.");
                }

                this._displayAnalysisResult(result);
 
            } catch (error) {
                MessageBox.error(error.message);
            } finally {
                this._setAnalysisState(false);
            }
        },

        _callAnalysisApi: async function(sText, sLanguage) {
            const response = await fetch("/api/analyze", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ text: sText, language: sLanguage })
            });

            if (!response.ok) {
                let errorMessage = `Server error: ${response.status} ${response.statusText}`;
                try {
                    const errorData = await response.json();
                    if (errorData.error && errorData.error.message) {
                        errorMessage = errorData.error.message;
                    }
                } catch (e) {
                    // Could not parse error response
                }
                throw new Error(errorMessage);
            }
            return response;
        },

        _setAnalysisState: function(bIsBusy) {
            const oAnalysisModel = this.getView().getModel("analysis");
            oAnalysisModel.setProperty("/busy", bIsBusy);
            if (bIsBusy) {
                oAnalysisModel.setProperty("/resultsVisible", false);
            }
        },

        _displayAnalysisResult: function(oResult) {
            const oAnalysisModel = this.getView().getModel("analysis");
            oAnalysisModel.setProperty("/score", oResult.score);
            oAnalysisModel.setProperty("/problems", oResult.problems);
            oAnalysisModel.setProperty("/summary", oResult.summary);
            oAnalysisModel.setProperty("/resultsVisible", true);
            this._updateScoreIndicator(oResult.score);
        },

        _updateScoreIndicator: function(score) {
            const oScoreGauge = this.getView().byId("scoreGauge");
            if (!oScoreGauge) return;
            
            let scoreColor = sap.m.ValueColor.Error;

            if (score > 70) {
                scoreColor = sap.m.ValueColor.Good;
            } else if (score >= 50) {
                scoreColor = sap.m.ValueColor.Critical;
            }

            oScoreGauge.setValueColor(scoreColor);
        }
    });
});
