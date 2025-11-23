sap.ui.define([
    "sap/ui/core/UIComponent",
    "sap/ui/Device",
    "sap/ui/model/json/JSONModel"
],
function (UIComponent, Device, JSONModel) {
    "use strict";

    return UIComponent.extend("com.sap.pm.rulemanager.Component", {
        metadata: {
            manifest: "json"
        },

        init: function () {
            // Call the base UIComponent's init method
            UIComponent.prototype.init.apply(this, arguments);

            // Set the device model
            this.setModel(new JSONModel(Device), "device");

            // create the views based on the url/hash
            this.getRouter().initialize();

            // Initialize the UI model
            const oUiModel = new JSONModel({
                isBusy: false
            });
            this.setModel(oUiModel, "ui");
        }
    });
});
