sap.ui.define([
    "sap/ui/core/UIComponent",
    "sap/ui/Device",
    "sap/ui/model/json/JSONModel",
    "sap/ui/model/resource/ResourceModel"
],
function (UIComponent, Device, JSONModel, ResourceModel) {
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
            
            // --- START: CORRECTED MULTILINGUAL DATA LOADING ---
            // Determine which language file to load
            let sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
            if (sLanguage !== "de") {
                sLanguage = "en"; // Default to English
            }
            const sMockDataPath = sap.ui.require.toUrl(`com/sap/pm/pmanalyzerfiori/mock_data_${sLanguage}.json`);
            
            // Set the main data model by loading the correct JSON file
            const oModel = new JSONModel(sMockDataPath);
            this.setModel(oModel);

            // Wait for the data to be loaded before initializing the router
            oModel.dataLoaded().then(() => {
                this.getRouter().initialize();
            });
            // --- END: CORRECTED MULTILINGUAL DATA LOADING ---

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
        }
    });
});