sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/MessageBox"
], function (Controller, MessageBox) {
    "use strict";

    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.Login", {

        onLoginPress: async function () {
            try {
                const oComponent = this.getOwnerComponent();
                const auth0Client = await oComponent.getAuth0Client();
                await auth0Client.loginWithRedirect();
            } catch (error) {
                MessageBox.error("Could not initiate login process. Please try again later.");
                console.error("Login failed", error);
            }
        }
    });
});