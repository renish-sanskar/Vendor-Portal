// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vendor Rating Log", {
	refresh(frm) {
		frm.toggle_display("naming_series", false);
	},
});
