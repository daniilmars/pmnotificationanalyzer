sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/core/UIComponent"
], function (Controller, UIComponent) {
    "use strict";

    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.BaseController", {

        getRouter: function () {
            return UIComponent.getRouterFor(this);
        }

    });
});