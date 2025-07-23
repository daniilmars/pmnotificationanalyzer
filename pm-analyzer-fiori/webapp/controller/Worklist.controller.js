sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel"
], function (Controller, JSONModel) {
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

        onLogin: async function () {
            const oComponent = this.getOwnerComponent();
            const auth0Client = await oComponent.getAuth0Client();
            await auth0Client.loginWithRedirect();
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