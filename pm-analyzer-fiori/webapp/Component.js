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

            // Initialize the UI model (simplified, no longer tracking authentication state)
            const oUiModel = new JSONModel({
                isBusy: false // No longer busy due to auth, just general app loading
            });
            this.setModel(oUiModel, "ui");

            // Initialize the i18n model
            const i18nModel = new ResourceModel({
                bundleName: "com.sap.pm.pmanalyzerfiori.i18n.i18n",
                supportedLocales: ["en", "de"],
                fallbackLocale: "en"
            });
            this.setModel(i18nModel, "i18n");

            // Initialize the router directly, as no authentication is needed
            this.getRouter().initialize();

            // No Auth0 client initialization or handling needed
        }
    });
});
