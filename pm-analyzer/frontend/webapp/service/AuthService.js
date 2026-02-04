sap.ui.define([
    "sap/ui/base/Object",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox"
], function (BaseObject, JSONModel, MessageBox) {
    "use strict";

    /**
     * Authentication Service using Clerk
     *
     * Handles user authentication, session management, and role-based access control.
     *
     * Setup:
     * 1. Include Clerk's frontend SDK in index.html
     * 2. Initialize with your Clerk publishable key
     * 3. Use this service to manage auth state in the app
     */
    var AuthService = BaseObject.extend("pmanalyzer.service.AuthService", {

        _clerk: null,
        _user: null,
        _authModel: null,
        _initialized: false,

        /**
         * Initialize the auth service
         * @param {string} publishableKey - Clerk publishable key
         * @returns {Promise} Resolves when initialized
         */
        initialize: function (publishableKey) {
            var that = this;

            return new Promise(function (resolve, reject) {
                // Check if Clerk SDK is loaded
                if (typeof window.Clerk === "undefined") {
                    console.warn("Clerk SDK not loaded. Auth will be disabled.");
                    that._initializeDisabled();
                    resolve(false);
                    return;
                }

                // Initialize Clerk
                window.Clerk.load({
                    publishableKey: publishableKey
                }).then(function () {
                    that._clerk = window.Clerk;
                    that._setupAuthModel();
                    that._setupListeners();
                    that._initialized = true;

                    // Check initial auth state
                    if (that._clerk.user) {
                        that._setUser(that._clerk.user);
                    }

                    console.log("Clerk auth initialized");
                    resolve(true);
                }).catch(function (error) {
                    console.error("Clerk initialization failed:", error);
                    that._initializeDisabled();
                    resolve(false);
                });
            });
        },

        /**
         * Initialize in disabled mode (no auth)
         */
        _initializeDisabled: function () {
            this._authModel = new JSONModel({
                enabled: false,
                isAuthenticated: false,
                user: null,
                isAdmin: false,
                isEditor: false,
                isAuditor: false
            });
            this._initialized = true;
        },

        /**
         * Set up the auth model for data binding
         */
        _setupAuthModel: function () {
            this._authModel = new JSONModel({
                enabled: true,
                isAuthenticated: false,
                user: null,
                isAdmin: false,
                isEditor: false,
                isAuditor: false,
                isLoading: false
            });
        },

        /**
         * Set up Clerk event listeners
         */
        _setupListeners: function () {
            var that = this;

            // Listen for sign in/out events
            this._clerk.addListener(function (event) {
                if (event.user) {
                    that._setUser(event.user);
                } else {
                    that._clearUser();
                }
            });
        },

        /**
         * Set user data from Clerk user object
         */
        _setUser: function (clerkUser) {
            var publicMetadata = clerkUser.publicMetadata || {};
            var roles = publicMetadata.roles || [];

            this._user = {
                id: clerkUser.id,
                email: clerkUser.primaryEmailAddress?.emailAddress || "",
                firstName: clerkUser.firstName || "",
                lastName: clerkUser.lastName || "",
                fullName: clerkUser.fullName || clerkUser.firstName + " " + clerkUser.lastName,
                imageUrl: clerkUser.imageUrl || "",
                roles: roles,
                orgId: clerkUser.organizationMemberships?.[0]?.organization?.id,
                orgRole: clerkUser.organizationMemberships?.[0]?.role
            };

            // Determine role flags
            var isAdmin = roles.includes("admin") || roles.includes("org:admin");
            var isEditor = isAdmin || roles.includes("editor") || roles.includes("org:editor");
            var isAuditor = isAdmin || roles.includes("auditor") || roles.includes("org:auditor");

            this._authModel.setData({
                enabled: true,
                isAuthenticated: true,
                user: this._user,
                isAdmin: isAdmin,
                isEditor: isEditor,
                isAuditor: isAuditor,
                isLoading: false
            });

            console.log("User signed in:", this._user.email);
        },

        /**
         * Clear user data on sign out
         */
        _clearUser: function () {
            this._user = null;
            this._authModel.setData({
                enabled: true,
                isAuthenticated: false,
                user: null,
                isAdmin: false,
                isEditor: false,
                isAuditor: false,
                isLoading: false
            });

            console.log("User signed out");
        },

        /**
         * Get the auth model for data binding
         * @returns {sap.ui.model.json.JSONModel}
         */
        getModel: function () {
            return this._authModel;
        },

        /**
         * Check if user is authenticated
         * @returns {boolean}
         */
        isAuthenticated: function () {
            return this._authModel.getProperty("/isAuthenticated");
        },

        /**
         * Get current user
         * @returns {object|null}
         */
        getUser: function () {
            return this._user;
        },

        /**
         * Get auth token for API calls
         * @returns {Promise<string>}
         */
        getToken: function () {
            var that = this;

            return new Promise(function (resolve, reject) {
                if (!that._clerk || !that._clerk.session) {
                    resolve(null);
                    return;
                }

                that._clerk.session.getToken().then(function (token) {
                    resolve(token);
                }).catch(function (error) {
                    console.error("Failed to get token:", error);
                    resolve(null);
                });
            });
        },

        /**
         * Open sign in dialog
         */
        signIn: function () {
            if (this._clerk) {
                this._clerk.openSignIn();
            } else {
                MessageBox.warning("Authentication is not available.");
            }
        },

        /**
         * Open sign up dialog
         */
        signUp: function () {
            if (this._clerk) {
                this._clerk.openSignUp();
            } else {
                MessageBox.warning("Authentication is not available.");
            }
        },

        /**
         * Sign out current user
         * @returns {Promise}
         */
        signOut: function () {
            var that = this;

            return new Promise(function (resolve, reject) {
                if (!that._clerk) {
                    resolve();
                    return;
                }

                that._clerk.signOut().then(function () {
                    that._clearUser();
                    resolve();
                }).catch(function (error) {
                    console.error("Sign out failed:", error);
                    reject(error);
                });
            });
        },

        /**
         * Open user profile dialog
         */
        openUserProfile: function () {
            if (this._clerk) {
                this._clerk.openUserProfile();
            }
        },

        /**
         * Check if user has specific role
         * @param {string} role - Role to check
         * @returns {boolean}
         */
        hasRole: function (role) {
            if (!this._user) {
                return false;
            }

            // Admins have all roles
            if (this._authModel.getProperty("/isAdmin")) {
                return true;
            }

            return this._user.roles.includes(role);
        },

        /**
         * Check if user can perform action (for UI binding)
         * @param {string} action - Action name (view, edit, admin, audit)
         * @returns {boolean}
         */
        canPerform: function (action) {
            if (!this.isAuthenticated()) {
                return false;
            }

            switch (action) {
                case "view":
                    return true; // All authenticated users can view
                case "edit":
                    return this._authModel.getProperty("/isEditor");
                case "admin":
                    return this._authModel.getProperty("/isAdmin");
                case "audit":
                    return this._authModel.getProperty("/isAuditor");
                default:
                    return false;
            }
        },

        /**
         * Create authenticated fetch function for API calls
         * @returns {function}
         */
        createAuthFetch: function () {
            var that = this;

            return function (url, options) {
                options = options || {};
                options.headers = options.headers || {};

                return that.getToken().then(function (token) {
                    if (token) {
                        options.headers["Authorization"] = "Bearer " + token;
                    }
                    return fetch(url, options);
                });
            };
        }
    });

    // Singleton instance
    var instance = null;

    /**
     * Get singleton instance of AuthService
     * @returns {AuthService}
     */
    AuthService.getInstance = function () {
        if (!instance) {
            instance = new AuthService();
        }
        return instance;
    };

    return AuthService;
});
