sap.ui.define([
    "./BaseController",
    "sap/ui/model/json/JSONModel",
    "sap/ui/core/routing/History",
    "sap/m/MessageBox",
    "../model/formatter"
], function (BaseController, JSONModel, History, MessageBox, formatter) {
    "use strict";

    return BaseController.extend("com.sap.pm.pmanalyzerfiori.controller.Object", {

        formatter: formatter,

        onInit: function () {
            // Initialize default model to prevent binding errors
            this.getView().setModel(new JSONModel({}), "object"); // Named model
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

        onToggleSideContent: function (oEvent) {
            const oDynamicSideContent = this.byId("DynamicSideContent");
            // Toggle the showSideContent property
            const bCurrentState = oDynamicSideContent.getShowSideContent();
            oDynamicSideContent.setShowSideContent(!bCurrentState);
            
            // Update button text/icon state if needed (optional, but good UX)
            const oButton = oEvent.getSource();
            if (bCurrentState) { // if it was true, now false (hidden)
                 oButton.setType("Default");
            } else {
                 oButton.setType("Emphasized");
            }
        },

        _onObjectMatched: async function (oEvent) {
            const sNotificationId = oEvent.getParameter("arguments").notificationId;
            const oUiModel = this.getOwnerComponent().getModel("ui");
            oUiModel.setProperty("/isBusy", true);

            try {
                const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                const response = await fetch(`/api/notifications/${sNotificationId}?language=${sLanguage}`);
                
                if (!response.ok) {
                    this.getRouter().navTo("worklist");
                    return;
                }
                const data = await response.json();

                // Set data to the named model "object"
                this.getView().getModel("object").setData(data);
                
                this._buildTimelines(data);
                this._triggerAnalysis(data); 

            } catch (error) {
                MessageBox.error("Failed to load object details: " + error.message);
            } finally {
                oUiModel.setProperty("/isBusy", false);
            }
        },

        _buildTimelines: function (oNotification) {
            const oTimelineModel = this.getView().getModel("timeline");
            const oResourceBundle = this.getResourceBundle();

            let sNotifStatus = "OSDN"; 
            if (oNotification.NotificationType === "M1") sNotifStatus = "REL"; 

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
                let sOrderStatus = "REL"; 

                const oOrderTimelineData = this._createTimelineData(
                    ["OSDN", "REL", "TECO", "CLSD"], 
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
            // Retrieve from Named Model
            const oNotification = this.getView().getModel("object").getData();
            const sModifiedLongText = this.getView().byId("longTextForAnalysis").getValue();
            
            const oNotificationCopy = JSON.parse(JSON.stringify(oNotification));
            oNotificationCopy.LongText = sModifiedLongText;

            this._triggerAnalysis(oNotificationCopy);
        },

        _addMessageToChat: function (sText, sAuthor) {
            const oChatModel = this.getView().getModel("chat");
            const aMessages = oChatModel.getProperty("/messages");
            aMessages.push({ text: sText, author: sAuthor });
            oChatModel.setProperty("/messages", aMessages);
            
            const oScrollContainer = this.byId("chatScrollContainer");
            setTimeout(() => {
                if (oScrollContainer) {
                    oScrollContainer.scrollTo(0, 10000, 0);
                }
            }, 0);
        },

        onPostChatMessage: async function (oEvent) {
            const sQuestion = oEvent.getParameter("value");
            if (!sQuestion) {
                return;
            }

            this._addMessageToChat(sQuestion, "user");
            this.getView().setBusy(true);

            try {
                // Retrieve from Named Model
                const oNotification = this.getView().getModel("object").getData();
                const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                const oAnalysis = this.getView().getModel("analysis").getData();

                const oPayload = {
                    language: sLanguage,
                    question: sQuestion,
                    notification: oNotification,
                    analysis: {
                        score: oAnalysis.score,
                        problems: oAnalysis.problems,
                        summary: oAnalysis.summary
                    }
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
        },
        
        onProblemPress: function (oEvent) {
             const sFieldId = oEvent.getSource().data("field");
             const oIconTabBar = this.byId("iconTabBar");
             let oTargetControl;
             let sTargetTabKey;
 
             switch (sFieldId) {
                 case "DESCRIPTION":
                     sTargetTabKey = "notification";
                     oTargetControl = this.byId("notificationDetailsVBox"); 
                     break;
                 case "LONG_TEXT":
                     // In new layout, this is in side content, always visible if open.
                     // Focus the text area
                     oTargetControl = this.byId("longTextForAnalysis");
                     // Ensure side content is open
                     const oDSC = this.byId("DynamicSideContent");
                     if (!oDSC.getShowSideContent()) {
                         oDSC.setShowSideContent(true);
                     }
                     break;
                 case "DAMAGE_CODE":
                 case "CAUSE_CODE":
                     sTargetTabKey = "notification";
                     oTargetControl = this.byId("codesForm");
                     break;
                 case "WORK_ORDER_DESCRIPTION":
                     sTargetTabKey = "workOrder";
                     oTargetControl = this.byId("workOrderDetailsForm"); 
                     break;
                 default: 
                     // General issue
                     break;
             }
 
             if (sTargetTabKey && oIconTabBar.getSelectedKey() !== sTargetTabKey) {
                 oIconTabBar.setSelectedKey(sTargetTabKey);
             }
 
             setTimeout(() => {
                 if (oTargetControl) {
                     const oDomRef = oTargetControl.getDomRef();
                     if (oDomRef) {
                         oDomRef.scrollIntoView({ behavior: "smooth", block: "center" });
     
                         oDomRef.classList.add("highlighted-field");
                         oDomRef.addEventListener("animationend", () => {
                             oDomRef.classList.remove("highlighted-field");
                         });
     
                         if (oTargetControl.focus) {
                             setTimeout(() => oTargetControl.focus(), 300);
                         }
                     }
                 }
             }, 300); 
        }
    });
});