sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "sap/ui/model/Filter",
    "sap/ui/model/FilterOperator",
    "sap/m/MessageBox",
    "sap/ui/core/Fragment"
], function (BaseController, JSONModel, Filter, FilterOperator, MessageBox, Fragment) {
    "use strict";
    return BaseController.extend("com.sap.pm.rulemanager.controller.RulesetDashboard", {

        onInit: function () {
            this.getView().setModel(new JSONModel(), "rulesets");
            this._loadRulesets();
        },

        _loadRulesets: async function() {
            const oModel = this.getView().getModel("rulesets");
            try {
                const response = await fetch("/api/v1/rulesets");
                if (!response.ok) {
                    throw new Error(`Failed to load rulesets: ${response.statusText}`);
                }
                const data = await response.json();
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
            const sName = Fragment.byId(this.getView().getId(), "rulesetNameInput").getValue();
            const sType = Fragment.byId(this.getView().getId(), "notificationTypeInput").getValue();

            if (!sName || !sType) {
                MessageBox.error("Please fill in all required fields.");
                return;
            }

            const oNewRuleset = { name: sName, notification_type: sType, created_by: "manual_user" };

            try {
                const response = await fetch("/api/v1/rulesets", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(oNewRuleset)
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `Request failed with status ${response.status}`);
                }

                MessageBox.success("Ruleset created successfully!");
                this.onCloseDialog();
                this._loadRulesets();
            } catch (error) {
                MessageBox.error(`Failed to create ruleset: ${error.message}`);
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
            const oModel = this._oEditDialog.getModel();
            const oUpdatedData = oModel.getData();

            const oPayload = { name: oUpdatedData.name, notification_type: oUpdatedData.notification_type, created_by: "manual_user_edit" };

            try {
                const response = await fetch(`/api/v1/rulesets/${this._oCurrentRulesetToEdit.id}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(oPayload)
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `Request failed with status ${response.status}`);
                }

                MessageBox.success("Ruleset updated successfully! A new version has been created.");
                this.onCloseEditDialog();
                this._loadRulesets();
            } catch (error) {
                MessageBox.error(`Failed to update ruleset: ${error.message}`);
            }
        },

        // --- Activate Action --- //

        onActivateRuleset: async function(oEvent) {
            const oBindingContext = oEvent.getSource().getBindingContext("rulesets");
            const oRulesetToActivate = oBindingContext.getObject();

            MessageBox.confirm(`Are you sure you want to activate version ${oRulesetToActivate.version} of this ruleset?`, {
                onClose: async function (sAction) {
                    if (sAction === MessageBox.Action.OK) {
                        const oPayload = { created_by: "manual_user_activate" }; // Placeholder
                        try {
                            const response = await fetch(`/api/v1/rulesets/${oRulesetToActivate.id}/activate`, {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify(oPayload)
                            });

                            if (!response.ok) {
                                const errorData = await response.json();
                                throw new Error(errorData.error || `Request failed with status ${response.status}`);
                            }

                            MessageBox.success("Ruleset activated successfully!");
                            this._loadRulesets(); // Refresh the table

                        } catch (error) {
                            MessageBox.error(`Failed to activate ruleset: ${error.message}`);
                        }
                    }
                }.bind(this)
            });
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
            const oFileUploader = Fragment.byId(this.getView().getId(), "sopFileUploader");
            const oRulesetSelect = Fragment.byId(this.getView().getId(), "rulesetSelect");
            const sSelectedRulesetId = oRulesetSelect.getSelectedKey();
            const oFile = oFileUploader.getDomRef("fu").files[0];

            if (!oFile || !sSelectedRulesetId) {
                MessageBox.error("Please choose a file and a ruleset.");
                return;
            }

            const oFormData = new FormData();
            oFormData.append("sop_file", oFile);

            this.getView().setBusy(true);
            this.onCloseSopDialog();

            try {
                const response = await fetch("/api/v1/sop-assistant/extract", {
                    method: "POST",
                    body: oFormData
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `Request failed with status ${response.status}`);
                }

                const aSuggestedRules = await response.json();
                
                this.getRouter().navTo("review", {
                    rulesetId: sSelectedRulesetId,
                    suggestedRules: encodeURIComponent(JSON.stringify(aSuggestedRules))
                });

            } catch (error) {
                MessageBox.error(`Failed to analyze SOP: ${error.message}`);
            }
        }

    });
});