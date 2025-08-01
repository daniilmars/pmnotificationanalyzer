sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox"
], function (Controller, JSONModel, MessageBox) {
    "use strict";
 
    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.View1", {
        onInit: function () {
            // Model for analysis results
            const oAnalysisModel = new JSONModel({
                busy: false,
                resultsVisible: false,
                score: 0,
                problems: [],
                summary: ""
            });
            this.getView().setModel(oAnalysisModel, "analysis");
            
            // The main UI model (with auth state) is now managed globally by Component.js
            // and is available automatically in this view.
        },
 
        // Removed onLogin as login is no longer required
        // Removed onLogout as logout is no longer required
 
        onAnalyzePress: async function () {
            const oComponent = this.getOwnerComponent();
            const oView = this.getView();
            const oAnalysisModel = oView.getModel("analysis");
            const sTextToAnalyze = oView.byId("pmTextInput").getValue();
 
            if (!sTextToAnalyze.trim()) {
                MessageBox.warning("Please enter text to analyze.");
                return;
            }
 
            oAnalysisModel.setProperty("/busy", true);
            oAnalysisModel.setProperty("/resultsVisible", false);
 
            try {
                // No auth0Client needed anymore
                const response = await this._callAnalysisApi(sTextToAnalyze);
 
                const { score, problems, summary } = await response.json();
                oAnalysisModel.setProperty("/score", score);
                oAnalysisModel.setProperty("/problems", problems);
                oAnalysisModel.setProperty("/summary", summary);
                oAnalysisModel.setProperty("/resultsVisible", true);

                this._updateScoreIndicator(score);
 
            } catch (error) {
                // Removed specific error handling for login_required/consent_required
                MessageBox.error(error.message);
            } finally {
                oAnalysisModel.setProperty("/busy", false);
            }
        },

        /**
         * Calls the backend API to analyze the text.
         * @param {string} sText The text to analyze.
         * @returns {Promise<Response>} A promise that resolves with the fetch response.
         * @private
         */
        _callAnalysisApi: async function(sText) {
            // No accessToken needed anymore
            const response = await fetch("/api/analyze", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                    // Removed Authorization header as no authentication is needed
                },
                body: JSON.stringify({ text: sText })
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

        /**
         * Helper function to color the score indicator based on the value.
         * @param {int} score The quality score received from the backend.
         */
        _updateScoreIndicator: function(score) {
            const oScoreIndicator = this.getView().byId("scoreIndicator");
            if (score >= 90) {
                oScoreIndicator.setState(sap.ui.core.ValueState.Success); // Green
            } else if (score >= 70) {
                oScoreIndicator.setState(sap.ui.core.ValueState.Warning); // Yellow
            } else {
                oScoreIndicator.setState(sap.ui.core.ValueState.Error); // Red
            }
        }
    });
});
