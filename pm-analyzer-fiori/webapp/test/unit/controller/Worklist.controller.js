/*global QUnit*/

sap.ui.define([
	"com/sap/pm/pmanalyzerfiori/controller/Worklist.controller"
], function (Controller) {
	"use strict";

	QUnit.module("Worklist Controller");

	QUnit.test("I should test the Worklist controller", function (assert) {
		var oAppController = new Controller();
		oAppController.onInit();
		assert.ok(oAppController);
	});

});
