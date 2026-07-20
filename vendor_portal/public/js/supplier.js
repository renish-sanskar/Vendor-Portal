// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

// Cache Vendor Portal Settings so we don't re-fetch on every form load.
let _vendor_portal_settings = null;

function _get_vendor_portal_settings() {
	if (_vendor_portal_settings) {
		return Promise.resolve(_vendor_portal_settings);
	}
	return frappe.db
		.get_single_value("Vendor Portal Settings", "low_rating_threshold")
		.then((threshold) => {
			_vendor_portal_settings = { low_rating_threshold: flt(threshold) };
			return _vendor_portal_settings;
		});
}

frappe.ui.form.on("Supplier", {
	refresh(frm) {
		if (frm.doc.__islocal) return;

		_refresh_dashboard(frm);
		_check_low_rating(frm);
		_add_action_buttons(frm);
	},
});

// ---------------------------------------------------------------------------
// Dashboard metrics
// ---------------------------------------------------------------------------

function _refresh_dashboard(frm) {
	Promise.all([
		frappe.xcall("frappe.client.get_list", {
			doctype: "Purchase Order",
			filters: { supplier: frm.doc.name, docstatus: 1 },
			fields: ["name", "grand_total"],
			limit_page_length: 0,
		}),
		frappe.xcall("frappe.client.get_list", {
			doctype: "Vendor Rating Log",
			filters: { supplier: frm.doc.name },
			fields: ["score"],
			limit_page_length: 0,
		}),
		frappe.xcall("frappe.client.get_list", {
			doctype: "Supplier Scorecard",
			filters: { supplier: frm.doc.name },
			fields: ["supplier_score", "status", "indicator_color"],
			limit_page_length: 1,
		}),
	])
		.then(([po_list, ratings, scorecards]) => {
			po_list = po_list || [];
			ratings = ratings || [];
			const scorecard = (scorecards || [])[0] || null;

			const po_count = po_list.length;
			const total_po_value = po_list.reduce(
				(s, po) => s + flt(po.grand_total),
				0,
			);

			const total_ratings = ratings.length;
			const avg_rating = ratings.length
				? (
						ratings.reduce((s, r) => s + flt(r.score), 0) /
						ratings.length
				  ).toFixed(1)
				: null;

			// Use system default currency so format_currency renders correctly.
			const currency = frappe.boot.sysdefaults.currency;
			_render_dashboard_metrics(frm, po_count, total_po_value, avg_rating, total_ratings, scorecard, currency);
		})
		.catch(() => {
			const currency = frappe.boot.sysdefaults.currency;
			_render_dashboard_metrics(frm, 0, 0, null, 0, null, currency);
		});
}

function _render_dashboard_metrics(frm, po_count, total_po_value, avg_rating, total_ratings, scorecard, currency) {
	let scorecard_html = "";
	if (scorecard) {
		let color_map = {
			Red: "#ef4444",
			Yellow: "#eab308",
			Green: "#22c55e",
			Blue: "#3b82f6",
		};
		let bg = color_map[scorecard.indicator_color] || "#94a3b8";
		scorecard_html = `
			<div>
				<div class="text-muted" style="font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">${__("Scorecard")}</div>
				<div style="font-size: 20px; font-weight: 600; margin-top: 5px; color: ${bg};">
					${scorecard.supplier_score || "---"}
				</div>
				<div style="font-size: 10px; margin-top: 2px;">
					<span style="display: inline-block; padding: 1px 6px; border-radius: 8px; color: #fff; background: ${bg}; font-size: 9px; font-weight: 600;">
						${scorecard.status || ""}
					</span>
				</div>
			</div>
		`;
	}

	let html = `
		<div style="padding: 15px; margin-bottom: 15px; border-radius: 8px; border: 1px solid var(--border-color, #d1d8dd); background-color: var(--card-bg, #ffffff); display: flex; justify-content: space-around; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
			<div>
				<div class="text-muted" style="font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">${__("Total POs")}</div>
				<div style="font-size: 20px; font-weight: 600; margin-top: 5px;">${po_count}</div>
			</div>
			<div>
				<div class="text-muted" style="font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">${__("Total PO Value")}</div>
				<div style="font-size: 20px; font-weight: 600; margin-top: 5px; color: var(--green-500, #28a745);">${format_currency(total_po_value, currency)}</div>
			</div>
			${scorecard_html}
			<div>
				<div class="text-muted" style="font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">${__("Avg Rating")}</div>
				<div style="font-size: 20px; font-weight: 600; margin-top: 5px; color: var(--orange-500, #fd7e14);">${avg_rating || "N/A"}</div>
			</div>
			<div>
				<div class="text-muted" style="font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">${__("Total Ratings")}</div>
				<div style="font-size: 20px; font-weight: 600; margin-top: 5px;">${total_ratings}</div>
			</div>
		</div>
	`;

	// Use frm.dashboard to inject the metrics section — avoids brittle DOM traversal.
	if (!frm.__metrics_section) {
		frm.__metrics_section = frm.dashboard.add_section("", __("Supplier Metrics"));
	}
	$(frm.__metrics_section).html(html);
}

// ---------------------------------------------------------------------------
// Low rating warning
// ---------------------------------------------------------------------------

function _check_low_rating(frm) {
	_get_vendor_portal_settings().then((settings) => {
		const threshold = settings.low_rating_threshold;
		// custom_vendor_rating is stored as 0–1 (Rating fieldtype);
		// convert to 1–5 scale for comparison against the threshold.
		const rating = flt(frm.doc.custom_vendor_rating) * 5;
		if (threshold > 0 && rating > 0 && rating < threshold) {
			frm.page.set_indicator(
				__("Low Rating \u2014 Review Required"),
				"orange",
			);
		}
	});
}

// ---------------------------------------------------------------------------
// Action buttons
// ---------------------------------------------------------------------------

function _add_action_buttons(frm) {
	if (frappe.user_roles.includes("Purchase Manager")) {
		const is_blacklisted = frm.doc.custom_is_blacklisted;

		if (!is_blacklisted) {
			// Show blacklist button only when supplier is not already blacklisted.
			frm.add_custom_button(__("Blacklist Supplier"), () => {
				frappe.prompt(
					{
						label: __("Reason"),
						fieldname: "reason",
						fieldtype: "Small Text",
						reqd: 1,
					},
					(values) => {
						frm.set_value("custom_is_blacklisted", 1);
						frm.set_value("custom_blacklist_reason", values.reason);
						frm.save();
					},
					__("Blacklist Supplier"),
					__("Submit"),
				);
			}, __("Actions"));
		} else {
			// Show remove-from-blacklist button when supplier is already blacklisted.
			frm.add_custom_button(__("Remove from Blacklist"), () => {
				frappe.confirm(
					__("Are you sure you want to remove this supplier from the blacklist?"),
					() => {
						frm.set_value("custom_is_blacklisted", 0);
						frm.set_value("custom_blacklist_reason", "");
						frm.save();
					},
				);
			}, __("Actions"));
		}
	}

	if (frm.doc.custom_onboarding_reference) {
		frm.add_custom_button(__("View Onboarding"), () => {
			frappe.set_route(
				"Form",
				"Vendor Onboarding",
				frm.doc.custom_onboarding_reference,
			);
		}, __("Actions"));
	}
}
