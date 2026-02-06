sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/m/library"
], function (Controller, mobileLibrary) {
    "use strict";

    var URLHelper = mobileLibrary.URLHelper;

    return Controller.extend("com.sap.pm.launchpad.controller.Home", {

        onNavToPmAnalyzer: function () {
            URLHelper.redirect("http://localhost:8081/index.html", true);
        },

        onNavToRuleManager: function () {
            URLHelper.redirect("http://localhost:8080/index.html", true);
        },

        onNavToQualityDashboard: function () {
            URLHelper.redirect("http://localhost:8081/index.html#/QualityDashboard", true);
        },

        onNavToReliabilityDashboard: function () {
            URLHelper.redirect("http://localhost:8081/index.html#/ReliabilityDashboard", true);
        }
    });
});
