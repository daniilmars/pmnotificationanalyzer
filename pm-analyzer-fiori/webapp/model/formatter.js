sap.ui.define([], function () {
    "use strict";

    return {
        formatDateTime: function (sDate) {
            if (!sDate) {
                return "";
            }
            // Check if it's already a JS Date object
            if (sDate instanceof Date) {
                return sDate.toLocaleDateString() + " " + sDate.toLocaleTimeString();
            }
            
            // Handle string dates (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
            // Simple parsing for now
            const oDate = new Date(sDate);
            if (isNaN(oDate.getTime())) {
                return sDate; // Return original if invalid
            }
            
            return oDate.toLocaleDateString() + " " + oDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        },

        statusState: function (sStatus) {
            switch (sStatus) {
                case "1": // Very High
                    return "Error";
                case "2": // High
                    return "Warning";
                case "3": // Medium
                    return "None";
                case "4": // Low
                    return "Success";
                default:
                    return "None";
            }
        }
    };
});
