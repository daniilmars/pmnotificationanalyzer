sap.ui.define([], function () {
    "use strict";
    return {
        formatIssues: function (aIssues) {
            if (aIssues && Array.isArray(aIssues)) {
                // Wandelt das Array in einen String um, wobei jedes Element in einer neuen Zeile steht.
                return aIssues.join("\n");
            }
            return "";
        }
    };
});
