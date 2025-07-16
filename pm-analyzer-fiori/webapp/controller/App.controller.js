sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/json/JSONModel"
], function (Controller, JSONModel) {
    "use strict";
    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.App", {
        onInit: function () {
            // Ein globales Model für den App-Zustand erstellen.
            var oAppViewModel = new JSONModel({
                currentUserRole: "Anwender"
            });
            this.getOwnerComponent().setModel(oAppViewModel, "appView");
        }
    });
});