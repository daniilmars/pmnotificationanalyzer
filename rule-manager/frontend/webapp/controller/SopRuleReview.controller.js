sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox"
], function (BaseController, JSONModel, MessageBox) {
    "use strict";
    return BaseController.extend("com.sap.pm.rulemanager.controller.SopRuleReview", {

        onInit: function () {
            this.getRouter().getRoute("review").attachPatternMatched(this._onObjectMatched, this);
        },

        _onObjectMatched: function (oEvent) {
            const oArgs = oEvent.getParameter("arguments");
            this._rulesetId = oArgs.rulesetId;
            const aSuggestedRules = JSON.parse(decodeURIComponent(oArgs.suggestedRules));

            aSuggestedRules.forEach(oRule => oRule.review_status = 'pending');

            const oModel = new JSONModel(aSuggestedRules);
            this.getView().setModel(oModel, "suggestions");
        },

        onNavBack: function() {
            this.getRouter().navTo("dashboard", {}, true);
        },

        onApprove: function(oEvent) {
            const oBindingContext = oEvent.getSource().getBindingContext("suggestions");
            oBindingContext.getModel().setProperty(oBindingContext.getPath() + "/review_status", "approved");
        },

        onReject: function(oEvent) {
            const oBindingContext = oEvent.getSource().getBindingContext("suggestions");
            oBindingContext.getModel().setProperty(oBindingContext.getPath() + "/review_status", "rejected");
        },

        onAddApprovedRules: async function() {
            const oSuggestionsModel = this.getView().getModel("suggestions");
            const aAllRules = oSuggestionsModel.getData();
            const aApprovedRules = aAllRules.filter(oRule => oRule.review_status === 'approved');

            if (aApprovedRules.length === 0) {
                MessageBox.information("No rules have been approved.");
                return;
            }

            // The backend expects an array of rule objects
            const oPayload = aApprovedRules.map(oRule => {
                return {
                    name: oRule.rule_name,
                    description: oRule.source_text,
                    target_field: oRule.target_field,
                    condition: oRule.condition,
                    value: oRule.value,
                    score_impact: -10, // Default score impact
                    feedback_message: oRule.feedback_message
                };
            });

            try {
                const response = await fetch(`/api/v1/rulesets/${this._rulesetId}/rules`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(oPayload)
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `Request failed with status ${response.status}`);
                }

                MessageBox.success(`${aApprovedRules.length} rules added successfully to the ruleset!`, {
                    onClose: () => this.onNavBack()
                });

            } catch (error) {
                MessageBox.error(`Failed to add rules: ${error.message}`);
            }
        }

    });
});
