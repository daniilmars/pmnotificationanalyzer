sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "../model/formatter",
    "sap/ui/core/routing/History",
    "sap/m/MessageBox"
], function (BaseController, JSONModel, formatter, History, MessageBox) {
    "use strict";

    return BaseController.extend("com.sap.pm.pmanalyzerfiori.controller.Object", {

        formatter: formatter,

        onInit: function () {
            this.getView().setModel(new JSONModel(), "timeline");
            this.getView().setModel(new JSONModel({
                busy: false,
                score: 0,
                problems: [],
                summary: ""
            }), "analysis");
            this.getView().setModel(new JSONModel({
                messages: []
            }), "chat");

            const oRouter = this.getRouter();
            oRouter.getRoute("object").attachPatternMatched(this._onObjectMatched, this);
        },

        onNavBack: function () {
            const oHistory = History.getInstance();
            const sPreviousHash = oHistory.getPreviousHash();

            if (sPreviousHash !== undefined) {
                window.history.go(-1);
            } else {
                this.getRouter().navTo("worklist", {}, true);
            }
        },

        onGoToField: function (oEvent) {
            const oProblem = oEvent.getSource().getBindingContext("analysis").getObject();
            const sFieldId = oProblem.fieldId;
            const oTargetControl = this.byId(sFieldId) || this.byId(sFieldId.replace("Display", "ForAnalysis")); // Try both display and input
            
            if (oTargetControl) {
                // Switch to the correct tab if necessary
                const sTargetTab = sFieldId.includes("Analysis") ? "analysis" : "notification";
                this.byId("iconTabBar").setSelectedKey(sTargetTab);

                // Scroll to the control
                oTargetControl.getDomRef().scrollIntoView({ behavior: "smooth", block: "center" });
                
                // Highlight the control
                this._highlightControl(oTargetControl);
            }
        },

        onSuggestImprovement: async function (oEvent) {
            const oProblem = oEvent.getSource().getBindingContext("analysis").getObject();
            const oNotification = this.getView().getBindingContext().getObject();
            const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);

            this.getView().setBusy(true);

            try {
                const oPayload = {
                    language: sLanguage,
                    problem: oProblem,
                    notification: oNotification
                };

                const response = await fetch("/api/suggest", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(oPayload)
                });

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const result = await response.json();
                
                MessageBox.confirm(result.suggestion, {
                    title: "Suggestion",
                    actions: [this.getResourceBundle().getText("suggestionApplyButtonText"), MessageBox.Action.CANCEL],
                    emphasizedAction: this.getResourceBundle().getText("suggestionApplyButtonText"),
                    onClose: function (sAction) {
                        if (sAction === this.getResourceBundle().getText("suggestionApplyButtonText")) {
                            this.byId("longTextForAnalysis").setValue(result.suggestion);
                            MessageBox.information("Suggestion applied to the 'What-If' text area. You can now re-analyze.");
                        }
                    }.bind(this)
                });

            } catch (error) {
                MessageBox.error(error.message);
            } finally {
                this.getView().setBusy(false);
            }
        },

        _highlightControl: function (oControl) {
            const $control = oControl.$();
            $control.addClass("fieldHighlight");
            setTimeout(() => {
                $control.removeClass("fieldHighlight");
            }, 2000); // Highlight for 2 seconds
        },

        _onObjectMatched: function (oEvent) {
            const sNotificationId = oEvent.getParameter("arguments").notificationId;
            const oModel = this.getOwnerComponent().getModel();

            oModel.dataLoaded().then(() => {
                const aNotifications = oModel.getProperty("/Notifications") || [];
                const iObjectIndex = aNotifications.findIndex(
                    (notif) => notif.NotificationId === sNotificationId
                );

                if (iObjectIndex !== -1) {
                    const sObjectPath = `/Notifications/${iObjectIndex}`;
                    this.getView().bindElement({ path: sObjectPath });
                    const oNotification = aNotifications[iObjectIndex];
                    this._buildTimelines(oNotification);
                    this._triggerAnalysis(oNotification); // Initial analysis
                } else {
                    this.getRouter().navTo("worklist");
                }
            });
        },

        _buildTimelines: function (oNotification) {
            const oTimelineModel = this.getView().getModel("timeline");
            const oResourceBundle = this.getResourceBundle();

            // Status mapping from German IDs to English IDs
            const oStatusIdMap = {
                "EROF": "OSDN", // Eröffnet -> Outstanding / Created
                "FREI": "REL",  // Freigegeben -> Released
                "ABGE": "NOCO", // Abgeschlossen -> Notification Closed
                "TABG": "TECO"  // Technisch Abgeschlossen -> Technically Completed
            };

            let sNotifStatus = oNotification.SystemStatus;
            // Normalize status if it's a German ID
            if (oStatusIdMap[sNotifStatus]) {
                sNotifStatus = oStatusIdMap[sNotifStatus];
            }
            
            const oNotifTimelineData = this._createTimelineData(
                ["OSDN", "REL", "NOCO"],
                [
                    oResourceBundle.getText("statusOutstanding"),
                    oResourceBundle.getText("statusReleased"),
                    oResourceBundle.getText("statusClosed")
                ],
                sNotifStatus
            );
            oTimelineModel.setProperty("/notification", oNotifTimelineData);

            if (oNotification.WorkOrder) {
                let sOrderStatus = oNotification.WorkOrder.SystemStatus;
                // Normalize status if it's a German ID
                if (oStatusIdMap[sOrderStatus]) {
                    sOrderStatus = oStatusIdMap[sOrderStatus];
                }

                const oOrderTimelineData = this._createTimelineData(
                    ["OSDN", "REL", "TECO", "CLSD"], // Using OSDN for CRTD as EROF maps to it
                    [
                        oResourceBundle.getText("statusCreated"),
                        oResourceBundle.getText("statusReleased"),
                        oResourceBundle.getText("statusTechnicallyCompleted"),
                        oResourceBundle.getText("statusBusinessClosed")
                    ],
                    sOrderStatus
                );
                oTimelineModel.setProperty("/workOrder", oOrderTimelineData);
            } else {
                oTimelineModel.setProperty("/workOrder", []);
            }
        },

        _createTimelineData: function (aStatusIds, aStatusNames, sCurrentStatusId) {
            const aSteps = [];
            const iCurrentIndex = aStatusIds.indexOf(sCurrentStatusId);

            aStatusIds.forEach((sId, i) => {
                let sStatusType = "future";
                if (i < iCurrentIndex) {
                    sStatusType = "completed";
                } else if (i === iCurrentIndex) {
                    sStatusType = "current";
                }
                aSteps.push({ text: aStatusNames[i], status: sStatusType });
            });
            return aSteps;
        },

        onReanalyze: function () {
            // Get the current notification object from the view's binding context
            const oNotification = this.getView().getBindingContext().getObject();
            // Get the potentially modified long text from the text area
            const sModifiedLongText = this.getView().byId("longTextForAnalysis").getValue();
            
            // Create a deep copy of the notification to avoid modifying the main model directly
            const oNotificationCopy = JSON.parse(JSON.stringify(oNotification));
            // Update the LongText in the copied object
            oNotificationCopy.LongText = sModifiedLongText;

            this._triggerAnalysis(oNotificationCopy);
        },

        _addMessageToChat: function (sText, sAuthor) {
            const oChatModel = this.getView().getModel("chat");
            const aMessages = oChatModel.getProperty("/messages");
            const sSender = sAuthor === "user" ? "You" : "Assistant";

            aMessages.push({ text: sText, author: sAuthor, sender: sSender });
            oChatModel.setProperty("/messages", aMessages);

            // Use a timeout to ensure the DOM is updated before we scroll
            setTimeout(() => {
                const oScrollContainer = this.byId("chatScrollContainer");
                if (oScrollContainer) {
                    // Get the underlying DOM element to find its full scrollable height
                    const oDomRef = oScrollContainer.getDomRef();
                    if (oDomRef) {
                        // Scroll to the very bottom of the container
                        oScrollContainer.scrollTo(0, oDomRef.scrollHeight);
                    }
                }
            }, 100); // A small delay is sometimes needed to wait for rendering
        },

        onPostChatMessage: async function (oEvent) {
            const sQuestion = oEvent.getParameter("value");
            if (!sQuestion) {
                return;
            }

            this._addMessageToChat(sQuestion, "user");

            // Show busy indicator for assistant response
            this.getView().setBusy(true);

            try {
                const oNotification = this.getView().getBindingContext().getObject();
                const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                const oChatModel = this.getView().getModel("chat");
                const aMessages = oChatModel.getProperty("/messages");

                // Prepare history for the backend
                const aHistory = aMessages.slice(0, -1).map(msg => { // Exclude the latest user message
                    return {
                        role: msg.author,
                        content: msg.text
                    };
                });

                const oPayload = {
                    language: sLanguage,
                    question: sQuestion,
                    notification: oNotification,
                    history: aHistory
                };

                const response = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(oPayload)
                });

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const result = await response.json();
                this._addMessageToChat(result.answer, "assistant");

            } catch (error) {
                MessageBox.error(error.message);
            } finally {
                this.getView().setBusy(false);
            }
        },

        _triggerAnalysis: async function (oNotification) {
            const oAnalysisModel = this.getView().getModel("analysis");
            oAnalysisModel.setProperty("/busy", true);

            try {
                const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                const oPayload = {
                    language: sLanguage,
                    notification: oNotification
                };

                const response = await fetch("/api/analyze", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(oPayload)
                });

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const result = await response.json();
                oAnalysisModel.setProperty("/score", result.score);
                oAnalysisModel.setProperty("/problems", result.problems);
                oAnalysisModel.setProperty("/summary", result.summary);

            } catch (error) {
                MessageBox.error(error.message);
            } finally {
                oAnalysisModel.setProperty("/busy", false);
            }
        }
    });
});
