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

            // --- START: NEW DATA MODEL INITIALIZATION ---
            // Explicitly create and set the main data model
            var oModel = new JSONModel();
            this.setModel(oModel); // Set as the default model

            // Load the mock data into the model
            var sMockDataPath = sap.ui.require.toUrl("com/sap/pm/pmanalyzerfiori/mock_data_en.json");
            oModel.loadData(sMockDataPath);
            // --- END: NEW DATA MODEL INITIALIZATION ---


            // Check for stored language and set it
            const sStoredLanguage = localStorage.getItem("appLanguage");
            if (sStoredLanguage) {
                sap.ui.getCore().getConfiguration().setLanguage(sStoredLanguage);
            }

            // Initialize the UI model
            const oUiModel = new JSONModel({
                isBusy: false
            });
            this.setModel(oUiModel, "ui");

            // Initialize the i18n model
            const i18nModel = new ResourceModel({
                bundleName: "com.sap.pm.pmanalyzerfiori.i18n.i18n",
                supportedLocales: ["en", "de"],
                fallbackLocale: "en"
            });
            this.setModel(i18nModel, "i18n");

            // Initialize the router
            this.getRouter().initialize();
        }
    });
});
