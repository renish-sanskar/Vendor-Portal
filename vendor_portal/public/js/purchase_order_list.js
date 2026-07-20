// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt
//
// purchase_order_list.js — loaded ONLY on the Purchase Order list view
// via doctype_list_js.
//
// NOTE: vendor_portal.bundle.js (loaded on every page via app_include_js)
// sets add_fields, get_indicator, and wraps onload FIRST.
// This file must NOT re-declare add_fields or get_indicator — doing so
// would overwrite the bundle's definitions because doctype_list_js loads
// after app_include_js.
//
// This file's only job: add the "Supplier Comparison" menu item.

frappe.listview_settings["Purchase Order"] =
	frappe.listview_settings["Purchase Order"] || {};

// Preserve whatever onload the bundle (or ERPNext core) already set.
var _orig_po_list_onload =
	frappe.listview_settings["Purchase Order"].onload;

frappe.listview_settings["Purchase Order"].onload = function (listview) {
	if (_orig_po_list_onload) {
		_orig_po_list_onload.call(this, listview);
	}

	// ── Supplier Comparison button ───────────────────────────────────
	listview.page.add_menu_item(__("Supplier Comparison"), function () {
		open_supplier_comparison_dialog();
	});
};
