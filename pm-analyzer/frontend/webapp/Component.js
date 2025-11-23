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

            // Initialize an empty JSONModel for the application data
            // This will be populated by the Worklist controller via API
            this.setModel(new JSONModel({ Notifications: [] }));

            // Initialize the router after the model is set
            this.getRouter().initialize();

            // Initialize the UI model
            const oUiModel = new JSONModel({
                isBusy: false
            });
            this.setModel(oUiModel, "ui");
        }
    });
});
