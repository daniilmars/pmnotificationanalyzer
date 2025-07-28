sap.ui.define([
    "sap/ui/core/UIComponent",
    "sap/ui/Device",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/ui/model/resource/ResourceModel"
],
function (UIComponent, Device, JSONModel, MessageBox, ResourceModel) {
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

            // --- MODIFIED BLOCK FOR MULTILINGUAL MOCK DATA ---
            // Determine which language file to load
            let sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
            if (sLanguage !== "de") {
                sLanguage = "en"; // Default to English
            }
            // Use a simple, direct path to the file
            const sMockDataPath = `./mock_data_${sLanguage}.json`;
            
            // Load the language-specific data
            const oDataModel = new JSONModel();
            this.setModel(oDataModel);
            oDataModel.loadData(sMockDataPath) // No longer need sap.ui.require.toUrl()
                .then(() => {
                    oDataModel.setProperty("/Notifications", oDataModel.getData());
                });
            // --- END OF MODIFIED BLOCK ---

            UIComponent.prototype.init.apply(this, arguments);

            const i18nModel = new ResourceModel({
                bundleName: "com.sap.pm.pmanalyzerfiori.i18n.i18n",
                supportedLocales: ["en", "de"],
                fallbackLocale: "en"
            });
            this.setModel(i18nModel, "i18n");

            this._auth0Promise = oConfigModel.loadData(sap.ui.require.toUrl("com/sap/pm/pmanalyzerfiori/config.json"))
                .then(() => this._initAuth0Client());

            this._auth0Promise.then(() => {
                this.getRouter().initialize();
            });
        },
        
        getAuth0Client: function() {
            return this._auth0Promise;
        },

        _initAuth0Client: async function () {
            // ... this function remains unchanged ...
            const oUiModel = this.getModel("ui");
            try {
                const oConfig = this.getModel("config").getData().auth0;
                
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
                    await auth0Client.handleRedirectCallback();
                    window.history.replaceState({}, document.title, window.location.pathname);
                }
                
                const isAuthenticated = await auth0Client.isAuthenticated();
                oUiModel.setProperty("/isAuthenticated", isAuthenticated);

                if (isAuthenticated) {
                    const userProfile = await auth0Client.getUser();
                    oUiModel.setProperty("/userProfile", userProfile);
                    this.getRouter().navTo("worklist", {}, true);
                } else {
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
        }
    });
});