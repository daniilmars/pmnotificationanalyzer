sap.ui.define([
    "./BaseController"
], function (BaseController) {
    "use strict";

    return BaseController.extend("com.sap.pm.pmanalyzerfiori.controller.Worklist", {
        onPress: function (oEvent) {
            var oItem = oEvent.getSource();
            var sPath = oItem.getBindingContext().getPath();
            var sIndex = sPath.split("/").slice(-1).pop();

            this.getRouter().navTo("object", {
                caseId: sIndex
            });
        }
    });
});
