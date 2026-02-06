sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "sap/ui/model/Filter",
    "sap/ui/model/FilterOperator",
    "sap/ui/model/json/JSONModel",
    "sap/m/MessageBox",
    "../model/formatter"
], function (Controller, Filter, FilterOperator, JSONModel, MessageBox, formatter) {
    "use strict";
    return Controller.extend("com.sap.pm.pmanalyzerfiori.controller.Worklist", {

        formatter: formatter,

        onInit: function () {
            const oLanguageSelect = this.byId("languageSelect");
            if (oLanguageSelect) {
                const sCurrentLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                oLanguageSelect.setSelectedKey(sCurrentLanguage);
            }

            const oViewModel = new JSONModel({
                uniqueCreators: [],
                uniqueTypes: [],
                uniqueFuncLocs: [],
                uniqueEquipments: [],
                uniqueStatuses: []
            });
            this.getView().setModel(oViewModel, "filters");

            // Fetch real data from the backend
            this._loadNotifications();
        },

        _loadNotifications: async function() {
            const oModel = this.getOwnerComponent().getModel();
            const oUiModel = this.getOwnerComponent().getModel("ui");
            oUiModel.setProperty("/isBusy", true);

            try {
                const sLanguage = sap.ui.getCore().getConfiguration().getLanguage().substring(0, 2);
                const response = await fetch(`/api/notifications?language=${sLanguage}`);
                if (!response.ok) {
                    throw new Error(`Failed to load notifications: ${response.statusText}`);
                }
                const data = await response.json();
                
                // Map API response "value" to "Notifications" property
                oModel.setProperty("/Notifications", data.value);
                
                // Build filters based on the new data
                this._createUniqueFilters(data.value);

            } catch (error) {
                MessageBox.error("Could not load notifications: " + error.message);
            } finally {
                oUiModel.setProperty("/isBusy", false);
            }
        },

        _createUniqueFilters: function(aData) {
            const oViewModel = this.getView().getModel("filters");

            // Helper to create filter lists
            const createFilterList = (field) => {
                const uniqueValues = [...new Set(aData.map(item => item[field]).filter(Boolean))];
                const list = uniqueValues.map(val => ({ key: val, text: val }));
                list.unshift({ key: "", text: "(All)" });
                return list;
            };

            oViewModel.setProperty("/uniqueCreators", createFilterList("CreatedByUser"));
            oViewModel.setProperty("/uniqueTypes", createFilterList("NotificationType")); // Using ID as text for now
            oViewModel.setProperty("/uniqueFuncLocs", createFilterList("FunctionalLocation"));
            oViewModel.setProperty("/uniqueEquipments", createFilterList("EquipmentNumber"));
            
            // Status logic might need adjustment if API returns text or ID
            // For now assuming simple list
             oViewModel.setProperty("/uniqueStatuses", []); // Placeholder until status logic is robust
        },

        onPress: function (oEvent) {
            const oItem = oEvent.getSource();
            const oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("object", {
                notificationId: oItem.getBindingContext().getProperty("NotificationId")
            });
        },

        onNavigateToQualityDashboard: function () {
            const oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("qualityDashboard");
        },

        onNavigateToReliabilityDashboard: function () {
            const oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("reliabilityDashboard");
        },

        onNavigateToAuditDashboard: function () {
            const oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("auditDashboard");
        },

        onLanguageChange: function(oEvent) {
            const sLanguage = oEvent.getParameter("selectedItem").getKey();
            localStorage.setItem("appLanguage", sLanguage);
            window.location.reload(); // Reload to refresh UI language
        },

        onListUpdateFinished: function (oEvent) {
            var sTitle,
                iTotalItems = oEvent.getParameter("total"),
                oTitle = this.byId("listTitle");
            if (iTotalItems) {
                sTitle = this.getView().getModel("i18n").getResourceBundle().getText("worklistTitle") + " (" + iTotalItems + ")";
            } else {
                sTitle = this.getView().getModel("i18n").getResourceBundle().getText("worklistTitle");
            }
            oTitle.setText(sTitle);
        },

        onFilterSearch: function() {
            const aFilters = [];
            const sQuery = this.byId("shortTextFilter").getValue();
            const sType = this.byId("notifTypeFilter").getSelectedKey();
            const sCreator = this.byId("creatorFilter").getSelectedKey();
            const sFuncLoc = this.byId("funcLocFilter").getSelectedKey();
            const sEquipment = this.byId("equipmentFilter").getSelectedKey();
            
            if (sQuery) { aFilters.push(new Filter("Description", FilterOperator.Contains, sQuery)); }
            if (sType) { aFilters.push(new Filter("NotificationType", FilterOperator.EQ, sType)); }
            if (sCreator) { aFilters.push(new Filter("CreatedByUser", FilterOperator.EQ, sCreator)); }
            if (sFuncLoc) { aFilters.push(new Filter("FunctionalLocation", FilterOperator.EQ, sFuncLoc)); }
            if (sEquipment) { aFilters.push(new Filter("EquipmentNumber", FilterOperator.EQ, sEquipment)); }
            
            const oList = this.byId("list");
            const oBinding = oList.getBinding("items");
            oBinding.filter(aFilters);
        }
    });
});