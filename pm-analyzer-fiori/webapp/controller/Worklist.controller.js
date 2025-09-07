sap.ui.define([
    "sap/ui/core/mvc/Controller",
    "../model/formatter",
    "sap/ui/model/Filter",
    "sap/ui/model/FilterOperator",
    "sap/ui/model/json/JSONModel"
], function (Controller, formatter, Filter, FilterOperator, JSONModel) {
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

            this.getOwnerComponent().getModel().dataLoaded().then(this._createUniqueFilters.bind(this));
        },

        _createUniqueFilters: function() {
            const oData = this.getOwnerComponent().getModel().getData().Notifications || [];
            const oViewModel = this.getView().getModel("filters");

            // Get unique creators and add an "All" option
            const aCreatorNames = [...new Set(oData.map(item => item.CreatedByUser).filter(Boolean))];
            const aCreators = aCreatorNames.map(name => ({ key: name, text: name }));
            aCreators.unshift({ key: "", text: "(All)" });
            oViewModel.setProperty("/uniqueCreators", aCreators);

            // Get unique notification types and add an "All" option
            const oTypesMap = new Map();
            oData.forEach(item => {
                if (item.NotificationType && item.NotificationTypeText) {
                    oTypesMap.set(item.NotificationType, item.NotificationTypeText);
                }
            });
            const aTypes = Array.from(oTypesMap, ([key, text]) => ({ key: key, text: text }));
            aTypes.unshift({ key: "", text: "(All Types)" });
            oViewModel.setProperty("/uniqueTypes", aTypes);
            
            // Get unique Functional Locations and add an "All" option
            const aFuncLocNames = [...new Set(oData.map(item => item.FunctionalLocation).filter(Boolean))];
            const aFuncLocs = aFuncLocNames.map(name => ({ key: name, text: name }));
            aFuncLocs.unshift({ key: "", text: "(All)" });
            oViewModel.setProperty("/uniqueFuncLocs", aFuncLocs);

            // Get unique Equipment Numbers and add an "All" option
            const aEquipmentNumbers = [...new Set(oData.map(item => item.EquipmentNumber).filter(Boolean))];
            const aEquipments = aEquipmentNumbers.map(name => ({ key: name, text: name }));
            aEquipments.unshift({ key: "", text: "(All)" });
            oViewModel.setProperty("/uniqueEquipments", aEquipments);

            // Get unique System Statuses and add an "All" option
            const oStatusMap = new Map();
            oData.forEach(item => {
                if (item.SystemStatus && item.SystemStatusText) {
                    oStatusMap.set(item.SystemStatus, item.SystemStatusText);
                }
            });
            const aStatuses = Array.from(oStatusMap, ([key, text]) => ({ key: key, text: text }));
            aStatuses.unshift({ key: "", text: "(All Statuses)"});
            oViewModel.setProperty("/uniqueStatuses", aStatuses);
        },

        onPress: function (oEvent) {
            const oItem = oEvent.getSource();
            const oRouter = this.getOwnerComponent().getRouter();
            oRouter.navTo("object", {
                notificationId: oItem.getBindingContext().getProperty("NotificationId")
            });
        },
 
        // Removed onLogout as logout is no longer required

        onLanguageChange: function(oEvent) {
            const sLanguage = oEvent.getParameter("selectedItem").getKey();
            localStorage.setItem("appLanguage", sLanguage);
            window.location.href = window.location.pathname;
        },

        onFilterSearch: function() {
            const aFilters = [];
            const sQuery = this.byId("shortTextFilter").getValue();
            const sType = this.byId("notifTypeFilter").getSelectedKey();
            const sCreator = this.byId("creatorFilter").getSelectedKey();
            const sFuncLoc = this.byId("funcLocFilter").getSelectedKey();
            const sEquipment = this.byId("equipmentFilter").getSelectedKey();
            const sStatus = this.byId("statusFilter").getSelectedKey();

            if (sQuery) { aFilters.push(new Filter("Description", FilterOperator.Contains, sQuery)); }
            if (sType) { aFilters.push(new Filter("NotificationType", FilterOperator.EQ, sType)); }
            if (sCreator) { aFilters.push(new Filter("CreatedByUser", FilterOperator.EQ, sCreator)); }
            if (sFuncLoc) { aFilters.push(new Filter("FunctionalLocation", FilterOperator.EQ, sFuncLoc)); }
            if (sEquipment) { aFilters.push(new Filter("EquipmentNumber", FilterOperator.EQ, sEquipment)); }
            if (sStatus) { aFilters.push(new Filter("SystemStatus", FilterOperator.EQ, sStatus)); }

            const oList = this.byId("list");
            const oBinding = oList.getBinding("items");
            oBinding.filter(aFilters);
        }
    });
});
