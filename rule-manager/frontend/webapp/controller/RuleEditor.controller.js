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

            const oViewModel = new JSONModel({
                isValidationRule: true,
                isEditMode: false,
                isDraft: false
            });
            this.getView().setModel(oViewModel, "viewModel");
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
                console.log("Rules data received from backend:", data.rules);
                this.getView().getModel("rules").setData(data.rules);
                this.getView().getModel("viewModel").setProperty("/isDraft", data.status === "Draft");
            } catch (error) {
                MessageBox.error(error.message);
            }
        },

        onNavBack: function() {
            this.getRouter().navTo("dashboard", {}, true);
        },

        _openCreateRuleDialog: function(oRuleData) {
            var oView = this.getView();

            const openDialog = (oDialog) => {
                this.getView().getModel("viewModel").setProperty("/isEditMode", !!oRuleData);
                if (oRuleData) {
                    const setVal = (sId, sVal) => Fragment.byId(oView.getId(), sId).setValue(sVal);
                    const setKey = (sId, sKey) => Fragment.byId(oView.getId(), sId).setSelectedKey(sKey);
                    setVal("ruleNameInput", oRuleData.name);
                    setVal("ruleDescriptionInput", oRuleData.description);
                    setKey("ruleTypeSelect", oRuleData.rule_type);
                    this.getView().getModel("viewModel").setProperty("/isValidationRule", oRuleData.rule_type === "VALIDATION");
                    if (oRuleData.rule_type === "VALIDATION") {
                        setKey("targetFieldSelect", oRuleData.target_field);
                        setKey("conditionSelect", oRuleData.condition);
                        setVal("ruleValueInput", oRuleData.value);
                        setVal("ruleScoreInput", oRuleData.score_impact);
                        setVal("ruleFeedbackInput", oRuleData.feedback_message);
                    }
                    this._editingRuleId = oRuleData.id;
                } else {
                    // Reset fields for creation
                }
                oDialog.open();
            };

            if (!this._oCreateRuleDialog) {
                Fragment.load({
                    id: oView.getId(),
                    name: "com.sap.pm.rulemanager.view.CreateRuleDialog",
                    controller: this
                }).then(function (oDialog) {
                    oView.addDependent(oDialog);
                    this._oCreateRuleDialog = oDialog;
                    openDialog(oDialog);
                }.bind(this));
            } else {
                openDialog(this._oCreateRuleDialog);
            }
        },

        onCreateRule: function() {
            this._openCreateRuleDialog();
        },

        onEditRule: function(oEvent) {
            const oRule = oEvent.getSource().getBindingContext("rules").getObject();
            this._openCreateRuleDialog(oRule);
        },

        onRuleTypeChange: function(oEvent) {
            const sSelectedKey = oEvent.getParameter("selectedItem").getKey();
            this.getView().getModel("viewModel").setProperty("/isValidationRule", sSelectedKey === "VALIDATION");
        },

        onCloseCreateRuleDialog: function() {
            this._oCreateRuleDialog.close();
        },

        onSaveRule: async function() {
            const bIsEditMode = this.getView().getModel("viewModel").getProperty("/isEditMode");
            if (bIsEditMode) {
                this._updateRule();
            } else {
                this._createRule();
            }
        },

        _createRule: async function() {
            const oView = this.getView();
            const getVal = (sId) => Fragment.byId(oView.getId(), sId).getValue();
            const getKey = (sId) => Fragment.byId(oView.getId(), sId).getSelectedKey();
            const sRuleType = getKey("ruleTypeSelect");
            const oPayload = { name: getVal("ruleNameInput"), description: getVal("ruleDescriptionInput"), rule_type: sRuleType };

            if (sRuleType === 'VALIDATION') {
                oPayload.target_field = getKey("targetFieldSelect");
                oPayload.condition = getKey("conditionSelect");
                oPayload.value = getVal("ruleValueInput");
                oPayload.score_impact = parseInt(getVal("ruleScoreInput"), 10);
                oPayload.feedback_message = getVal("ruleFeedbackInput");
            } else { Object.assign(oPayload, {target_field: 'N/A', condition: 'N/A', value: '', score_impact: 0, feedback_message: ''}); }

            try {
                const response = await fetch(`/api/v1/rulesets/${this._rulesetId}/rules`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify([oPayload]) });
                if (!response.ok) { throw new Error((await response.json()).error || `Request failed with status ${response.status}`); }
                MessageBox.success("Rule created successfully!");
                this.onCloseCreateRuleDialog();
                this._loadRules();
            } catch (error) { MessageBox.error(`Failed to create rule: ${error.message}`); }
        },

        _updateRule: async function() {
            const oView = this.getView();
            const getVal = (sId) => Fragment.byId(oView.getId(), sId).getValue();
            const getKey = (sId) => Fragment.byId(oView.getId(), sId).getSelectedKey();
            const sRuleType = getKey("ruleTypeSelect");
            const oPayload = { name: getVal("ruleNameInput"), description: getVal("ruleDescriptionInput"), rule_type: sRuleType };

            if (sRuleType === 'VALIDATION') {
                oPayload.target_field = getKey("targetFieldSelect");
                oPayload.condition = getKey("conditionSelect");
                oPayload.value = getVal("ruleValueInput");
                oPayload.score_impact = parseInt(getVal("ruleScoreInput"), 10);
                oPayload.feedback_message = getVal("ruleFeedbackInput");
            } else { Object.assign(oPayload, {target_field: 'N/A', condition: 'N/A', value: '', score_impact: 0, feedback_message: ''}); }

            try {
                const response = await fetch(`/api/v1/rules/${this._editingRuleId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(oPayload) });
                if (!response.ok) { throw new Error((await response.json()).error || `Request failed with status ${response.status}`); }
                MessageBox.success("Rule updated successfully!");
                this.onCloseCreateRuleDialog();
                this._loadRules();
            } catch (error) { MessageBox.error(`Failed to update rule: ${error.message}`); }
        },

        onDeleteRule: async function(oEvent) {
            const oRule = oEvent.getSource().getBindingContext("rules").getObject();
            
            MessageBox.confirm(`Are you sure you want to delete the rule: "${oRule.name}"?`, {
                onClose: async (sAction) => {
                    if (sAction === MessageBox.Action.OK) {
                        try {
                            const response = await fetch(`/api/v1/rules/${oRule.id}`, { method: "DELETE" });
                            if (!response.ok) {
                                const errorData = await response.json();
                                throw new Error(errorData.error || `Request failed with status ${response.status}`);
                            }
                            MessageBox.success("Rule deleted successfully!");
                            this._loadRules();
                        } catch (error) {
                            MessageBox.error(`Failed to delete rule: ${error.message}`);
                        }
                    }
                }
            });
        }

    });
});
