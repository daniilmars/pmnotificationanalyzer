sap.ui.define([
    "sap/ui/core/UIComponent",
    "sap/ui/Device",
    "sap/ui/dom/includeScript",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox"
],
function (UIComponent, Device, includeScript, JSONModel, MessageBox) {
    "use strict";

    return UIComponent.extend("com.sap.pm.pmanalyzerfiori.Component", {
        metadata: {
            manifest: "json"
        },

        init: function () {
            // Create a model for the application's UI state and user profile
            const oUiModel = new JSONModel({
                isAuthenticated: false,
                userProfile: null,
                isBusy: true // Start in a busy state until auth is checked
            });
            this.setModel(oUiModel, "ui");

            const oConfigModel = new JSONModel();
            this.setModel(oConfigModel, "config");

            // Set the main data model with mock data
            const oDataModel = new JSONModel();
            this.setModel(oDataModel); // Set model immediately
            oDataModel.loadData(sap.ui.require.toUrl("com/sap/pm/pmanalyzerfiori/mock_data.json"))
                .then((oData) => {
                    oDataModel.setProperty("/Notifications", oDataModel.getData());
                });

            // call the base component's init function AFTER setting up the models
            UIComponent.prototype.init.apply(this, arguments);

            // enable routing
            this.getRouter().initialize();

            // Load config and then initialize Auth0. We wrap this in a promise
            // that the Component will hold.
            this._auth0Promise = oConfigModel.loadData(sap.ui.require.toUrl("com/sap/pm/pmanalyzerfiori/config.json"))
                .then(() => {
                    return new Promise((resolve, reject) => {
                        includeScript({
                            url: "https://unpkg.com/@auth0/auth0-spa-js@2.1.3/dist/auth0-spa-js.production.js"
                        })
                        .then(() => this._initAuth0Client())
                        .then(resolve)
                        .catch(reject);
                    });
                });
        },
        
        getAuth0Client: function() {
            return this._auth0Promise;
        },

        _initAuth0Client: async function () {
            const oUiModel = this.getModel("ui");
            try {
                const oConfig = this.getModel("config").getData().auth0;

                // eslint-disable-next-line no-undef
                const auth0Client = await auth0.createAuth0Client({
                    domain: oConfig.domain,
                    clientId: oConfig.clientId,
                    authorizationParams: {
                        audience: oConfig.audience,
                        redirect_uri: window.location.origin + window.location.pathname
                    }
                });

                const query = window.location.search;
                if (query.includes("code=") && query.includes("state=")) {
                    try {
                        await auth0Client.handleRedirectCallback();
                    } catch(e) {
                        console.error("Error during handleRedirectCallback", e);
                        MessageBox.error("An error occurred during the login process. Please try logging in again.", {
                            title: "Authentication Error"
                        });
                    }
                    window.history.replaceState({}, document.title, window.location.pathname);
                }
                
                // Update the UI model with the authentication state and user profile
                const isAuthenticated = await auth0Client.isAuthenticated();
                oUiModel.setProperty("/isAuthenticated", isAuthenticated);
                if (isAuthenticated) {
                    const userProfile = await auth0Client.getUser();
                    oUiModel.setProperty("/userProfile", userProfile);
                    // *** NEW: Navigate to worklist if authenticated ***
                    this.getRouter().navTo("worklist", {}, true);
                } else {
                    // *** NEW: Navigate to login page if not authenticated ***
                    this.getRouter().navTo("login", {}, true);
                }

                return auth0Client;
            } catch (err) {
                console.error("A critical error occurred during authentication setup.", err);
                MessageBox.error("Could not initialize the application due to an authentication error.");
                throw err; // Re-throw to reject the main promise
            } finally {
                // This block guarantees the busy indicator is always removed.
                oUiModel.setProperty("/isBusy", false);
            }
        }
    });
});