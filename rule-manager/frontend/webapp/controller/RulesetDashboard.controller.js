sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "sap/ui/model/Filter",
    "sap/ui/model/FilterOperator",
    "sap/m/MessageBox",
    "sap/m/MessageToast",
    "sap/ui/core/Fragment"
], function (BaseController, JSONModel, Filter, FilterOperator, MessageBox, MessageToast, Fragment) {
    "use strict";
    return BaseController.extend("com.sap.pm.rulemanager.controller.RulesetDashboard", {

        onInit: function () {
            this.getView().setModel(new JSONModel(), "rulesets");
            this._loadRulesets();
        },

        /**
         * Handle login button press
         */
        onLoginPress: function () {
            var that = this;
            this.showLoginDialog(false).then(function () {
                // Reload rulesets after successful login
                that._loadRulesets();
            }).catch(function () {
                // Login cancelled or failed
            });
        },

        _loadRulesets: async function() {
            var oModel = this.getView().getModel("rulesets");
            var oAuthService = this.getAuthService();

            try {
                var oHeaders = oAuthService.getAuthHeaders();
                var response = await fetch("/api/v1/rulesets", {
                    headers: oHeaders
                });

                if (!response.ok) {
                    // Handle auth errors gracefully
                    if (response.status === 401) {
                        // Not authenticated - show empty list, user needs to login
                        oModel.setData([]);
                        return;
                    }
                    throw new Error("Failed to load rulesets: " + response.statusText);
                }
                var data = await response.json();
                oModel.setData(data);
            } catch (error) {
                MessageBox.error("Could not load rulesets: " + error.message);
            }
        },

        onPressRuleset: function (oEvent) {
            const oItem = oEvent.getSource();
            const oBindingContext = oItem.getBindingContext("rulesets");
            const sRulesetId = oBindingContext.getProperty("id");
            this.getRouter().navTo("ruleEditor", { 
                rulesetId: sRulesetId
            });
        },

        // --- Create Dialog --- //

        onCreateRuleset: function() {
            var oView = this.getView();
            if (!this._oCreateDialog) {
                Fragment.load({
                    id: oView.getId(),
                    name: "com.sap.pm.rulemanager.view.CreateRulesetDialog",
                    controller: this
                }).then(function (oDialog) {
                    oView.addDependent(oDialog);
                    this._oCreateDialog = oDialog;
                    oDialog.open();
                }.bind(this));
            } else {
                this._oCreateDialog.open();
            }
        },

        onCloseDialog: function() {
            this._oCreateDialog.close();
        },

        onSaveNewRuleset: async function() {
            var sName = Fragment.byId(this.getView().getId(), "rulesetNameInput").getValue();
            var sType = Fragment.byId(this.getView().getId(), "notificationTypeInput").getValue();

            if (!sName || !sType) {
                MessageBox.error("Please fill in all required fields.");
                return;
            }

            var oAuthService = this.getAuthService();
            var oUser = oAuthService.getCurrentUser();
            var oNewRuleset = {
                name: sName,
                notification_type: sType,
                created_by: oUser ? oUser.username : "system"
            };

            try {
                var oHeaders = Object.assign(
                    { "Content-Type": "application/json" },
                    oAuthService.getAuthHeaders()
                );

                var response = await fetch("/api/v1/rulesets", {
                    method: "POST",
                    headers: oHeaders,
                    body: JSON.stringify(oNewRuleset)
                });

                if (!response.ok) {
                    var errorData = await response.json();
                    throw new Error(errorData.error || "Request failed with status " + response.status);
                }

                MessageToast.show("Ruleset created successfully!");
                this.onCloseDialog();
                this._loadRulesets();
            } catch (error) {
                MessageBox.error("Failed to create ruleset: " + error.message);
            }
        },

        // --- Edit Dialog --- //

        onEditRuleset: function(oEvent) {
            var oView = this.getView();
            const oBindingContext = oEvent.getSource().getBindingContext("rulesets");
            this._oCurrentRulesetToEdit = oBindingContext.getObject();

            if (!this._oEditDialog) {
                Fragment.load({
                    id: oView.getId(),
                    name: "com.sap.pm.rulemanager.view.EditRulesetDialog",
                    controller: this
                }).then(function (oDialog) {
                    this._oEditDialog = oDialog;
                    oView.addDependent(oDialog);
                    oDialog.setModel(new JSONModel(this._oCurrentRulesetToEdit));
                    oDialog.open();
                }.bind(this));
            } else {
                this._oEditDialog.setModel(new JSONModel(this._oCurrentRulesetToEdit));
                this._oEditDialog.open();
            }
        },

        onCloseEditDialog: function() {
            this._oEditDialog.close();
        },

        onSaveUpdateRuleset: async function() {
            var oModel = this._oEditDialog.getModel();
            var oUpdatedData = oModel.getData();
            var oAuthService = this.getAuthService();
            var oUser = oAuthService.getCurrentUser();

            var oPayload = {
                name: oUpdatedData.name,
                notification_type: oUpdatedData.notification_type,
                created_by: oUser ? oUser.username : "system"
            };

            try {
                var oHeaders = Object.assign(
                    { "Content-Type": "application/json" },
                    oAuthService.getAuthHeaders()
                );

                var response = await fetch("/api/v1/rulesets/" + this._oCurrentRulesetToEdit.id, {
                    method: "PUT",
                    headers: oHeaders,
                    body: JSON.stringify(oPayload)
                });

                if (!response.ok) {
                    var errorData = await response.json();
                    throw new Error(errorData.error || "Request failed with status " + response.status);
                }

                MessageToast.show("Ruleset updated successfully! A new version has been created.");
                this.onCloseEditDialog();
                this._loadRulesets();
            } catch (error) {
                MessageBox.error("Failed to update ruleset: " + error.message);
            }
        },

        // --- Activate Action (with Electronic Signature) --- //

        onActivateRuleset: function(oEvent) {
            var that = this;
            var oBindingContext = oEvent.getSource().getBindingContext("rulesets");
            var oRulesetToActivate = oBindingContext.getObject();

            // Confirm activation
            MessageBox.confirm(
                "Activating this ruleset requires an electronic signature for regulatory compliance.\n\n" +
                "Are you sure you want to activate version " + oRulesetToActivate.version + " of ruleset '" + oRulesetToActivate.name + "'?",
                {
                    title: "Confirm Activation",
                    onClose: function (sAction) {
                        if (sAction === MessageBox.Action.OK) {
                            // Request electronic signature
                            that._activateWithSignature(oRulesetToActivate);
                        }
                    }
                }
            );
        },

        /**
         * Activate ruleset with electronic signature
         * @param {object} oRuleset - Ruleset to activate
         */
        _activateWithSignature: function(oRuleset) {
            var that = this;

            // Request electronic signature for activation
            this.requestSignature({
                entityType: "ruleset",
                entityId: oRuleset.id,
                entityName: oRuleset.name,
                entityVersion: oRuleset.version
            }, "Approved").then(function(oSignature) {
                // Signature successful, now activate the ruleset
                return that._performActivation(oRuleset, oSignature);
            }).catch(function(oError) {
                if (oError.message !== "Signature cancelled") {
                    MessageBox.error("Activation cancelled: " + oError.message);
                }
            });
        },

        /**
         * Perform the actual ruleset activation
         * @param {object} oRuleset - Ruleset to activate
         * @param {object} oSignature - Electronic signature
         */
        _performActivation: async function(oRuleset, oSignature) {
            var that = this;
            var oAuthService = this.getAuthService();
            var oUser = oAuthService.getCurrentUser();

            var oPayload = {
                created_by: oUser ? oUser.username : "system",
                signature_id: oSignature.id
            };

            try {
                var oHeaders = Object.assign(
                    { "Content-Type": "application/json" },
                    oAuthService.getAuthHeaders()
                );

                var response = await fetch("/api/v1/rulesets/" + oRuleset.id + "/activate", {
                    method: "POST",
                    headers: oHeaders,
                    body: JSON.stringify(oPayload)
                });

                if (!response.ok) {
                    var errorData = await response.json();
                    throw new Error(errorData.error || "Request failed with status " + response.status);
                }

                MessageToast.show("Ruleset '" + oRuleset.name + "' activated successfully!");
                that._loadRulesets();

            } catch (error) {
                MessageBox.error("Failed to activate ruleset: " + error.message);
            }
        },

        // --- SOP Assistant --- //

        onImportFromSop: function() {
            var oView = this.getView();
            if (!this._oSopDialog) {
                Fragment.load({
                    id: oView.getId(),
                    name: "com.sap.pm.rulemanager.view.SopAssistantDialog",
                    controller: this
                }).then(function (oDialog) {
                    oView.addDependent(oDialog);
                    this._oSopDialog = oDialog;
                    oDialog.open();
                    this._loadDraftRulesetsForSelect();
                }.bind(this));
            } else {
                this._oSopDialog.open();
                this._loadDraftRulesetsForSelect();
            }
        },

        _loadDraftRulesetsForSelect: function() {
            const oRulesetsModel = this.getView().getModel("rulesets");
            const aAllRulesets = oRulesetsModel.getData();
            const aDraftRulesets = aAllRulesets.filter(rs => rs.status === "Draft");
            
            const oDraftModel = new JSONModel(aDraftRulesets);
            this._oSopDialog.setModel(oDraftModel, "draftRulesets");
        },

        onCloseSopDialog: function() {
            if (this._oSopDialog && this._oSopDialog.close) {
                this._oSopDialog.close();
            }
        },

        onAnalyzeSop: async function() {
            var oFileUploader = Fragment.byId(this.getView().getId(), "sopFileUploader");
            var oRulesetSelect = Fragment.byId(this.getView().getId(), "rulesetSelect");
            var sSelectedRulesetId = oRulesetSelect.getSelectedKey();
            var oFile = oFileUploader.getDomRef("fu").files[0];

            if (!oFile || !sSelectedRulesetId) {
                MessageBox.error("Please choose a file and a ruleset.");
                return;
            }

            var oFormData = new FormData();
            oFormData.append("sop_file", oFile);

            this.getView().setBusy(true);
            this.onCloseSopDialog();

            try {
                var oAuthService = this.getAuthService();
                var oHeaders = oAuthService.getAuthHeaders();

                var response = await fetch("/api/v1/sop-assistant/extract", {
                    method: "POST",
                    headers: oHeaders,
                    body: oFormData
                });

                if (!response.ok) {
                    var errorData = await response.json();
                    throw new Error(errorData.error || "Request failed with status " + response.status);
                }

                var aSuggestedRules = await response.json();

                this.getRouter().navTo("review", {
                    rulesetId: sSelectedRulesetId,
                    suggestedRules: encodeURIComponent(JSON.stringify(aSuggestedRules))
                });

            } catch (error) {
                MessageBox.error("Failed to analyze SOP: " + error.message);
            } finally {
                this.getView().setBusy(false);
            }
        }

    });
});