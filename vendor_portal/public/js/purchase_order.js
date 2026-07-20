// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order", {
	/**
	 * Refresh — runs on every form load / refresh.
	 * Adds custom buttons, sets up supplier info display, and checks
	 * blacklist state on refresh to keep the UI in sync.
	 */
	refresh(frm) {
		_add_action_buttons(frm);
		_supplier_changed(frm);
	},

	/**
	 * supplier — runs when the supplier field value changes.
	 * Fetches vendor info and shows warnings / disables buttons if
	 * the supplier is blacklisted.
	 */
	supplier(frm) {
		_supplier_changed(frm);
	},
});

// ---------------------------------------------------------------------------
// Event handler: supplier change / refresh
// ---------------------------------------------------------------------------

function _supplier_changed(frm) {
	const supplier = frm.doc.supplier;
	if (!supplier) {
		frm.dashboard.clear_headline();
		return;
	}

	Promise.all([
		frappe.db.get_value(
			"Supplier",
			supplier,
			[
				"custom_vendor_category",
				"custom_vendor_rating",
				"custom_total_rating_count",
				"custom_is_blacklisted",
				"custom_blacklist_reason",
			],
		),
		frappe.db.get_list("Supplier Scorecard", {
			filters: { supplier: supplier },
			fields: ["supplier_score", "status", "indicator_color"],
			limit: 1,
		}),
	])
		.then(([r, scorecards]) => {
			if (!r || !r.message) return;

			const { message } = r;
			const is_blacklisted = message.custom_is_blacklisted;
			const scorecard = (scorecards || [])[0] || null;

			frm.dashboard.clear_headline();

			if (is_blacklisted) {
				frm.dashboard.set_headline(
					`<span class="indicator-pill red">⚠️ ${__("WARNING: This supplier is blacklisted!")}</span>`,
				);
			} else {
				const rating = message.custom_vendor_rating != null
					? (message.custom_vendor_rating * 5).toFixed(1)
					: "N/A";
				const category = message.custom_vendor_category || "N/A";
				const count = message.custom_total_rating_count ?? 0;

				let sc_badge = "";
				if (scorecard) {
					const color_map = {
						Red: "#ef4444",
						Yellow: "#eab308",
						Green: "#22c55e",
						Blue: "#3b82f6",
					};
					const bg = color_map[scorecard.indicator_color] || "#94a3b8";
					sc_badge = ` | ${__("Scorecard")}: <span style="display:inline-block;padding:1px 8px;border-radius:8px;color:#fff;background:${bg};font-size:11px;font-weight:600;">${scorecard.status || ""}</span> <strong>${scorecard.supplier_score || "---"}</strong>`;
				}

				frm.dashboard.set_headline(
					`${__("Vendor Category")}: <strong>${category}</strong> | ${__("Rating")}: <strong>${rating}</strong> | ${__("Total Ratings")}: <strong>${count}</strong>${sc_badge}`,
				);
			}

			// Disable Save / Submit if blacklisted
			if (is_blacklisted) {
				frm.disable_save();
			} else {
				frm.enable_save();
			}
		});
}

// ---------------------------------------------------------------------------
// Custom action buttons
// ---------------------------------------------------------------------------

function _add_action_buttons(frm) {
	// "View Vendor Rating History" — always visible in Actions menu
	frm.add_custom_button(
		__("View Vendor Rating History"),
		() => _show_rating_history(frm),
		__("Actions"),
	);

	// "View Supplier Scorecard" — navigate to the scorecard if it exists
	frm.add_custom_button(
		__("View Supplier Scorecard"),
		() => _open_supplier_scorecard(frm),
		__("Actions"),
	);

	// "Rate This Supplier" — only visible when the document is submitted
	if (frm.doc.docstatus === 1) {
		frm.add_custom_button(
			__("Rate This Supplier"),
			() => _show_rate_supplier_dialog(frm),
			__("Actions"),
		);
	}
}

function _open_supplier_scorecard(frm) {
	if (!frm.doc.supplier) {
		frappe.msgprint(__("Please select a supplier first."));
		return;
	}

	frappe.db.get_list("Supplier Scorecard", {
		filters: { supplier: frm.doc.supplier },
		fields: ["name"],
		limit: 1,
	}).then(rows => {
		if (rows && rows.length) {
			frappe.set_route("Form", "Supplier Scorecard", rows[0].name);
		} else {
			frappe.confirm(
				__("No scorecard exists for this supplier yet. Would you like to create one?"),
				() => {
					frappe.new_doc("Supplier Scorecard", {
						supplier: frm.doc.supplier,
					});
				}
			);
		}
	});
}

// ---------------------------------------------------------------------------
// Dialog 1: Vendor Rating History
// ---------------------------------------------------------------------------

function _show_rating_history(frm) {
	if (!frm.doc.supplier) {
		frappe.msgprint(__("Please select a supplier first."));
		return;
	}

	const dlg = new frappe.ui.Dialog({
		title: __("Vendor Rating History"),
		size: "large",
		fields: [
			{
				fieldname: "history_html",
				fieldtype: "HTML",
				label: __("Rating History"),
			},
		],
		primary_action_label: __("Close"),
		primary_action() {
			dlg.hide();
		},
	});

	dlg.show();
	dlg.get_primary_btn().text(__("Close"));

	dlg.set_value(
		"history_html",
		`<p class="text-muted">${__("Loading...")}</p>`,
	);

	frappe
		.call({
			method: "vendor_portal.vendor_portal.api.get_vendor_rating_history",
			args: { supplier: frm.doc.supplier },
		})
		.then((r) => {
			const records = r.message || [];
			if (!records.length) {
				dlg.set_value(
					"history_html",
					`<p class="text-muted">${__("No rating history found for this supplier.")}</p>`,
				);
				return;
			}

			const rows = records
				.map(
					(row) =>
						`<tr>
							<td>${frappe.datetime.str_to_user(row.rating_date) || row.creation || ""}</td>
							<td>${frappe.utils.escape_html(row.rating_type || "")}</td>
							<td>${row.score != null ? row.score : ""}</td>
							<td>${frappe.utils.escape_html(row.remarks || "")}</td>
						</tr>`,
				)
				.join("");

			dlg.set_value(
				"history_html",
				`<div style="max-height:400px;overflow-y:auto;">
					<table class="table table-bordered table-hover">
						<thead>
							<tr>
								<th>${__("Date")}</th>
								<th>${__("Rating Type")}</th>
								<th>${__("Score")}</th>
								<th>${__("Remarks")}</th>
							</tr>
						</thead>
						<tbody>${rows}</tbody>
					</table>
				</div>`,
			);
		})
		.catch(() => {
			dlg.set_value(
				"history_html",
				`<p class="text-danger">${__("Failed to load rating history.")}</p>`,
			);
		});
}

// ---------------------------------------------------------------------------
// Dialog 2: Rate Supplier
// ---------------------------------------------------------------------------

function _show_rate_supplier_dialog(frm) {
	const dlg = new frappe.ui.Dialog({
		title: __("Rate Supplier"),
		fields: [
			{
				fieldname: "rating_type",
				fieldtype: "Select",
				label: __("Rating Type"),
				reqd: 1,
				options: [
					"Delivery",
					"Quality",
					"Pricing",
					"Communication",
				],
			},
			{
				fieldname: "score",
				fieldtype: "Rating",
				label: __("Score (1–5)"),
				reqd: 1,
			},
			{
				fieldname: "remarks",
				fieldtype: "Text",
				label: __("Remarks"),
			},
		],
		primary_action_label: __("Submit"),
		primary_action(values) {
			if (!values.rating_type || values.score == null) {
				frappe.msgprint(__("Please fill in Rating Type and Score."));
				return;
			}

			// Rating fieldtype stores 0–1; convert to 1–5 scale for the API
			var score = Math.round(values.score * 5) || 1;

			frappe
				.call({
					method: "vendor_portal.vendor_portal.api.submit_vendor_rating",
					args: {
						supplier: frm.doc.supplier,
						purchase_order: frm.doc.name,
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
					frm.refresh();
				})
				.catch(() => {
					frappe.msgprint(__("Failed to submit rating. Please try again."));
				});
		},
	});

	dlg.show();
}
