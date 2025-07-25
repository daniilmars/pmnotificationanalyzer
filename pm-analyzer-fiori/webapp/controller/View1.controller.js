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
 
        onLogin: async function () {
            const oComponent = this.getOwnerComponent();
            const auth0Client = await oComponent.getAuth0Client();
            await auth0Client.loginWithRedirect();
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
                const auth0Client = await oComponent.getAuth0Client();
                const response = await this._callAnalysisApi(sTextToAnalyze, auth0Client);
 
                const { score, problems, summary } = await response.json();
                oAnalysisModel.setProperty("/score", score);
                oAnalysisModel.setProperty("/problems", problems);
                oAnalysisModel.setProperty("/summary", summary);
                oAnalysisModel.setProperty("/resultsVisible", true);

                this._updateScoreIndicator(score);
 
            } catch (error) {
                if (error.error === 'login_required' || error.error === 'consent_required') {
                    // If login is required, redirect the user and stop further execution.
                    const auth0Client = await oComponent.getAuth0Client();
                    await auth0Client.loginWithRedirect();
                    return;
                }
                // For all other types of errors, display a message to the user.
                MessageBox.error(error.message);
            } finally {
                oAnalysisModel.setProperty("/busy", false);
            }
        },

        /**
         * Calls the backend API to analyze the text.
         * @param {string} sText The text to analyze.
         * @param {object} auth0Client The initialized Auth0 client instance.
         * @returns {Promise<Response>} A promise that resolves with the fetch response.
         * @private
         */
        _callAnalysisApi: async function(sText, auth0Client) {
            const accessToken = await auth0Client.getTokenSilently();
 
            const response = await fetch("/api/analyze", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${accessToken}`
                },
                body: JSON.stringify({ text: sText })
            });

            if (!response.ok) {
                let errorMessage = `Server error: ${response.status} ${response.statusText}`;
                try {
                    // Try to parse a structured error from the backend
                    const errorData = await response.json();
                    if (errorData.error && errorData.error.message) {
                        errorMessage = errorData.error.message;
                    }
                } catch (e) {
                    // This catch block handles the "Unexpected end of JSON input" error
                    // if the response body is empty or not valid JSON.
                    // We will proceed with the generic server error message.
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
            // The percentValue and displayValue are already bound to the model.
            // We only need to set the color state.
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