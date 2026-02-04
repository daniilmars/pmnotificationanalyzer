sap.ui.define([
    "sap/ui/core/UIComponent",
    "sap/ui/Device",
    "sap/ui/model/json/JSONModel",
    "com/sap/pm/rulemanager/service/AuthService"
],
function (UIComponent, Device, JSONModel, AuthService) {
    "use strict";

    return UIComponent.extend("com.sap.pm.rulemanager.Component", {
        metadata: {
            manifest: "json"
        },

        _oAuthService: null,

        init: function () {
            // Call the base UIComponent's init method
            UIComponent.prototype.init.apply(this, arguments);

            // Set the device model
            this.setModel(new JSONModel(Device), "device");

            // Initialize the UI model
            const oUiModel = new JSONModel({
                isBusy: false
            });
            this.setModel(oUiModel, "ui");

            // Initialize the Auth Service
            this._oAuthService = new AuthService();
            this._oAuthService.init(this);

            // Create the views based on the url/hash
            this.getRouter().initialize();
        },

        /**
         * Get the Auth Service instance
         * @returns {AuthService}
         */
        getAuthService: function () {
            return this._oAuthService;
        },

        /**
         * Check if user is authenticated
         * @returns {boolean}
         */
        isAuthenticated: function () {
            return this._oAuthService ? this._oAuthService.isAuthenticated() : false;
        },

        /**
         * Check if user has permission
         * @param {string} sResource - Resource name
         * @param {string} sAction - Action name
         * @returns {boolean}
         */
        hasPermission: function (sResource, sAction) {
            return this._oAuthService ? this._oAuthService.hasPermission(sResource, sAction) : false;
        }
    });
});
