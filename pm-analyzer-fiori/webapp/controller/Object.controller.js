sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel", // JSONModel importieren
    "sap/m/MessageToast" // MessageToast für Fehlermeldungen importieren
], function (BaseController, JSONModel, MessageToast) {
    "use strict";

    return BaseController.extend("com.sap.pm.pmanalyzerfiori.controller.Object", {

        /**
         * Wird bei der Initialisierung der View aufgerufen.
         */
        onInit: function () {
            // Ein leeres Model für die Analyseergebnisse erstellen und an die View binden.
            // Dies ermöglicht es uns, die Ergebnis-UI einfach zu aktualisieren.
            var oAnalysisModel = new JSONModel({
                score: 0,
                issues: [],
                summary: ""
            });
            this.getView().setModel(oAnalysisModel, "analysis");

            // Den Router holen und eine Funktion registrieren, die aufgerufen wird,
            // wenn die "object"-Route aufgerufen wird.
            var oRouter = this.getRouter();
            oRouter.getRoute("object").attachPatternMatched(this._onObjectMatched, this);
        },

        /**
         * Wird aufgerufen, wenn die URL zur Detailseite passt.
         * @param {sap.ui.base.Event} oEvent Das Routing-Event
         */
        _onObjectMatched: function (oEvent) {
            // Holt die ID des Objekts aus der URL (z.B. "0", "1", etc.)
            var sObjectId =  oEvent.getParameter("arguments").objectId;
            
            // Bindet die gesamte View an den Pfad des ausgewählten Objekts im Hauptmodell.
            // z.B. an "/0" für das erste Element in unserer mock_data.json.
            // Dadurch werden alle Felder wie {Description}, {LongText} automatisch gefüllt.
            this.getView().bindElement({
                path: "/" + sObjectId
            });

            // Stellt sicher, dass der Ergebnisbereich bei jeder neuen Navigation ausgeblendet ist.
            this.getView().byId("resultsPanel").setVisible(false);
        },

        /**
         * Wird aufgerufen, wenn der "Zurück"-Button geklickt wird.
         * Navigiert zur vorherigen Seite in der Browser-Historie.
         */
        onNavBack: function () {
            var oHistory = sap.ui.core.routing.History.getInstance();
            var sPreviousHash = oHistory.getPreviousHash();

            if (sPreviousHash !== undefined) {
                window.history.go(-1);
            } else {
                this.getRouter().navTo("worklist", {}, true);
            }
        },

        /**
         * Wird beim Klick auf den "Qualität analysieren"-Button aufgerufen.
         */
        onAnalyzePress: async function () {
            const oView = this.getView();
            const oResultsPanel = oView.byId("resultsPanel");
            const oSpinner = oView.byId("loadingSpinner");
            const oAnalyzeButton = oView.byId("analyzeButton");

            // Daten aus den UI-Elementen der Detailseite sammeln
            const sLongText = oView.byId("longText").getValue();
            const sActivities = oView.byId("activitiesText").getValue();
            
            // Die Texte für die Analyse kombinieren
            const sFullText = sLongText + "\n\nMaßnahmen:\n" + sActivities;

            // UI für den Ladezustand vorbereiten
            oAnalyzeButton.setEnabled(false);
            oResultsPanel.setVisible(true);
            oSpinner.setVisible(true);

            try {
                // API-Aufruf an das lokale Python-Backend (läuft auf Port 8000)
                const response = await fetch("http://localhost:8000/analyze", {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ text: sFullText }),
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || "Serverfehler");
                }

                const result = await response.json();
                
                // Das "analysis"-Model mit den neuen Daten vom Backend aktualisieren.
                // Die UI-Elemente, die an dieses Model gebunden sind, aktualisieren sich automatisch.
                const oAnalysisModel = this.getView().getModel("analysis");
                oAnalysisModel.setData(result);

                // Hilfsfunktion aufrufen, um den Score-Balken einzufärben
                this._updateScoreIndicator(result.score);

            } catch (error) {
                console.error("Analyse-Fehler:", error);
                let displayMessage = 'Ein unerwarteter Fehler ist aufgetreten.';
                if (error.message.includes('Failed to fetch')) {
                    displayMessage = 'Netzwerkfehler: Konnte das Backend nicht erreichen. Läuft der Python-Server?';
                } else {
                    displayMessage = error.message;
                }
                MessageToast.show(displayMessage);
                // Bei einem Fehler den Ergebnisbereich wieder ausblenden
                oResultsPanel.setVisible(false);
            } finally {
                // Ladezustand in jedem Fall beenden
                oSpinner.setVisible(false);
                oAnalyzeButton.setEnabled(true);
            }
        },

        /**
         * Hilfsfunktion zum Einfärben des Score-Balkens je nach Wert.
         * @param {int} score Der erhaltene Qualitäts-Score
         */
        _updateScoreIndicator: function(score) {
            const oScoreIndicator = this.getView().byId("scoreIndicator");
            oScoreIndicator.setPercentValue(score);
            oScoreIndicator.setDisplayValue(score + "/100");

            if (score >= 90) {
                oScoreIndicator.setState(sap.ui.core.ValueState.Success); // Grün
            } else if (score >= 70) {
                oScoreIndicator.setState(sap.ui.core.ValueState.Warning); // Gelb
            } else {
                oScoreIndicator.setState(sap.ui.core.ValueState.Error); // Rot
            }
        }
    });
});
