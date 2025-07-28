sap.ui.define([], function () {
    "use strict";

    return {
        /**
         * Formats a date string into a locale-specific date and time (e.g., 25.07.2025, 12:00:00).
         * @param {string} sDate The date string from the JSON model.
         * @returns {string} The formatted date and time string.
         */
        formatDateTime: function (sDate) {
            if (!sDate) {
                return "";
            }
            // Use style "medium" for both date and time for a good locale-specific default
            const oDateFormat = sap.ui.core.format.DateFormat.getDateTimeInstance({
                style: "medium"
            });
            return oDateFormat.format(new Date(sDate));
        }
    };
});