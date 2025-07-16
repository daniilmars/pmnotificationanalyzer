sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageToast"
], function (BaseController, JSONModel, MessageToast) {
    "use strict";

    return BaseController.extend("com.sap.pm.pmanalyzerfiori.controller.Object", {

        onInit: function () {
            this.getView().setModel(new JSONModel({ score: 0, issues: [], summary: "" }), "analysis");
            this.getView().setModel(new JSONModel({
                editMode: false,
                analysisDone: false
            }), "view");

            this.getRouter().getRoute("object").attachPatternMatched(this._onObjectMatched, this);
        },

        _onObjectMatched: function (oEvent) {
            var sCaseId =  oEvent.getParameter("arguments").caseId;
            this.getView().bindElement({ path: "/" + sCaseId });

            this.getView().getModel("view").setData({ editMode: false, analysisDone: false });
            this.getView().byId("resultsPanel").setVisible(false);
            this.getView().byId("uploadCollection").destroyItems();
        },

        onNavBack: function () {
            window.history.go(-1);
        },

        onAnalyzePress: async function () {
            const oView = this.getView();
            this.setBusy(true);

            // --- Payload manuell und sicher erstellen ---
            const oBindingContext = oView.getBindingContext();
            
            const oPayload = {
                Notification: {
                    NotificationId: oBindingContext.getProperty("Notification/NotificationId"),
                    NotificationType: oBindingContext.getProperty("Notification/NotificationType"),
                    Description: oBindingContext.getProperty("Notification/Description"),
                    LongText: oView.byId("longText").getValue()
                },
                Confirmation: {
                    Activities: oView.byId("activitiesText").getValue()
                }
            };

            const oOrderData = oBindingContext.getProperty("Order");
            if (oOrderData) {
                oPayload.Order = {
                    OrderId: oBindingContext.getProperty("Order/OrderId"),
                    Operations: oBindingContext.getProperty("Order/Operations"),
                    Components: oBindingContext.getProperty("Order/Components")
                };
            }

            const oUploadCollection = oView.byId("uploadCollection");
            const aItems = oUploadCollection.getItems();
            if (aItems.length > 0) {
                try {
                    const fileContent = await this._readFile(aItems[0].getFileObject());
                    oPayload.ExternalProtocol = fileContent;
                } catch (e) {
                    MessageToast.show("Fehler beim Lesen der Protokolldatei.");
                    this.setBusy(false);
                    return;
                }
            }
            
            // --- DEBUGGING: Den finalen Payload in der Browser-Konsole ausgeben ---
            console.log("Sende folgendes Datenpaket an das Backend:", JSON.stringify(oPayload, null, 2));

            // Analyse durchführen
            this._executeAnalysis(oPayload);
        },

        _executeAnalysis: async function(oPayload) {
            const oView = this.getView();
            const oResultsPanel = oView.byId("resultsPanel");

            oResultsPanel.setVisible(true);

            try {
                const response = await fetch("http://localhost:8000/analyze", {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(oPayload)
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || "Serverfehler");
                }

                const result = await response.json();
                oView.getModel("analysis").setData(result);
                this._updateScoreIndicator(result.score);

                oView.getModel("view").setProperty("/editMode", true);
                oView.getModel("view").setProperty("/analysisDone", true);

            } catch (error) {
                MessageToast.show("Fehler bei der Analyse: " + error.message);
                oResultsPanel.setVisible(false);
            } finally {
                this.setBusy(false);
            }
        },

        setBusy: function(bBusy) {
            this.getView().byId("analyzeButton").setEnabled(!bBusy);
            this.getView().byId("reanalyzeButton").setEnabled(!bBusy);
            this.getView().byId("loadingSpinner").setVisible(bBusy);
        },

        _updateScoreIndicator: function (score) {
            const oIndicator = this.getView().byId("scoreIndicator");
            oIndicator.setPercentValue(score);
            oIndicator.setDisplayValue(score + "/100");
            if (score >= 70) {
                oIndicator.setState(sap.ui.core.ValueState.Success);
            } else if (score >= 50) {
                oIndicator.setState(sap.ui.core.ValueState.Warning);
            } else {
                oIndicator.setState(sap.ui.core.ValueState.Error);
            }
        },

        _readFile: function(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = () => reject(reader.error);
                reader.readAsText(file);
            });
        },

        onFileChange: function(oEvent) {
            const oUploadCollection = oEvent.getSource();
            if (oUploadCollection.getItems().length > 1) {
                oUploadCollection.removeItem(oUploadCollection.getItems()[0]);
            }
        },
        onUploadComplete: function(oEvent) {},
        onFileDeleted: function(oEvent) {}
    });
});
