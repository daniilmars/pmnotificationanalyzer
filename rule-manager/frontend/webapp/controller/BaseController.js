sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/core/UIComponent",
    "sap/ui/core/routing/History",
    "sap/ui/core/Fragment",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/m/MessageToast"
], function (Controller, UIComponent, History, Fragment, JSONModel, MessageBox, MessageToast) {
    "use strict";

    return Controller.extend("com.sap.pm.rulemanager.controller.BaseController", {

        _oLoginDialog: null,
        _oSignatureDialog: null,
        _oUserMenu: null,
        _fnSignatureCallback: null,

        getRouter: function () {
            return UIComponent.getRouterFor(this);
        },

        getModel: function (sName) {
            return this.getView().getModel(sName);
        },

        setModel: function (oModel, sName) {
            return this.getView().setModel(oModel, sName);
        },

        getResourceBundle: function () {
            return this.getOwnerComponent().getModel("i18n").getResourceBundle();
        },

        onNavBack: function () {
            const sPreviousHash = History.getInstance().getPreviousHash();
            if (sPreviousHash !== undefined) {
                history.go(-1);
            } else {
                this.getRouter().navTo("dashboard", {}, true);
            }
        },

        // ==========================================
        // Authentication Methods
        // ==========================================

        /**
         * Get the Auth Service
         * @returns {AuthService}
         */
        getAuthService: function () {
            return this.getOwnerComponent().getAuthService();
        },

        /**
         * Check if user is authenticated
         * @returns {boolean}
         */
        isAuthenticated: function () {
            return this.getOwnerComponent().isAuthenticated();
        },

        /**
         * Check if user has permission
         * @param {string} sResource - Resource name
         * @param {string} sAction - Action name
         * @returns {boolean}
         */
        hasPermission: function (sResource, sAction) {
            return this.getOwnerComponent().hasPermission(sResource, sAction);
        },

        /**
         * Show login dialog
         * @param {boolean} bShowCancel - Show cancel button
         * @returns {Promise}
         */
        showLoginDialog: function (bShowCancel) {
            var that = this;
            var oView = this.getView();

            // Create login model
            var oLoginModel = new JSONModel({
                username: "",
                password: "",
                hasError: false,
                errorMessage: "",
                showPasswordWarning: false,
                showCancelButton: bShowCancel !== false
            });
            oView.setModel(oLoginModel, "loginModel");

            return new Promise(function (resolve, reject) {
                if (!that._oLoginDialog) {
                    Fragment.load({
                        id: oView.getId(),
                        name: "com.sap.pm.rulemanager.view.LoginDialog",
                        controller: that
                    }).then(function (oDialog) {
                        oView.addDependent(oDialog);
                        that._oLoginDialog = oDialog;
                        that._fnLoginResolve = resolve;
                        that._fnLoginReject = reject;
                        oDialog.open();
                    });
                } else {
                    that._fnLoginResolve = resolve;
                    that._fnLoginReject = reject;
                    that._oLoginDialog.open();
                }
            });
        },

        /**
         * Handle login submit
         */
        onLoginSubmit: function () {
            var that = this;
            var oLoginModel = this.getModel("loginModel");
            var sUsername = oLoginModel.getProperty("/username");
            var sPassword = oLoginModel.getProperty("/password");

            oLoginModel.setProperty("/hasError", false);

            this.getAuthService().login(sUsername, sPassword)
                .then(function (oData) {
                    that._oLoginDialog.close();
                    oLoginModel.setProperty("/username", "");
                    oLoginModel.setProperty("/password", "");
                    if (that._fnLoginResolve) {
                        that._fnLoginResolve(oData);
                    }
                })
                .catch(function (oError) {
                    oLoginModel.setProperty("/hasError", true);
                    oLoginModel.setProperty("/errorMessage", oError.message || "Login failed");
                    if (that._fnLoginReject) {
                        that._fnLoginReject(oError);
                    }
                });
        },

        /**
         * Handle login input change - clear error
         */
        onLoginInputChange: function () {
            this.getModel("loginModel").setProperty("/hasError", false);
        },

        /**
         * Handle login dialog cancel
         */
        onLoginDialogCancel: function () {
            this._oLoginDialog.close();
            this.getModel("loginModel").setProperty("/username", "");
            this.getModel("loginModel").setProperty("/password", "");
            if (this._fnLoginReject) {
                this._fnLoginReject(new Error("Login cancelled"));
            }
        },

        /**
         * Handle login dialog escape
         */
        onLoginDialogEscape: function (oPromise) {
            oPromise.reject();
        },

        // ==========================================
        // User Menu Methods
        // ==========================================

        /**
         * Show user menu
         * @param {sap.ui.base.Event} oEvent - Button press event
         */
        onUserMenuPress: function (oEvent) {
            var that = this;
            var oButton = oEvent.getSource();
            var oView = this.getView();

            if (!this._oUserMenu) {
                Fragment.load({
                    id: oView.getId(),
                    name: "com.sap.pm.rulemanager.view.UserMenu",
                    controller: this
                }).then(function (oMenu) {
                    oView.addDependent(oMenu);
                    that._oUserMenu = oMenu;
                    oMenu.openBy(oButton);
                });
            } else {
                this._oUserMenu.openBy(oButton);
            }
        },

        /**
         * Handle logout
         */
        onLogoutPress: function () {
            var that = this;
            MessageBox.confirm(this.getResourceBundle().getText("logoutConfirm") || "Are you sure you want to logout?", {
                title: this.getResourceBundle().getText("logout"),
                onClose: function (oAction) {
                    if (oAction === MessageBox.Action.OK) {
                        that.getAuthService().logout().then(function () {
                            // Optionally navigate to login or refresh
                            that.getRouter().navTo("dashboard");
                        });
                    }
                }
            });
        },

        /**
         * Handle change password
         */
        onChangePasswordPress: function () {
            // Implementation for password change dialog
            MessageToast.show("Change password feature - to be implemented");
        },

        // ==========================================
        // Electronic Signature Methods
        // ==========================================

        /**
         * Request electronic signature
         * @param {object} oEntityInfo - Entity information
         * @param {string} oEntityInfo.entityType - Entity type (e.g., "ruleset")
         * @param {string} oEntityInfo.entityId - Entity ID
         * @param {string} oEntityInfo.entityName - Entity display name
         * @param {number} oEntityInfo.entityVersion - Entity version
         * @param {string} sDefaultMeaning - Default signature meaning
         * @returns {Promise<object>} - Resolves with signature data
         */
        requestSignature: function (oEntityInfo, sDefaultMeaning) {
            var that = this;
            var oView = this.getView();

            // Create signature model
            var oSignatureModel = new JSONModel({
                entityType: oEntityInfo.entityType,
                entityId: oEntityInfo.entityId,
                entityName: oEntityInfo.entityName || oEntityInfo.entityId,
                entityVersion: oEntityInfo.entityVersion || null,
                meaning: sDefaultMeaning || "Approved",
                reason: "",
                password: "",
                hasError: false,
                errorMessage: "",
                isSubmitting: false
            });
            oView.setModel(oSignatureModel, "signatureModel");

            return new Promise(function (resolve, reject) {
                if (!that._oSignatureDialog) {
                    Fragment.load({
                        id: oView.getId(),
                        name: "com.sap.pm.rulemanager.view.SignatureDialog",
                        controller: that
                    }).then(function (oDialog) {
                        oView.addDependent(oDialog);
                        that._oSignatureDialog = oDialog;
                        that._fnSignatureResolve = resolve;
                        that._fnSignatureReject = reject;
                        oDialog.open();
                    });
                } else {
                    that._fnSignatureResolve = resolve;
                    that._fnSignatureReject = reject;
                    that._oSignatureDialog.open();
                }
            });
        },

        /**
         * Handle signature submit
         */
        onSignatureSubmit: function () {
            var that = this;
            var oSignatureModel = this.getModel("signatureModel");

            oSignatureModel.setProperty("/hasError", false);
            oSignatureModel.setProperty("/isSubmitting", true);

            var sPassword = oSignatureModel.getProperty("/password");
            var sEntityType = oSignatureModel.getProperty("/entityType");
            var sEntityId = oSignatureModel.getProperty("/entityId");
            var sMeaning = oSignatureModel.getProperty("/meaning");
            var sReason = oSignatureModel.getProperty("/reason");
            var iVersion = oSignatureModel.getProperty("/entityVersion");

            this.getAuthService().createSignature(
                sPassword,
                sEntityType,
                sEntityId,
                sMeaning,
                sReason,
                iVersion
            )
            .then(function (oSignature) {
                that._oSignatureDialog.close();
                oSignatureModel.setProperty("/password", "");
                MessageToast.show(that.getResourceBundle().getText("signatureSuccess"));
                if (that._fnSignatureResolve) {
                    that._fnSignatureResolve(oSignature);
                }
            })
            .catch(function (oError) {
                oSignatureModel.setProperty("/hasError", true);
                oSignatureModel.setProperty("/errorMessage", oError.message || "Signature failed");
            })
            .finally(function () {
                oSignatureModel.setProperty("/isSubmitting", false);
            });
        },

        /**
         * Handle signature dialog cancel
         */
        onSignatureDialogCancel: function () {
            this._oSignatureDialog.close();
            this.getModel("signatureModel").setProperty("/password", "");
            if (this._fnSignatureReject) {
                this._fnSignatureReject(new Error("Signature cancelled"));
            }
        },

        // ==========================================
        // Permission-based UI Helpers
        // ==========================================

        /**
         * Check permission and show message if denied
         * @param {string} sResource - Resource name
         * @param {string} sAction - Action name
         * @returns {boolean}
         */
        checkPermissionWithMessage: function (sResource, sAction) {
            if (!this.hasPermission(sResource, sAction)) {
                MessageBox.warning(this.getResourceBundle().getText("noPermission"));
                return false;
            }
            return true;
        },

        /**
         * Execute action with signature if required
         * @param {object} oEntityInfo - Entity information
         * @param {string} sMeaning - Signature meaning
         * @param {function} fnAction - Action to execute after signature
         * @returns {Promise}
         */
        executeWithSignature: function (oEntityInfo, sMeaning, fnAction) {
            var that = this;
            return this.requestSignature(oEntityInfo, sMeaning)
                .then(function (oSignature) {
                    return fnAction(oSignature);
                });
        }

    });
});