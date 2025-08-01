const fs = require('fs-extra');
const path = require('path');

/**
 * Custom UI5 build task to delete specific Auth0 SDK files
 * that cause minification errors.
 *
 * @param {object} tree The UI5 resource tree
 * @param {object} options The task options
 * @param {object} options.log The UI5 logger
 * @returns {Promise<void>}
 */
module.exports = async function({ tree, options }) {
    options.log.info("Running custom task: deleteAuth0Files");

    const filesToDelete = [
        "webapp/libs/auth0-spa-js.production.js",
        "webapp/libs/auth0-spa-js.js"
    ];

    for (const filePath of filesToDelete) {
        const fullPath = path.join(process.cwd(), filePath);
        try {
            if (await fs.pathExists(fullPath)) {
                await fs.remove(fullPath);
                options.log.info(`Successfully deleted: ${filePath}`);
            } else {
                options.log.warn(`File not found, skipping: ${filePath}`);
            }
        } catch (error) {
            options.log.error(`Failed to delete ${filePath}: ${error.message}`);
            throw error; // Re-throw to fail the build
        }
    }

    options.log.info("Finished custom task: deleteAuth0Files");
};
