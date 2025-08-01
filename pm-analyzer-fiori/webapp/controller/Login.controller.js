sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/MessageBox"
], function (Controller, MessageBox) {
    "use strict";

    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.Login", {

        onInit: function () {
            // Automatically navigate to worklist if no authentication is needed
            this.getOwnerComponent().getRouter().navTo("worklist", {}, true);
        }
        // Removed onLoginPress as login is no longer required
    });
});
