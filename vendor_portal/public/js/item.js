// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

frappe.ui.form.on("Item", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		frm.add_custom_button(
			__("Compare Suppliers"),
			function () {
				// Pass the item code via route_options so the comparison
				// page can auto-select it and run the comparison immediately.
				frappe.route_options = { item_code: frm.doc.name };
				frappe.set_route("vendor-comparison");
			},
			__("Actions"),
		);
	},
});
