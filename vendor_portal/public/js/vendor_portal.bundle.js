// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt
//
// vendor_portal.bundle.js — loaded via app_include_js on every page.
// Contains:
//   1. Purchase Order list view override (indicators + right-click menu)
//   2. Purchase Invoice form handler (low-rating banner)
//   3. Supplier Comparison Dialog

// ---------------------------------------------------------------------------
// A) Purchase Order List View — custom indicators & right-click menu
// ---------------------------------------------------------------------------

frappe.listview_settings["Purchase Order"] =
	frappe.listview_settings["Purchase Order"] || {};

// Fetch fields needed by the custom indicator & context menu.
// purchase_order_list.js must NOT redeclare this — it would overwrite
// these fields and break get_indicator.
frappe.listview_settings["Purchase Order"].add_fields = [
	"supplier",
	"supplier_name",
	"schedule_date",
	"per_received",
	"status",
	"docstatus",
	"base_grand_total",
	"grand_total",
];

// Custom indicator:
//   Green  → Completed / Closed (fully received or manually closed)
//   Grey   → Draft
//   Red    → Cancelled  |  Overdue (submitted, past schedule_date, not fully received)
//   Blue   → On Hold
//   Orange → To Receive (submitted, not yet overdue)
frappe.listview_settings["Purchase Order"].get_indicator = function (doc) {
	if (doc.status === "Closed" || doc.status === "Completed" || doc.per_received >= 100) {
		return [__("Completed"), "green", "status,in,Closed,Completed|per_received,>=,100"];
	}

	if (doc.docstatus === 2 || doc.status === "Cancelled") {
		return [__("Cancelled"), "red", "status,=,Cancelled"];
	}

	if (doc.docstatus === 0) {
		return [__("Draft"), "grey", "status,=,Draft"];
	}

	if (doc.status === "On Hold") {
		return [__("On Hold"), "blue", "status,=,On Hold"];
	}

	// Submitted & not fully received — check overdue
	if (doc.schedule_date && frappe.datetime.get_diff(doc.schedule_date, frappe.datetime.nowdate()) < 0) {
		return [__("Overdue"), "red", "per_received,<,100|schedule_date,<,Today"];
	}

	return [__("To Receive"), "orange", "per_received,<,100"];
};

// Preserve existing onload from the core app / ERPNext.
// purchase_order_list.js will chain onto this in turn.
var _po_orig_onload = frappe.listview_settings["Purchase Order"].onload;

frappe.listview_settings["Purchase Order"].onload = function (listview) {
	if (_po_orig_onload) {
		_po_orig_onload.call(this, listview);
	}

	// Attach right-click (contextmenu) handler to list rows
	_setup_context_menu(listview);
};

// ---------------------------------------------------------------------------
// Context menu: "Quick Rate Supplier" on right-click
// ---------------------------------------------------------------------------

function _setup_context_menu(listview) {
	const $list = $(listview.$result_area);

	$list.off("contextmenu", ".list-row-container").on("contextmenu", ".list-row-container", function (e) {
		const $row = $(this);
		const name = $row.attr("data-name") || $row.find(".list-row-check:checked").val();

		if (!name) return;

		const doc = listview.data.find((d) => d.name === name);
		if (!doc || !doc.supplier_name) return;

		e.preventDefault();
		_show_quick_rate_dialog(doc, listview);
	});
}

// ---------------------------------------------------------------------------
// Quick Rate Supplier dialog (reused by context menu)
// ---------------------------------------------------------------------------

function _show_quick_rate_dialog(doc, listview) {
	const dlg = new frappe.ui.Dialog({
		title: __("Quick Rate Supplier — {0}", [doc.supplier_name]),
		fields: [
			{
				fieldname: "supplier",
				fieldtype: "Data",
				label: __("Supplier"),
				default: doc.supplier_name,
				read_only: 1,
			},
			{
				fieldname: "purchase_order",
				fieldtype: "Data",
				label: __("Purchase Order"),
				default: doc.name,
				read_only: 1,
			},
			{
				fieldname: "rating_type",
				fieldtype: "Select",
				label: __("Rating Type"),
				reqd: 1,
				options: ["Delivery", "Quality", "Pricing", "Communication"],
			},
			{
				fieldname: "score",
				fieldtype: "Rating",
				label: __("Score (1–5)"),
				reqd: 1,
			},
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: __("Remarks"),
			},
		],
		primary_action_label: __("Submit Rating"),
		primary_action(values) {
			if (!values.rating_type || values.score == null) {
				frappe.msgprint(__("Please fill in Rating Type and Score."));
				return;
			}

			const score = Math.round(values.score * 5) || 1;

			frappe
				.call({
					method: "vendor_portal.vendor_portal.api.submit_vendor_rating",
					args: {
						supplier: doc.supplier,
						purchase_order: doc.name,
						rating_type: values.rating_type,
						score: score,
						remarks: values.remarks || "",
					},
				})
				.then(() => {
					frappe.show_alert({
						message: __("Rating submitted successfully."),
						indicator: "green",
					});
					dlg.hide();
					if (listview) listview.refresh();
				})
				.catch(() => {
					frappe.msgprint(__("Failed to submit rating. Please try again."));
				});
		},
	});

	dlg.show();
}

// ---------------------------------------------------------------------------
// B) Purchase Invoice — low-rating supplier banner on refresh
// ---------------------------------------------------------------------------

frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		_handle_low_rating_banner(frm);
	},

	supplier(frm) {
		_handle_low_rating_banner(frm);
	},
});

function _handle_low_rating_banner(frm) {
	const supplier = frm.doc.supplier;
	if (!supplier || frm.doc.__islocal) return;

	// Fetch both the supplier rating and the configured threshold in parallel.
	Promise.all([
		frappe.db.get_value("Supplier", supplier, ["custom_vendor_rating"]),
		frappe.db.get_single_value("Vendor Portal Settings", "low_rating_threshold"),
	]).then(([r, threshold]) => {
		if (!r || !r.message) return;

		const rating_raw = r.message.custom_vendor_rating;
		if (rating_raw == null) return;

		// custom_vendor_rating is stored as 0–1 (Frappe Rating fieldtype);
		// convert to 1–5 scale.
		const rating = rating_raw * 5;
		// Fall back to 3 if the setting is not configured.
		const effective_threshold = flt(threshold) > 0 ? flt(threshold) : 3;

		if (rating > 0 && rating < effective_threshold) {
			_show_low_rating_banner(frm, rating.toFixed(1));
		}
	});
}

function _show_low_rating_banner(frm, rating) {
	// Remove any previously injected banner to prevent stacking on re-refresh.
	frm.layout && frm.layout.$wrapper &&
		frm.layout.$wrapper.find(".vp-low-rating-banner").remove();

	const msg = __("Note: This supplier has a low vendor rating ({0}/5). Consider reviewing vendor performance before proceeding.", [rating]);

	// Use set_headline for the warning so it's prominently visible and
	// automatically cleared on the next refresh cycle.
	frm.dashboard.set_headline(
		`<div class="vp-low-rating-banner" style="color:#92400e;">⚠️ ${msg}</div>`,
	);
}

// ---------------------------------------------------------------------------
// C) Supplier Comparison Dialog — side-by-side matrix
// ---------------------------------------------------------------------------

/**
 * open_supplier_comparison_dialog
 *
 * Opens an interactive dialog comparing all suppliers for a given item.
 * Usage: open_supplier_comparison_dialog("ITEM-001", 50)
 */
function open_supplier_comparison_dialog(item_code, qty) {
	qty = qty || 1;

	var dlg = new frappe.ui.Dialog({
		title: item_code ? __("Supplier Comparison") : __("Supplier Comparison Matrix"),
		size: "xl",
		fields: [
			{
				fieldname: "item_code",
				fieldtype: "Link",
				options: "Item",
				label: __("Item"),
				reqd: 1,
				default: item_code || "",
			},
			{
				fieldname: "qty",
				fieldtype: "Int",
				label: __("Quantity"),
				default: qty,
			},
			{
				fieldname: "results_section",
				fieldtype: "Section Break",
				label: __("Comparison Results"),
			},
			{
				fieldname: "results_html",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Compare"),
		primary_action: function (values) {
			if (!values.item_code) {
				frappe.msgprint(__("Please select an item."));
				return;
			}
			_sc_load(values.item_code, values.qty || 1, dlg);
		},
	});

	dlg.show();

	// Auto-trigger if item was pre-filled
	if (item_code) {
		setTimeout(function () {
			_sc_load(item_code, qty, dlg);
		}, 300);
	}
}

function _sc_load(item_code, qty, dlg) {
	dlg.set_value("results_html", '<p class="text-muted text-center" style="padding: 40px;">' + __("Loading...") + "</p>");

	frappe
		.call({
			method: "vendor_portal.vendor_portal.vendor_portal.api.supplier_comparison.get_supplier_comparison",
			args: {
				item_code: item_code,
				qty: qty,
			},
		})
		.then(function (r) {
			if (!r || !r.message || !r.message.length) {
				dlg.set_value(
					"results_html",
					'<p class="text-muted text-center" style="padding: 40px;">' +
						__("No suppliers found for item {0}.", [item_code]) +
						"</p>"
				);
				return;
			}
			_sc_render(dlg, r.message);
		})
		.fail(function () {
			dlg.set_value(
				"results_html",
				'<p class="text-danger text-center" style="padding: 40px;">' +
					__("Failed to load comparison data.") +
					"</p>"
			);
		});
}

function _sc_render(dlg, suppliers) {
	const currency = frappe.boot.sysdefaults.currency;
	var rows = [];
	for (var i = 0; i < suppliers.length; i++) {
		var s = suppliers[i];

		// Scorecard badge
		var sc_html = __("No scorecard");
		if (s.scorecard_status) {
			var color_map = { Red: "#ef4444", Yellow: "#eab308", Green: "#22c55e", Blue: "#3b82f6" };
			var bg = color_map[s.scorecard_color] || "#94a3b8";
			sc_html =
				"<span style='display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:#fff;background:" +
				bg +
				"'>" +
				frappe.utils.escape_html(s.scorecard_status) +
				"</span> " +
				(s.scorecard_score != null ? s.scorecard_score.toFixed(1) : "—");
		}

		// Rating stars
		var stars_html = "☆☆☆☆☆";
		if (s.custom_rating != null && s.custom_rating > 0) {
			var full = Math.min(Math.round(s.custom_rating), 5);
			var empty = 5 - full;
			stars_html = "";
			for (var j = 0; j < full; j++) stars_html += "★";
			for (var j = 0; j < empty; j++) stars_html += "☆";
		}

		// Price history
		var ph_html = '<span class="text-muted">N/A</span>';
		if (s.rate_history && s.rate_history.length) {
			ph_html = "";
			for (var k = 0; k < s.rate_history.length; k++) {
				var rh = s.rate_history[k];
				ph_html +=
					"<div style='font-size:10px;line-height:1.5'>" +
					"<span class='text-muted'>" +
					frappe.datetime.str_to_user(rh.date) +
					"</span> " +
					"<span style='float:right;font-weight:600'>" +
					format_currency(rh.rate, currency) +
					"</span></div>";
			}
		}

		var row_class = i === 0 ? 'style="background:var(--highlight-bg,#f0f9ff);"' : "";
		rows.push(
			"<tr " +
				row_class +
				">" +
				"<td><strong>" +
				frappe.utils.escape_html(s.supplier_name || s.supplier) +
				"</strong><br><span class='text-muted' style='font-size:10px'>" +
				frappe.utils.escape_html(s.vendor_category || __("Uncategorized")) +
				"</span></td>" +
				"<td style='text-align:center'>" +
				sc_html +
				"</td>" +
				"<td style='text-align:center;color:#eab308;letter-spacing:2px;font-size:13px'>" +
				stars_html +
				"</td>" +
				"<td style='text-align:right'>" +
				"<div style='font-weight:600'>" +
				(s.last_rate != null ? format_currency(s.last_rate, currency) : "—") +
				"</div>" +
				"<div class='text-muted' style='font-size:10px'>" +
				__("Avg:") +
				" " +
				(s.avg_rate != null ? format_currency(s.avg_rate, currency) : "—") +
				"</div></td>" +
				"<td style='text-align:right'>" +
				ph_html +
				"</td>" +
				"<td style='text-align:center'>" +
				(s.delivery_score != null ? s.delivery_score.toFixed(1) : "—") +
				"</td>" +
				"<td style='text-align:center'>" +
				(s.quality_score != null ? s.quality_score.toFixed(1) : "—") +
				"</td>" +
				"<td style='text-align:right'>" +
				(s.total_supplied_qty || 0) +
				" <span class='text-muted' style='font-size:10px'>" +
				__("POs:") +
				" " +
				(s.total_pos || 0) +
				"</span></td>" +
				"</tr>"
		);
	}

	var html =
		"<div style='overflow-x:auto;max-height:500px;overflow-y:auto'>" +
		"<table class='table table-bordered table-hover' style='font-size:12px;margin-bottom:0'>" +
		"<thead><tr style='background:var(--control-bg)'>" +
		"<th style='min-width:160px'>" +
		__("Supplier") +
		"</th>" +
		"<th style='min-width:120px;text-align:center'>" +
		__("Scorecard") +
		"</th>" +
		"<th style='min-width:90px;text-align:center'>" +
		__("Rating") +
		"</th>" +
		"<th style='min-width:110px;text-align:right'>" +
		__("Pricing") +
		"</th>" +
		"<th style='min-width:140px;text-align:right'>" +
		__("Price History") +
		"</th>" +
		"<th style='min-width:80px;text-align:center'>" +
		__("Delivery") +
		"</th>" +
		"<th style='min-width:80px;text-align:center'>" +
		__("Quality") +
		"</th>" +
		"<th style='min-width:90px;text-align:right'>" +
		__("Volume") +
		"</th>" +
		"</tr></thead><tbody>" +
		rows.join("") +
		"</tbody></table></div>";

	dlg.set_value("results_html", html);
}
