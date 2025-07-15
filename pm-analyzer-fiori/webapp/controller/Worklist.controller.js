sap.ui.define([
    "./BaseController"
], function (BaseController) {
    "use strict";

    return BaseController.extend("com.sap.pm.pmanalyzerfiori.controller.Worklist", {

        onPress: function (oEvent) {
            // Holt das Objekt, auf das geklickt wurde
            var oItem = oEvent.getSource();

            // Holt den Pfad zum Datenobjekt (z.B. "/0" für das erste Element)
            var sPath = oItem.getBindingContext().getPath();
            var sIndex = sPath.split("/").slice(-1).pop();

            // Navigiert zur "object"-Route und übergibt den Index als Parameter
            this.getRouter().navTo("object", {
                objectId: sIndex
            });
        }
    });
});