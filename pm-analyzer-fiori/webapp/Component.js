sap.ui.define([
    "sap/ui/core/UIComponent",
    "sap/ui/Device",
    "sap/ui/model/json/JSONModel"
],
function (UIComponent, Device, JSONModel) {
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

            // Check for stored language first and set it
            const sStoredLanguage = localStorage.getItem("appLanguage");
            if (sStoredLanguage) {
                sap.ui.getCore().getConfiguration().setLanguage(sStoredLanguage);
            }

            // Determine which language file to load based on the potentially updated language
            let sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
            if (sLanguage !== "de") {
                sLanguage = "en"; // Default to English
            }
            const sMockDataPath = sap.ui.require.toUrl(`com/sap/pm/pmanalyzerfiori/mock_data_${sLanguage}.json`);
            
            // The JSON file already has the correct structure { "Notifications": [...] }
            // So we can load it directly.
            const oModel = new JSONModel(sMockDataPath);
            this.setModel(oModel);

            // Initialize the router after the model is set
            this.getRouter().initialize();

            // Initialize the UI model
            const oUiModel = new JSONModel({
                isBusy: false
            });
            this.setModel(oUiModel, "ui");

            // The i18n model is now automatically initialized based on the manifest.json
        }
    });
});