sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "sap/ui/core/Fragment"
], function (BaseController, JSONModel, MessageBox, Fragment) {
    "use strict";
    return BaseController.extend("com.sap.pm.rulemanager.controller.RuleEditor", {

        onInit: function () {
            const oRouter = this.getRouter();
            oRouter.getRoute("ruleEditor").attachPatternMatched(this._onObjectMatched, this);
        },

        _onObjectMatched: async function (oEvent) {
            const sRulesetId = oEvent.getParameter("arguments").rulesetId;
            this._rulesetId = sRulesetId;
            const oModel = new JSONModel();
            this.getView().setModel(oModel, "rules");
            this._loadRules();
        },

        _loadRules: async function() {
            try {
                const response = await fetch(`/api/v1/rulesets/${this._rulesetId}`);
                if (!response.ok) {
                    throw new Error(`Failed to load ruleset details: ${response.statusText}`);
                }
                const data = await response.json();
                this.getView().getModel("rules").setData(data.rules);
            } catch (error) {
                MessageBox.error(error.message);
            }
        },

        onNavBack: function() {
            this.getRouter().navTo("dashboard", {}, true);
        },

        onCreateRule: function() {
            var oView = this.getView();
            if (!this._oCreateRuleDialog) {
                Fragment.load({
                    id: oView.getId(),
                    name: "com.sap.pm.rulemanager.view.CreateRuleDialog",
                    controller: this
                }).then(function (oDialog) {
                    oView.addDependent(oDialog);
                    this._oCreateRuleDialog = oDialog;
                    oDialog.open();
                }.bind(this));
            } else {
                this._oCreateRuleDialog.open();
            }
        },

        onCloseCreateRuleDialog: function() {
            this._oCreateRuleDialog.close();
        },

        onSaveNewRule: async function() {
            const oView = this.getView();
            const getVal = (sId) => Fragment.byId(oView.getId(), sId).getValue();
            const getKey = (sId) => Fragment.byId(oView.getId(), sId).getSelectedKey();

            const oPayload = {
                name: getVal("ruleNameInput"),
                target_field: getKey("targetFieldSelect"),
                condition: getKey("conditionSelect"),
                value: getVal("ruleValueInput"),
                score_impact: parseInt(getVal("ruleScoreInput"), 10),
                feedback_message: getVal("ruleFeedbackInput"),
                description: "Manually created rule"
            };

            try {
                const response = await fetch(`/api/v1/rulesets/${this._rulesetId}/rules`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify([oPayload]) // API expects an array
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `Request failed with status ${response.status}`);
                }

                MessageBox.success("Rule created successfully!");
                this.onCloseCreateRuleDialog();
                this._loadRules(); // Refresh the table

            } catch (error) {
                MessageBox.error(`Failed to create rule: ${error.message}`);
            }
        },

        onDeleteRule: function(oEvent) {
            MessageBox.information("Deleting a rule is not yet implemented.");
        }

    });
});
