sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/library"
],
function (Controller, mobileLibrary) {
    "use strict";

    var URLHelper = mobileLibrary.URLHelper;

    return Controller.extend("com.sap.pm.rulemanager.controller.App", {
        onInit: function () {
        },

        onHomePressed: function () {
            URLHelper.redirect("http://localhost:8008/index.html", false);
        }
    });
});
