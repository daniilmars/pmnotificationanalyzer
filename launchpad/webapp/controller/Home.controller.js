sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/library"
], function (Controller, mobileLibrary) {
    "use strict";

    var URLHelper = mobileLibrary.URLHelper;

    return Controller.extend("com.sap.pm.launchpad.controller.Home", {

        onNavToPmAnalyzer: function () {
            // In a real-world scenario, this would be a more robust navigation.
            // For local development, we will just open the URL.
            URLHelper.redirect("http://localhost:8081/index.html", true);
        },

        onNavToRuleManager: function () {
            // In a real-world scenario, this would be a more robust navigation.
            // For local development, we will just open the URL.
            URLHelper.redirect("http://localhost:8080/index.html", true);
        }
    });
});