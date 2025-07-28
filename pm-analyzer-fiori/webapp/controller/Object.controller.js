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
 
        onAnalyzePress: async function () {
            const oComponent = this.getOwnerComponent();
            const oView = this.getView();
            const oAnalysisModel = oView.getModel("analysis");
            const oNotification = oView.getBindingContext().getObject();

            const sHeaderText = `Functional Location: ${oNotification.FunctionalLocation}\nEquipment: ${oNotification.EquipmentNumber}\nDescription: ${oNotification.Description}`;
            const sLongText = oView.byId("longText").getValue();
            const sActivities = oView.byId("activitiesText").getValue();
            const sTextToAnalyze = `${sHeaderText}\n\nLong Text:\n${sLongText}\n\nActivities:\n${sActivities}`;
 
            if (!sTextToAnalyze.trim()) {
                MessageBox.warning("Please enter text to analyze.");
                return;
            }
            
            this._setAnalysisState(true);
 
            try {
                // Get the current language to send to the backend
                const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                const auth0Client = await oComponent.getAuth0Client();

                // Pass the language to the API call function
                const response = await this._callAnalysisApi(sTextToAnalyze, auth0Client, sLanguage);
                const result = await response.json();
                this._displayAnalysisResult(result);
 
            } catch (error) {
                MessageBox.error(error.message);
            } finally {
                this._setAnalysisState(false);
            }
        },

        onLogout: async function () {
            const oComponent = this.getOwnerComponent();
            const auth0Client = await oComponent.getAuth0Client();
            auth0Client.logout({
                logoutParams: {
                    returnTo: window.location.origin + window.location.pathname
                }
            });
        },

        _callAnalysisApi: async function(sText, auth0Client, sLanguage) {
            const accessToken = await auth0Client.getTokenSilently();
 
            const response = await fetch("/api/analyze", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${accessToken}`
                },
                // Add the language to the request body
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
                    console.error("Could not parse error response as JSON.", e);
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
            const oScoreIndicator = this.getView().byId("scoreIndicator");
            if (score >= 90) {
                oScoreIndicator.setState(sap.ui.core.ValueState.Success);
            } else if (score >= 70) {
                oScoreIndicator.setState(sap.ui.core.ValueState.Warning);
            } else {
                oScoreIndicator.setState(sap.ui.core.ValueState.Error);
            }
        }
    });
});