// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

/**
 * open_supplier_comparison_dialog
 *
 * Opens an interactive dialog where the user selects an item and sees a
 * side-by-side comparison of all suppliers with pricing history, rating,
 * delivery score, and Supplier Scorecard data.
 *
 * Usage:
 *   open_supplier_comparison_dialog();                     // standalone
 *   open_supplier_comparison_dialog("ITEM-001");           // with item pre-filled
 *   open_supplier_comparison_dialog("ITEM-001", 50);       // with item + qty
 */
var open_supplier_comparison_dialog = function (item_code, qty) {
	// ── Dialog fields ─────────────────────────────────────────────────
	var dlg = new frappe.ui.Dialog({
		title: __("Supplier Comparison Matrix"),
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
				default: qty || 1,
				description: __("Used to estimate total cost per supplier"),
			},
			{
				fieldname: "results_section",
				fieldtype: "Section Break",
				label: __("Comparison Results"),
				collapsible: 0,
			},
			{
				fieldname: "results_html",
				fieldtype: "HTML",
				label: __("Results"),
			},
		],
		primary_action_label: __("Compare"),
		primary_action: function (values) {
			if (!values.item_code) {
				frappe.msgprint(__("Please select an item."));
				return;
			}
			_load_comparison(values.item_code, values.qty || 1, dlg);
		},
	});

	// Update title to show item name when selected
	dlg.fields_dict.item_code.$input.on("change", function () {
		var val = $(this).val();
		if (val) {
			frappe.db
				.get_value("Item", val, "item_name")
				.then(function (r) {
					if (r && r.message) {
						dlg.set_title(
							__("Supplier Comparison: {0}", [r.message.item_name])
						);
					}
				});
		}
	});

	// Auto-trigger comparison if item_code was passed in
	if (item_code) {
		setTimeout(function () {
			_load_comparison(item_code, qty || 1, dlg);
		}, 500);
	}

	dlg.show();
};

/**
 * _load_comparison
 *
 * Fetches the supplier comparison data and renders the results table
 * inside the dialog.  Called by the primary action (Compare button).
 */
function _load_comparison(item_code, qty, dlg) {
	dlg.set_value(
		"results_html",
		`<div class="text-muted text-center" style="padding: 40px;">
			${__("Loading comparison data...")}
		</div>`
	);

	frappe
		.xcall(
			"vendor_portal.vendor_portal.vendor_portal.api.supplier_comparison.get_supplier_comparison",
			{
				item_code: item_code,
				qty: qty,
			}
		)
		.then(function (suppliers) {
			if (!suppliers || !suppliers.length) {
				dlg.set_value(
					"results_html",
					`<div class="text-muted text-center" style="padding: 40px;">
						${__("No suppliers found for item {0}.", [item_code])}
					</div>`
				);
				return;
			}
			_render_results(dlg, suppliers, qty);
		})
		.catch(function () {
			dlg.set_value(
				"results_html",
				`<div class="text-danger text-center" style="padding: 40px;">
					${__("Failed to load comparison data.")}
				</div>`
			);
		});
}

/**
 * _render_results
 *
 * Builds the HTML comparison table and inserts it into the dialog.
 */
function _render_results(dlg, suppliers, qty) {
	var rows = suppliers
		.map(function (s, i) {
			var scorecard_color = _indicator_bg(s.scorecard_color);
			var scorecard_badge = s.scorecard_status
				? `<span class="indicator-pill whitespace-nowrap ${s.scorecard_color || ''}"
				     style="background: ${scorecard_color}; color: #fff; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;">
				      ${frappe.utils.escape_html(s.scorecard_status)}
				     </span>
				     <span style="font-weight: 600; margin-left: 4px;">
				      ${s.scorecard_score != null ? s.scorecard_score.toFixed(1) : "—"}
				     </span>`
				: `<span class="text-muted">${__("No scorecard")}</span>`;

			var rating_stars = "";
			if (s.custom_rating != null && s.custom_rating > 0) {
				var full = Math.round(s.custom_rating);
				rating_stars =
					"★".repeat(Math.min(full, 5)) +
					"☆".repeat(Math.max(5 - full, 0));
			} else {
				rating_stars = "☆☆☆☆☆";
			}

			var rate_history = "";
			if (s.rate_history && s.rate_history.length) {
				rate_history = s.rate_history
					.map(function (rh) {
						return `<div style="font-size: 10px; line-height: 1.5;">
							<span class="text-muted">${frappe.datetime.str_to_user(rh.date)}</span>
							<span style="float: right; font-weight: 600;">${format_currency(rh.rate)}</span>
						</div>`;
					})
					.join("");
			} else {
				rate_history = `<span class="text-muted">${__("N/A")}</span>`;
			}

			// Highlight the best supplier (first row, sorted by scorecard desc)
			var row_class = i === 0 ? "comparison-best-row" : "";

			return `<tr class="${row_class}">
				<td>
					<strong>
						<a href="/app/supplier/${frappe.utils.escape_html(s.supplier)}"
						   target="_blank"
						   style="color: var(--text-color);">
							${frappe.utils.escape_html(s.supplier_name || s.supplier)}
						</a>
					</strong>
					<div class="text-muted" style="font-size: 10px;">
						${frappe.utils.escape_html(s.vendor_category || __("Uncategorized"))}
					</div>
				</td>
				<td style="text-align: center;">${scorecard_badge}</td>
				<td style="text-align: center;">
					<div style="color: #eab308; letter-spacing: 2px; font-size: 13px;">
						${rating_stars}
					</div>
				</td>
				<td style="text-align: right;">
					<div style="font-weight: 600;">${s.last_rate != null ? format_currency(s.last_rate) : "—"}</div>
					<div class="text-muted" style="font-size: 10px;">
						${__("Avg:")} ${s.avg_rate != null ? format_currency(s.avg_rate) : "—"}
					</div>
				</td>
				<td style="text-align: right;">
					${rate_history}
				</td>
				<td style="text-align: center;">
					<div style="font-weight: 600;">${s.delivery_score != null ? s.delivery_score.toFixed(1) : "—"}</div>
					<div class="text-muted" style="font-size: 10px;">
						${s.on_time_pct != null ? (s.on_time_pct.toFixed(0) + "% on-time") : ""}
					</div>
				</td>
				<td style="text-align: center;">
					${s.quality_score != null ? s.quality_score.toFixed(1) : "—"}
				</td>
				<td style="text-align: right;">
					<div>${s.total_supplied_qty || 0}</div>
					<div class="text-muted" style="font-size: 10px;">${s.total_pos || 0} ${__("POs")}</div>
				</td>
			</tr>`;
		})
		.join("");

	var html = `
		<div style="overflow-x: auto; max-height: 500px; overflow-y: auto;">
			<table class="table table-bordered table-hover comparison-table" style="font-size: 12px; margin-bottom: 0;">
				<thead>
					<tr style="background: var(--control-bg);">
						<th style="min-width: 160px;">${__("Supplier")}</th>
						<th style="min-width: 130px; text-align: center;">${__("Scorecard")}</th>
						<th style="min-width: 100px; text-align: center;">${__("Rating")}</th>
						<th style="min-width: 110px; text-align: right;">${__("Pricing")}</th>
						<th style="min-width: 150px; text-align: right;">${__("Price History")}</th>
						<th style="min-width: 100px; text-align: center;">${__("Delivery")}</th>
						<th style="min-width: 80px; text-align: center;">${__("Quality")}</th>
						<th style="min-width: 80px; text-align: right;">${__("Volume")}</th>
					</tr>
				</thead>
				<tbody>
					${rows}
				</tbody>
			</table>
		</div>
	`;

	dlg.set_value("results_html", html);
}

/**
 * _indicator_bg
 *
 * Maps Supplier Scorecard indicator_color names to hex backgrounds.
 */
function _indicator_bg(color_name) {
	var map = {
		Red: "#ef4444",
		Yellow: "#eab308",
		Green: "#22c55e",
		Blue: "#3b82f6",
	};
	return map[color_name] || "#94a3b8";
}
