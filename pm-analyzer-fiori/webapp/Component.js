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
            // Call the base UIComponent's init method
            UIComponent.prototype.init.apply(this, arguments);

            // Set the device model
            this.setModel(new JSONModel(Device), "device");

            // Check for stored language and set it
            const sStoredLanguage = localStorage.getItem("appLanguage");
            if (sStoredLanguage) {
                sap.ui.getCore().getConfiguration().setLanguage(sStoredLanguage);
            }

            // Initialize the UI model for authentication state and busy indicator
            const oUiModel = new JSONModel({
                isAuthenticated: false,
                userProfile: null,
                isBusy: true // Set to true initially to indicate loading/auth process
            });
            this.setModel(oUiModel, "ui");

            // Initialize the i18n model (if not already done via manifest.json)
            // Note: If i18n model is defined in manifest.json, this block can be removed
            // as the framework will instantiate it. However, keeping it here for explicit control.
            const i18nModel = new ResourceModel({
                bundleName: "com.sap.pm.pmanalyzerfiori.i18n.i18n",
                supportedLocales: ["en", "de"],
                fallbackLocale: "en"
            });
            this.setModel(i18nModel, "i18n");

            // Load config.json and initialize Auth0 client
            const oConfigModel = new JSONModel();
            this.setModel(oConfigModel, "config");

            // Store the Auth0 initialization promise
            this._auth0Promise = oConfigModel.loadData(sap.ui.require.toUrl("com/sap/pm/pmanalyzerfiori/config.json"))
                .then(() => this._initAuth0Client())
                .catch(error => {
                    console.error("Failed to load config.json or initialize Auth0:", error);
                    MessageBox.error("Application configuration error. Please contact support.");
                    oUiModel.setProperty("/isBusy", false); // Stop busy indicator on error
                    throw error; // Propagate error
                });

            // Initialize the router after Auth0 client is ready
            this._auth0Promise.then(() => {
                // The default model (notificationsMockData) is now handled by manifest.json
                // and will be preloaded. We just need to ensure the router initializes
                // after authentication state is determined.
                this.getRouter().initialize();
            });
        },

        /**
         * Returns the Auth0 client instance after it has been initialized.
         * @returns {Promise<object>} A promise that resolves with the Auth0 client instance.
         */
        getAuth0Client: function() {
            return this._auth0Promise;
        },

        /**
         * Initializes the Auth0 client and handles authentication redirect.
         * Updates the UI model with authentication status and user profile.
         * @private
         * @returns {Promise<object>} A promise that resolves with the Auth0 client instance.
         */
        _initAuth0Client: async function () {
            const oUiModel = this.getModel("ui");
            try {
                const oConfig = this.getModel("config").getData().auth0;

                // Ensure 'auth0' global object is available (from Auth0 SDK script)
                if (typeof auth0 === 'undefined') {
                    throw new Error("Auth0 SDK not loaded. Please ensure the Auth0 script is included in index.html.");
                }
                
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
                    // Handle the redirect callback from Auth0
                    await auth0Client.handleRedirectCallback();
                    // Clean the URL to remove Auth0 parameters
                    window.history.replaceState({}, document.title, window.location.pathname);
                }
                
                // Check authentication status
                const isAuthenticated = await auth0Client.isAuthenticated();
                oUiModel.setProperty("/isAuthenticated", isAuthenticated);

                if (isAuthenticated) {
                    const userProfile = await auth0Client.getUser();
                    oUiModel.setProperty("/userProfile", userProfile);
                    // Navigate to worklist if authenticated
                    this.getRouter().navTo("worklist", {}, true);
                } else {
                    // Navigate to login page if not authenticated
                    this.getRouter().navTo("login", {}, true);
                }
                return auth0Client;
            } catch (err) {
                console.error("A critical error occurred during authentication setup:", err);
                MessageBox.error("Could not initialize the application due to an authentication error. Please check browser console for details.");
                throw err; // Re-throw to propagate the error to the calling promise chain
            } finally {
                oUiModel.setProperty("/isBusy", false); // Always set busy to false when auth process completes
            }
        }
    });
});
