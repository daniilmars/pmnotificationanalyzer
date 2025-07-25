sap.ui.define([
    "sap/ui/core/UIComponent",
    "sap/ui/Device",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox"
],
function (UIComponent, Device, JSONModel, MessageBox) {
    "use strict";

    return UIComponent.extend("com.sap.pm.pmanalyzerfiori.Component", {
        metadata: {
            manifest: "json"
        },

        init: function () {
            const sStoredLanguage = localStorage.getItem("appLanguage");
            if (sStoredLanguage) {
                sap.ui.getCore().getConfiguration().setLanguage(sStoredLanguage);
            }

            const oUiModel = new JSONModel({
                isAuthenticated: false,
                userProfile: null,
                isBusy: true
            });
            this.setModel(oUiModel, "ui");

            const oConfigModel = new JSONModel();
            this.setModel(oConfigModel, "config");

            const oDataModel = new JSONModel();
            this.setModel(oDataModel);
            oDataModel.loadData(sap.ui.require.toUrl("com/sap/pm/pmanalyzerfiori/mock_data.json"))
                .then(() => {
                    oDataModel.setProperty("/Notifications", oDataModel.getData());
                });

            UIComponent.prototype.init.apply(this, arguments);

            // The promise now simply loads the config and initializes the client
            this._auth0Promise = oConfigModel.loadData(sap.ui.require.toUrl("com/sap/pm/pmanalyzerfiori/config.json"))
                .then(() => this._initAuth0Client());

            // The router is initialized after the auth process is complete
            this._auth0Promise.then(() => {
                this.getRouter().initialize();
            });
        },
        
        getAuth0Client: function() {
            return this._auth0Promise;
        },

        _initAuth0Client: async function () {
            const oUiModel = this.getModel("ui");
            try {
                console.log("DEBUG: 1. Starting _initAuth0Client...");
                const oConfig = this.getModel("config").getData().auth0;
                console.log("DEBUG: 2. Auth0 config loaded:", oConfig);

                console.log("DEBUG: 3. Calling createAuth0Client...");
                // 'auth0' is now globally available from index.html
                const auth0Client = await auth0.createAuth0Client({
                    domain: oConfig.domain,
                    clientId: oConfig.clientId,
                    authorizationParams: {
                        audience: oConfig.audience,
                        redirect_uri: window.location.origin + window.location.pathname
                    }
                });
                console.log("DEBUG: 4. Auth0 client object created:", auth0Client);

                const query = window.location.search;
                if (query.includes("code=") && query.includes("state=")) {
                    console.log("DEBUG: 5a. Handling redirect callback...");
                    await auth0Client.handleRedirectCallback();
                    window.history.replaceState({}, document.title, window.location.pathname);
                    console.log("DEBUG: 5b. Redirect callback handled.");
                }
                
                console.log("DEBUG: 6. Calling auth0Client.isAuthenticated()...");
                const isAuthenticated = await auth0Client.isAuthenticated();
                console.log("DEBUG: 7. isAuthenticated() returned:", isAuthenticated); // This is the most important log

                oUiModel.setProperty("/isAuthenticated", isAuthenticated);

                if (isAuthenticated) {
                    console.log("DEBUG: 8a. User is authenticated, getting profile...");
                    const userProfile = await auth0Client.getUser();
                    oUiModel.setProperty("/userProfile", userProfile);
                    this.getRouter().navTo("worklist", {}, true);
                } else {
                    console.log("DEBUG: 8b. User is NOT authenticated, navigating to login.");
                    this.getRouter().navTo("login", {}, true);
                }
                return auth0Client;
            } catch (err) {
                console.error("A critical error occurred during authentication setup.", err);
                MessageBox.error("Could not initialize the application due to an authentication error.");
                throw err;
            } finally {
                oUiModel.setProperty("/isBusy", false);
            }
        },
    
    });
});