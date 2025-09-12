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
        },

        /**
         * Converts a simple Markdown string to a safe HTML string for the FormattedText control.
         * @param {string} sMarkdown The Markdown text.
         * @returns {string} The formatted HTML string.
         */
        formatMarkdownToHtml: function (sMarkdown) {
            if (!sMarkdown) {
                return "";
            }
            let sHtml = sMarkdown;

            // Escape HTML to prevent XSS, except for our own tags
            sHtml = sHtml.replace(/</g, "&lt;").replace(/>/g, "&gt;");

            // Convert **bold** to <strong>
            sHtml = sHtml.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

            // Convert * list items to <li>
            sHtml = sHtml.replace(/^\s*\*\s*(.*)/gm, "<li>$1</li>");
            // Wrap list items in <ul>
            sHtml = sHtml.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");

            // Convert newlines to <br>
            sHtml = sHtml.replace(/\n/g, "<br>");

            return sHtml;
        }
    };
});
