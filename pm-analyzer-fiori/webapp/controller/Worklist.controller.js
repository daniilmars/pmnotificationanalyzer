sap.ui.define([
    "sap/ui/core/mvc/Controller"
], function (Controller) {
    "use strict";
    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.Worklist", {
        onInit: function () {
            // The main data model is now set globally in Component.js
        },

        onPress: function (oEvent) {
            const oItem = oEvent.getSource();
            const oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("object", {
                notificationId: oItem.getBindingContext().getProperty("NotificationId")
            });
        },
 
        onLogout: async function () {
            const oComponent = this.getOwnerComponent();
            const auth0Client = await oComponent.getAuth0Client();
            auth0Client.logout({
                logoutParams: {
                    returnTo: window.location.origin + window.location.pathname
                }
            });
        }
    });
});