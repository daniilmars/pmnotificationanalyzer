/**
 * Authentication Service for Rule Manager Frontend
 *
 * Provides authentication, authorization, and electronic signature functionality
 * for FDA 21 CFR Part 11 compliance.
 */
sap.ui.define([
    "sap/ui/base/Object",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/m/MessageToast"
], function (BaseObject, JSONModel, MessageBox, MessageToast) {
    "use strict";

    var AUTH_STORAGE_KEY = "pm_rulemanager_auth";
    var TOKEN_REFRESH_BUFFER = 5 * 60 * 1000; // 5 minutes before expiry

    return BaseObject.extend("com.sap.pm.rulemanager.service.AuthService", {

        _oAuthModel: null,
        _sApiBaseUrl: "/api/v1/auth",
        _refreshTimer: null,

        /**
         * Initialize the auth service
         * @param {sap.ui.core.Component} oComponent - The component instance
         */
        init: function (oComponent) {
            this._oComponent = oComponent;
            this._oAuthModel = new JSONModel({
                isAuthenticated: false,
                user: null,
                roles: [],
                permissions: [],
                token: null,
                tokenExpiry: null,
                isLoading: false
            });

            oComponent.setModel(this._oAuthModel, "auth");

            // Try to restore session from storage
            this._restoreSession();
        },

        /**
         * Get the auth model
         * @returns {sap.ui.model.json.JSONModel}
         */
        getModel: function () {
            return this._oAuthModel;
        },

        /**
         * Check if user is authenticated
         * @returns {boolean}
         */
        isAuthenticated: function () {
            return this._oAuthModel.getProperty("/isAuthenticated");
        },

        /**
         * Get current user info
         * @returns {object|null}
         */
        getCurrentUser: function () {
            return this._oAuthModel.getProperty("/user");
        },

        /**
         * Check if user has a specific role
         * @param {string} sRole - Role name to check
         * @returns {boolean}
         */
        hasRole: function (sRole) {
            var aRoles = this._oAuthModel.getProperty("/roles") || [];
            return aRoles.indexOf(sRole) !== -1;
        },

        /**
         * Check if user has a specific permission
         * @param {string} sResource - Resource name (e.g., "rulesets")
         * @param {string} sAction - Action name (e.g., "create")
         * @returns {boolean}
         */
        hasPermission: function (sResource, sAction) {
            var aPermissions = this._oAuthModel.getProperty("/permissions") || [];
            var sPermKey = sResource + ":" + sAction;
            return aPermissions.indexOf(sPermKey) !== -1;
        },

        /**
         * Login with username and password
         * @param {string} sUsername - Username
         * @param {string} sPassword - Password
         * @returns {Promise<object>} - User data on success
         */
        login: function (sUsername, sPassword) {
            var that = this;
            this._oAuthModel.setProperty("/isLoading", true);

            return fetch(this._sApiBaseUrl + "/login", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    username: sUsername,
                    password: sPassword
                })
            })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (error) {
                        throw new Error(error.error || "Login failed");
                    });
                }
                return response.json();
            })
            .then(function (data) {
                that._setAuthState(data);
                that._saveSession();
                that._scheduleTokenRefresh();
                MessageToast.show("Welcome, " + data.user.full_name);
                return data;
            })
            .catch(function (error) {
                that._clearAuthState();
                throw error;
            })
            .finally(function () {
                that._oAuthModel.setProperty("/isLoading", false);
            });
        },

        /**
         * Logout the current user
         * @returns {Promise}
         */
        logout: function () {
            var that = this;
            var sToken = this._oAuthModel.getProperty("/token");

            return fetch(this._sApiBaseUrl + "/logout", {
                method: "POST",
                headers: {
                    "Authorization": "Bearer " + sToken,
                    "Content-Type": "application/json"
                }
            })
            .then(function () {
                that._clearAuthState();
                that._clearSession();
                MessageToast.show("You have been logged out");
            })
            .catch(function (error) {
                // Clear local state even if server logout fails
                that._clearAuthState();
                that._clearSession();
                console.warn("Logout error:", error);
            });
        },

        /**
         * Change password for current user
         * @param {string} sCurrentPassword - Current password
         * @param {string} sNewPassword - New password
         * @returns {Promise}
         */
        changePassword: function (sCurrentPassword, sNewPassword) {
            var sToken = this._oAuthModel.getProperty("/token");

            return fetch(this._sApiBaseUrl + "/change-password", {
                method: "POST",
                headers: {
                    "Authorization": "Bearer " + sToken,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    current_password: sCurrentPassword,
                    new_password: sNewPassword
                })
            })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (error) {
                        throw new Error(error.error || "Password change failed");
                    });
                }
                return response.json();
            })
            .then(function (data) {
                MessageToast.show("Password changed successfully");
                return data;
            });
        },

        /**
         * Create an electronic signature (re-authentication required)
         * @param {string} sPassword - User password for re-authentication
         * @param {string} sEntityType - Entity type (e.g., "ruleset")
         * @param {string} sEntityId - Entity ID
         * @param {string} sMeaning - Signature meaning (e.g., "Approved", "Reviewed")
         * @param {string} sReason - Optional reason for signature
         * @param {number} iEntityVersion - Optional entity version
         * @returns {Promise<object>} - Signature data
         */
        createSignature: function (sPassword, sEntityType, sEntityId, sMeaning, sReason, iEntityVersion) {
            var sToken = this._oAuthModel.getProperty("/token");

            return fetch(this._sApiBaseUrl + "/signatures", {
                method: "POST",
                headers: {
                    "Authorization": "Bearer " + sToken,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    password: sPassword,
                    entity_type: sEntityType,
                    entity_id: sEntityId,
                    meaning: sMeaning,
                    reason: sReason || "",
                    entity_version: iEntityVersion
                })
            })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (error) {
                        throw new Error(error.error || "Signature creation failed");
                    });
                }
                return response.json();
            });
        },

        /**
         * Get signatures for an entity
         * @param {string} sEntityType - Entity type
         * @param {string} sEntityId - Entity ID
         * @returns {Promise<array>} - List of signatures
         */
        getSignatures: function (sEntityType, sEntityId) {
            var sToken = this._oAuthModel.getProperty("/token");

            return fetch(this._sApiBaseUrl + "/signatures/" + sEntityType + "/" + sEntityId, {
                method: "GET",
                headers: {
                    "Authorization": "Bearer " + sToken
                }
            })
            .then(function (response) {
                if (!response.ok) {
                    return response.json().then(function (error) {
                        throw new Error(error.error || "Failed to get signatures");
                    });
                }
                return response.json();
            });
        },

        /**
         * Get authorization header for API calls
         * @returns {object} - Headers object with Authorization
         */
        getAuthHeaders: function () {
            var sToken = this._oAuthModel.getProperty("/token");
            if (sToken) {
                return {
                    "Authorization": "Bearer " + sToken
                };
            }
            return {};
        },

        /**
         * Make authenticated API request
         * @param {string} sUrl - API endpoint URL
         * @param {object} oOptions - Fetch options
         * @returns {Promise}
         */
        fetchWithAuth: function (sUrl, oOptions) {
            var that = this;
            oOptions = oOptions || {};
            oOptions.headers = Object.assign({}, oOptions.headers, this.getAuthHeaders());

            return fetch(sUrl, oOptions).then(function (response) {
                // Handle 401 - session expired
                if (response.status === 401) {
                    that._clearAuthState();
                    that._clearSession();
                    MessageBox.warning("Your session has expired. Please login again.");
                    // Trigger re-login
                    that._oComponent.getRouter().navTo("login");
                    throw new Error("Session expired");
                }
                return response;
            });
        },

        /**
         * Refresh the current token
         * @returns {Promise}
         */
        refreshToken: function () {
            var that = this;
            var sToken = this._oAuthModel.getProperty("/token");

            return fetch(this._sApiBaseUrl + "/refresh", {
                method: "POST",
                headers: {
                    "Authorization": "Bearer " + sToken,
                    "Content-Type": "application/json"
                }
            })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Token refresh failed");
                }
                return response.json();
            })
            .then(function (data) {
                that._oAuthModel.setProperty("/token", data.token);
                that._oAuthModel.setProperty("/tokenExpiry", data.expires_at);
                that._saveSession();
                that._scheduleTokenRefresh();
            })
            .catch(function (error) {
                console.warn("Token refresh failed:", error);
                that._clearAuthState();
                that._clearSession();
            });
        },

        // Private methods

        _setAuthState: function (oData) {
            this._oAuthModel.setProperty("/isAuthenticated", true);
            this._oAuthModel.setProperty("/user", oData.user);
            this._oAuthModel.setProperty("/roles", oData.roles || []);
            this._oAuthModel.setProperty("/permissions", oData.permissions || []);
            this._oAuthModel.setProperty("/token", oData.token);
            this._oAuthModel.setProperty("/tokenExpiry", oData.expires_at);
        },

        _clearAuthState: function () {
            if (this._refreshTimer) {
                clearTimeout(this._refreshTimer);
                this._refreshTimer = null;
            }
            this._oAuthModel.setProperty("/isAuthenticated", false);
            this._oAuthModel.setProperty("/user", null);
            this._oAuthModel.setProperty("/roles", []);
            this._oAuthModel.setProperty("/permissions", []);
            this._oAuthModel.setProperty("/token", null);
            this._oAuthModel.setProperty("/tokenExpiry", null);
        },

        _saveSession: function () {
            var oSessionData = {
                token: this._oAuthModel.getProperty("/token"),
                tokenExpiry: this._oAuthModel.getProperty("/tokenExpiry"),
                user: this._oAuthModel.getProperty("/user"),
                roles: this._oAuthModel.getProperty("/roles"),
                permissions: this._oAuthModel.getProperty("/permissions")
            };
            try {
                sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(oSessionData));
            } catch (e) {
                console.warn("Could not save session to storage:", e);
            }
        },

        _clearSession: function () {
            try {
                sessionStorage.removeItem(AUTH_STORAGE_KEY);
            } catch (e) {
                console.warn("Could not clear session from storage:", e);
            }
        },

        _restoreSession: function () {
            try {
                var sSessionData = sessionStorage.getItem(AUTH_STORAGE_KEY);
                if (sSessionData) {
                    var oSessionData = JSON.parse(sSessionData);

                    // Check if token is still valid
                    if (oSessionData.tokenExpiry) {
                        var dExpiry = new Date(oSessionData.tokenExpiry);
                        if (dExpiry > new Date()) {
                            this._setAuthState({
                                token: oSessionData.token,
                                expires_at: oSessionData.tokenExpiry,
                                user: oSessionData.user,
                                roles: oSessionData.roles,
                                permissions: oSessionData.permissions
                            });
                            this._scheduleTokenRefresh();
                            return;
                        }
                    }
                    // Token expired, clear session
                    this._clearSession();
                }
            } catch (e) {
                console.warn("Could not restore session:", e);
                this._clearSession();
            }
        },

        _scheduleTokenRefresh: function () {
            var that = this;
            var sExpiry = this._oAuthModel.getProperty("/tokenExpiry");

            if (!sExpiry) {
                return;
            }

            var dExpiry = new Date(sExpiry);
            var iRefreshTime = dExpiry.getTime() - Date.now() - TOKEN_REFRESH_BUFFER;

            if (iRefreshTime > 0) {
                if (this._refreshTimer) {
                    clearTimeout(this._refreshTimer);
                }
                this._refreshTimer = setTimeout(function () {
                    that.refreshToken();
                }, iRefreshTime);
            }
        }
    });
});
