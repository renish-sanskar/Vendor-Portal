// Copyright (c) 2026, renish and contributors
// For license information, please see license.txt

/* ══════════════════════════════════════════════════════════════════════════
   Vendor Comparison Matrix — Interactive Frappe Page
   ══════════════════════════════════════════════════════════════════════════ */

frappe.pages["vendor-comparison"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Vendor Comparison Matrix"),
		single_column: true,
	});

	const page = wrapper.page;
	const $body = $(wrapper).find(".page-content");

	// ── Render shell ───────────────────────────────────────────────────────
	$body.html(`
		<div class="vcm-root">
			<!-- Hero search bar -->
			<div class="vcm-hero">
				<h2 class="vcm-hero-title">⚡ Vendor Comparison Matrix</h2>
				<p class="vcm-hero-subtitle">
					Select an item to instantly compare all suppliers — pricing history,
					scorecard ratings &amp; delivery performance side‑by‑side.
				</p>
				<div class="vcm-search-row">
					<div style="display:flex;flex-direction:column;flex:1;min-width:260px;">
						<div class="vcm-search-label">${__("Select Item")}</div>
						<div id="vcm-item-field-wrap" class="vcm-search-field"></div>
					</div>
					<button class="vcm-btn-compare" id="vcm-btn-compare">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
							<path d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/>
						</svg>
						${__("Compare Suppliers")}
					</button>
				</div>
			</div>

			<!-- Results area -->
			<div id="vcm-results">
				<div class="vcm-empty">
					<div class="vcm-empty-icon">📊</div>
					<h3>${__("Select an Item to Compare")}</h3>
					<p>${__("Search for any purchased item above and click Compare Suppliers to see all vendors side-by-side.")}</p>
				</div>
			</div>
		</div>
	`);

	// ── Item link field ─────────────────────────────────────────────────────
	const item_field = frappe.ui.form.make_control({
		parent: $("#vcm-item-field-wrap")[0],
		df: {
			fieldtype: "Link",
			options: "Item",
			fieldname: "item_code",
			placeholder: __("Search for an item…"),
		},
		render_input: true,
		only_input: true,
	});
	item_field.refresh();

	// ── Inject runtime styles (absolute fallback — CSS file may be cached) ──
	if (!document.getElementById("vcm-dropdown-styles")) {
		const style = document.createElement("style");
		style.id = "vcm-dropdown-styles";
		style.textContent = `
			/* VCM global awesomplete override — injected at runtime */
			ul[data-vcm-dropdown],
			#vcm-item-field-wrap .awesomplete > ul,
			.vcm-search-field .awesomplete > ul {
				background: #0f1f33 !important;
				border: 1.5px solid rgba(99,179,237,0.5) !important;
				border-radius: 14px !important;
				margin-top: 6px !important;
				padding: 6px !important;
				box-shadow: 0 24px 64px rgba(0,0,0,0.65), 0 4px 20px rgba(0,0,0,0.4) !important;
				z-index: 99999 !important;
				min-width: 440px !important;
				max-height: 380px !important;
				overflow-y: auto !important;
				overflow-x: hidden !important;
				color: white !important;
			}
			/* Each result row */
			ul[data-vcm-dropdown] > li,
			#vcm-item-field-wrap .awesomplete > ul > li,
			.vcm-search-field .awesomplete > ul > li {
				background: transparent !important;
				color: white !important;
				padding: 12px 16px !important;
				font-size: 14px !important;
				line-height: 1.5 !important;
				border-radius: 8px !important;
				border-bottom: 1px solid rgba(255,255,255,0.06) !important;
				cursor: pointer !important;
				margin: 1px 0 !important;
			}
			ul[data-vcm-dropdown] > li:last-child,
			#vcm-item-field-wrap .awesomplete > ul > li:last-child,
			.vcm-search-field .awesomplete > ul > li:last-child {
				border-bottom: none !important;
			}
			/* Force ALL child elements white — covers strong, p, small, span */
			ul[data-vcm-dropdown] > li *,
			#vcm-item-field-wrap .awesomplete > ul > li *,
			.vcm-search-field .awesomplete > ul > li * {
				color: #fff !important;
				background: transparent !important;
			}
			/* Subtitle / description (second line) — slightly dimmer */
			ul[data-vcm-dropdown] > li p,
			ul[data-vcm-dropdown] > li small,
			#vcm-item-field-wrap .awesomplete > ul > li p,
			#vcm-item-field-wrap .awesomplete > ul > li small,
			.vcm-search-field .awesomplete > ul > li p,
			.vcm-search-field .awesomplete > ul > li small {
				color: rgba(200,225,255,0.6) !important;
				font-size: 12px !important;
				margin: 2px 0 0 !important;
				display: block !important;
			}
			/* Hover & selected */
			ul[data-vcm-dropdown] > li:hover,
			ul[data-vcm-dropdown] > li[aria-selected="true"],
			#vcm-item-field-wrap .awesomplete > ul > li:hover,
			#vcm-item-field-wrap .awesomplete > ul > li[aria-selected="true"],
			.vcm-search-field .awesomplete > ul > li:hover,
			.vcm-search-field .awesomplete > ul > li[aria-selected="true"] {
				background: rgba(59,130,246,0.32) !important;
				color: #fff !important;
			}
			ul[data-vcm-dropdown] > li:hover *,
			ul[data-vcm-dropdown] > li[aria-selected="true"] *,
			#vcm-item-field-wrap .awesomplete > ul > li:hover *,
			#vcm-item-field-wrap .awesomplete > ul > li[aria-selected="true"] * {
				background: transparent !important;
				color: #fff !important;
			}
			/* Highlighted match characters */
			ul[data-vcm-dropdown] > li mark,
			#vcm-item-field-wrap .awesomplete > ul > li mark,
			.vcm-search-field .awesomplete > ul > li mark {
				background: transparent !important;
				color: #60a5fa !important;
				font-weight: 700 !important;
			}
			/* Scrollbar */
			ul[data-vcm-dropdown]::-webkit-scrollbar,
			#vcm-item-field-wrap .awesomplete > ul::-webkit-scrollbar { width: 5px; }
			ul[data-vcm-dropdown]::-webkit-scrollbar-thumb,
			#vcm-item-field-wrap .awesomplete > ul::-webkit-scrollbar-thumb {
				background: rgba(99,179,237,0.4);
				border-radius: 3px;
			}
		`;
		document.head.appendChild(style);
	}

	// ── Dropdown styling: polling approach ───────────────────────────────────
	// Frappe REUSES the same <ul> element across searches (shows/hides it),
	// so MutationObserver only fires once. Instead we poll on every input
	// event and re-apply inline !important styles on each tick.

	function _paint_dropdown() {
		const wrap = document.getElementById("vcm-item-field-wrap");
		if (!wrap) return;
		
		const input = wrap.querySelector("input");
		if (!input) return;

		// Frappe's awesomplete might append the ul to body or keep it inside wrapper
		let ul = null;
		if (input.awesomplete && input.awesomplete.ul) {
			ul = input.awesomplete.ul;
		} else {
			ul = wrap.querySelector(".awesomplete > ul");
		}
		
		if (!ul) return;

		// ── Container ───────────────────────────────────────────────────────
		const us = ul.style;
		us.setProperty("background",    "#ffffff",                                    "important");
		us.setProperty("border",        "1px solid rgba(0,0,0,0.08)",                 "important");
		us.setProperty("border-radius", "14px",                                       "important");
		us.setProperty("box-shadow",    "0 10px 25px rgba(0,0,0,0.1)",               "important");
		us.setProperty("z-index",       "99999",                                      "important");
		us.setProperty("min-width",     "440px",                                      "important");
		us.setProperty("max-height",    "380px",                                      "important");
		us.setProperty("overflow-y",    "auto",                                       "important");
		us.setProperty("overflow-x",    "hidden",                                     "important");
		us.setProperty("padding",       "6px",                                        "important");
		us.setProperty("margin-top",    "6px",                                        "important");

		// ── Each <li> row ────────────────────────────────────────────────────
		ul.querySelectorAll("li").forEach((li) => {
			const ls = li.style;
			
			// Detect if this item is selected via keyboard
			const is_selected = li.getAttribute("aria-selected") === "true";
			// Or hovered via mouse (we track this manually)
			const is_hovered = li._vcm_is_hovered;

			if (is_selected || is_hovered) {
				ls.setProperty("background", "rgba(59,130,246,0.08)", "important");
			} else {
				ls.setProperty("background", "transparent", "important");
			}

			ls.setProperty("color",        "#0f172a",                                 "important");
			ls.setProperty("padding",      "11px 16px",                              "important");
			ls.setProperty("font-size",    "14px",                                    "important");
			ls.setProperty("line-height",  "1.55",                                   "important");
			ls.setProperty("border-radius","8px",                                     "important");
			ls.setProperty("cursor",       "pointer",                                 "important");
			ls.setProperty("border-bottom","1px solid rgba(0,0,0,0.04)",              "important");

			// Force every child element to dark
			li.querySelectorAll("*").forEach((el) => {
				el.style.setProperty("color",      "#0f172a",   "important");
				el.style.setProperty("background", "transparent","important");
			});

			// Subtitle line
			li.querySelectorAll("p, small, .small").forEach((el) => {
				el.style.setProperty("color", "#64748b", "important");
				el.style.setProperty("font-size", "12px", "important");
			});

			// Bind hover once per li
			if (!li._vcm_hov) {
				li._vcm_hov = true;
				li.addEventListener("mouseenter", () => {
					li._vcm_is_hovered = true;
					li.style.setProperty("background", "rgba(59,130,246,0.08)", "important");
				});
				li.addEventListener("mouseleave", () => {
					li._vcm_is_hovered = false;
					if (li.getAttribute("aria-selected") !== "true") {
						li.style.setProperty("background", "transparent", "important");
					}
				});
			}
		});
	}

	// Poll every 50 ms while user is typing; stop 2 s after last keypress
	let _poll_timer = null;
	let _stop_timer = null;

	function _start_poll() {
		if (_poll_timer) return;
		_poll_timer = setInterval(_paint_dropdown, 50);
	}
	function _reset_stop() {
		clearTimeout(_stop_timer);
		_stop_timer = setTimeout(() => {
			clearInterval(_poll_timer);
			_poll_timer = null;
		}, 2000);
	}

	// Hook into the search input via delegation so we don't worry about DOM readiness
	$("#vcm-item-field-wrap").on("focus input keydown", "input", function () {
		_start_poll();
		_reset_stop();
	});

	// Allow Enter key to trigger compare
	$("#vcm-item-field-wrap").on("keydown", "input", function (e) {
		if (e.key === "Enter") {
			// Small delay so awesomplete can fill the input first
			setTimeout(() => $("#vcm-btn-compare").trigger("click"), 100);
		}
	});

	// ── Compare button ──────────────────────────────────────────────────────
	$("#vcm-btn-compare").on("click", function () {
		// get_value() on a standalone make_control can be stale;
		// read from the actual input element as the source of truth.
		const raw_input = $("#vcm-item-field-wrap input").val();
		const item_code = (item_field.get_value() || raw_input || "").trim();
		if (!item_code) {
			frappe.show_alert({ message: __("Please select an item first."), indicator: "orange" });
			return;
		}
		_load_comparison(item_code, $body);
	});

	// ── Store refs on wrapper for on_page_show access ────────────────────
	wrapper._vcm = { item_field, $body };

	// ── Page menu shortcuts ─────────────────────────────────────────────────
	page.add_menu_item(__("Vendor Dashboard"), () => frappe.set_route("vendor-dashboard"));
	page.add_menu_item(__("Refresh"), () => {
		const raw_input = $("#vcm-item-field-wrap input").val();
		const item_code = (item_field.get_value() || raw_input || "").trim();
		if (item_code) _load_comparison(item_code, $body);
	});
};

/* ── Auto-trigger when navigated from Item form ─────────────────────────────
   frappe.set_route("vendor-comparison") sets frappe.route_options = { item_code }
   on_page_show fires every time the page is visited (including back-nav),
   so we pick up the item code here and trigger comparison immediately.
   ─────────────────────────────────────────────────────────────────────────── */
frappe.pages["vendor-comparison"].on_page_show = function (wrapper) {
	const opts = frappe.route_options || {};
	const item_code = (opts.item_code || "").trim();

	// Clear route_options so a manual refresh doesn't re-trigger
	frappe.route_options = null;

	if (!item_code) return;

	const vcm = wrapper._vcm;
	if (!vcm) return;

	const { item_field, $body } = vcm;

	// Pre-fill the link field so the user sees what was selected
	item_field.set_value(item_code).then(() => {
		// Small delay to let the field render the value visually
		setTimeout(() => _load_comparison(item_code, $body), 80);
	});
};

/* ══════════════════════════════════════════════════════════════════════════
   Core data loader
   ══════════════════════════════════════════════════════════════════════════ */

function _load_comparison(item_code, $body) {
	const $results = $("#vcm-results");

	// Show spinner
	$results.html(`
		<div class="vcm-loading">
			<div class="vcm-spinner"></div>
			<span>${__("Fetching supplier data…")}</span>
		</div>
	`);

	frappe
		.call({
			method: "vendor_portal.vendor_portal.api.supplier_comparison.get_supplier_comparison",
			args: { item_code },
		})
		.then((r) => {
			const suppliers = r.message || [];
			if (!suppliers.length) {
				$results.html(`
					<div class="vcm-empty">
						<div class="vcm-empty-icon">🔍</div>
						<h3>${__("No Suppliers Found")}</h3>
						<p>${__("No supplier has supplied this item yet. Check your Purchase Receipts.")}</p>
					</div>
				`);
				return;
			}
			_render_matrix(suppliers, item_code, $results);
		})
		.catch(() => {
			$results.html(`
				<div class="vcm-empty">
					<div class="vcm-empty-icon">⚠️</div>
					<h3>${__("Error Loading Data")}</h3>
					<p>${__("Something went wrong. Please try again or check error logs.")}</p>
				</div>
			`);
		});
}

/* ══════════════════════════════════════════════════════════════════════════
   Matrix renderer
   ══════════════════════════════════════════════════════════════════════════ */

let _current_sort = "scorecard"; // default sort

function _render_matrix(suppliers, item_code, $results) {
	_current_sort = _current_sort || "scorecard";

	// ── Derived analytics ────────────────────────────────────────────────────
	const rates = suppliers.map((s) => parseFloat(s.last_rate) || 0).filter((r) => r > 0);
	const best_rate = Math.min(...rates);
	const worst_rate = Math.max(...rates);

	// ── Sort ────────────────────────────────────────────────────────────────
	const sorted = _sort_suppliers([...suppliers], _current_sort);

	// ── Build HTML ───────────────────────────────────────────────────────────
	const rows_html = sorted
		.map((s, idx) => _build_row(s, idx, best_rate, worst_rate))
		.join("");

	$results.html(`
		<div class="vcm-results-header">
			<div>
				<span class="vcm-results-title">${__("Comparing")} ${suppliers.length} ${__("Suppliers")}</span>
				<span class="vcm-results-meta"> — ${__("Item")}: <strong>${item_code}</strong></span>
			</div>
			<div class="vcm-sort-row">
				<span class="vcm-sort-label">${__("Sort by")}:</span>
				<button class="vcm-sort-btn ${_current_sort === "scorecard" ? "active" : ""}" data-sort="scorecard">${__("Scorecard")}</button>
				<button class="vcm-sort-btn ${_current_sort === "price_asc" ? "active" : ""}" data-sort="price_asc">${__("Price ↑")}</button>
				<button class="vcm-sort-btn ${_current_sort === "price_desc" ? "active" : ""}" data-sort="price_desc">${__("Price ↓")}</button>
				<button class="vcm-sort-btn ${_current_sort === "delivery" ? "active" : ""}" data-sort="delivery">${__("Delivery")}</button>
				<button class="vcm-sort-btn ${_current_sort === "rating" ? "active" : ""}" data-sort="rating">${__("Rating")}</button>
			</div>
		</div>

		<div class="vcm-table-wrap">
			<table class="vcm-table">
				<thead>
					<tr>
						<th>#</th>
						<th>${__("Supplier")}</th>
						<th class="col-num">${__("Last Price")}</th>
						<th class="col-num">${__("Avg Price")}</th>
						<th>${__("Price History")}</th>
						<th class="col-num">${__("Scorecard")}</th>
						<th class="col-num">${__("Delivery Score")}</th>
						<th class="col-num">${__("Quality Score")}</th>
						<th class="col-num">${__("On-Time %")}</th>
						<th class="col-num">${__("Qty Supplied")}</th>
						<th>${__("Actions")}</th>
					</tr>
				</thead>
				<tbody>
					${rows_html}
				</tbody>
			</table>
		</div>
	`);

	// ── Sort buttons ─────────────────────────────────────────────────────────
	$results.find(".vcm-sort-btn").on("click", function () {
		_current_sort = $(this).data("sort");
		_render_matrix(suppliers, item_code, $results);
	});

	// ── Row: open detail dialog ──────────────────────────────────────────────
	$results.find(".vcm-btn-detail").on("click", function () {
		const idx = parseInt($(this).data("idx"), 10);
		_open_detail_dialog(sorted[idx], item_code);
	});

	// ── Draw sparklines after DOM is ready ───────────────────────────────────
	sorted.forEach((s, idx) => {
		if (s.rate_history && s.rate_history.length) {
			_draw_sparkline(`#vcm-spark-${idx}`, s.rate_history);
		}
	});
}

/* ══════════════════════════════════════════════════════════════════════════
   Row builder
   ══════════════════════════════════════════════════════════════════════════ */

function _build_row(s, idx, best_rate, worst_rate) {
	const rank = idx + 1;
	const rank_class = rank === 1 ? "rank-1" : rank === 2 ? "rank-2" : rank === 3 ? "rank-3" : "rank-n";

	const last_rate = parseFloat(s.last_rate) || 0;
	const avg_rate = parseFloat(s.avg_rate) || 0;
	const scorecard = parseFloat(s.scorecard_score) || 0;
	const delivery = parseFloat(s.delivery_score) || 0;
	const quality = parseFloat(s.quality_score) || 0;
	const on_time = parseFloat(s.on_time_pct) || 0;
	const qty = parseFloat(s.total_supplied_qty) || 0;
	const custom_rating = parseFloat(s.custom_rating) || 0; // already scaled to 0-5

	const is_best = last_rate === best_rate && last_rate > 0;
	const is_worst = last_rate === worst_rate && last_rate > 0 && best_rate !== worst_rate;
	const price_class = is_best ? "vcm-price-best" : is_worst ? "vcm-price-worst" : "";

	// Price diff from best
	let diff_html = "";
	if (last_rate > 0 && best_rate > 0) {
		const pct = (((last_rate - best_rate) / best_rate) * 100).toFixed(1);
		if (parseFloat(pct) > 0) {
			diff_html = `<div class="vcm-price-diff pricier">+${pct}% vs best</div>`;
		} else if (parseFloat(pct) < 0) {
			diff_html = `<div class="vcm-price-diff cheaper">${pct}% vs best</div>`;
		} else {
			diff_html = `<div class="vcm-price-diff" style="color:var(--text-muted)">Best price ✓</div>`;
		}
	}

	// Sparkline placeholder
	const spark_html =
		s.rate_history && s.rate_history.length
			? `<div class="vcm-sparkline-wrap">
				<svg id="vcm-spark-${idx}" class="vcm-sparkline-svg"></svg>
				<span class="vcm-spark-label">${s.rate_history.length} ${__("data points")}</span>
			   </div>`
			: `<span style="color:var(--text-muted);font-size:12px;">—</span>`;

	// Score bar (scorecard 0-100)
	const sc_bar = _score_bar(scorecard, 100);
	// Delivery bar (1-5 scale)
	const dlv_bar = _score_bar_5(delivery);
	const qlt_bar = _score_bar_5(quality);

	// Stars for custom rating
	const stars_html = _stars_html(custom_rating);

	// Category badge
	const cat_badge = s.vendor_category
		? `<span class="vcm-category-badge">${frappe.utils.escape_html(s.vendor_category)}</span>`
		: "";

	// Scorecard status
	const sc_status = _status_pill(s.scorecard_status, s.scorecard_color);

	// On-time delivery badge
	const delivery_badge = _delivery_badge(delivery);

	return `
		<tr class="${is_best ? "vcm-best-row" : ""}">
			<td><span class="vcm-rank ${rank_class}">${rank}</span></td>
			<td class="vcm-supplier-cell">
				<span class="vcm-supplier-name">${frappe.utils.escape_html(s.supplier_name || s.supplier)}</span>
				<a class="vcm-supplier-link" href="/app/supplier/${encodeURIComponent(s.supplier)}" target="_blank">
					${frappe.utils.escape_html(s.supplier)} ↗
				</a>
				${cat_badge}
			</td>
			<td class="col-num">
				<div class="vcm-price ${price_class}">${_fmt_currency(last_rate)}</div>
				${diff_html}
			</td>
			<td class="col-num">
				<div class="vcm-price">${_fmt_currency(avg_rate)}</div>
			</td>
			<td>${spark_html}</td>
			<td class="col-num">
				${scorecard > 0
					? `<div class="vcm-score-bar-wrap">${sc_bar}<span class="vcm-score-num">${scorecard.toFixed(0)}</span></div>
					   ${sc_status}`
					: `<span style="color:var(--text-muted);font-size:12px">—</span>`}
			</td>
			<td class="col-num">
				${delivery > 0
					? `<div style="display:flex;flex-direction:column;gap:4px;align-items:flex-start">
						${delivery_badge}
						<div class="vcm-score-bar-wrap" style="width:90px">${dlv_bar}<span class="vcm-score-num">${delivery.toFixed(1)}</span></div>
					   </div>`
					: `<span style="color:var(--text-muted);font-size:12px">—</span>`}
			</td>
			<td class="col-num">
				${quality > 0
					? `<div class="vcm-score-bar-wrap">${qlt_bar}<span class="vcm-score-num">${quality.toFixed(1)}</span></div>`
					: `<span style="color:var(--text-muted);font-size:12px">—</span>`}
			</td>
			<td class="col-num">
				${on_time > 0
					? `<span style="font-weight:700;color:${on_time >= 80 ? "#059669" : on_time >= 60 ? "#d97706" : "#dc2626"}">${on_time.toFixed(0)}%</span>`
					: `<span style="color:var(--text-muted);font-size:12px">—</span>`}
			</td>
			<td class="col-num">
				<span style="font-weight:600">${_fmt_qty(qty)}</span>
			</td>
			<td>
				<button class="btn btn-xs btn-default vcm-btn-detail" data-idx="${idx}">
					${__("View Details")}
				</button>
			</td>
		</tr>
	`;
}

/* ══════════════════════════════════════════════════════════════════════════
   Detail Dialog
   ══════════════════════════════════════════════════════════════════════════ */

function _open_detail_dialog(s, item_code) {
	if (!s) return;

	const supplier_name = s.supplier_name || s.supplier;
	const initials = supplier_name
		.split(/\s+/)
		.slice(0, 2)
		.map((w) => w[0].toUpperCase())
		.join("");

	const scorecard   = parseFloat(s.scorecard_score)     || 0;
	const delivery    = parseFloat(s.delivery_score)      || 0;
	const quality     = parseFloat(s.quality_score)       || 0;
	const custom_rating = parseFloat(s.custom_rating)     || 0;
	const on_time     = parseFloat(s.on_time_pct)         || 0;
	const short_del   = parseInt(s.short_delivery_count)  || 0;
	const total_qty   = parseFloat(s.total_supplied_qty)  || 0;

	// ── Pricing history rows ─────────────────────────────────────────────────
	const history_rows = (s.rate_history || [])
		.map((h, idx, arr) => {
			const prev = arr[idx + 1];
			let change_html = "";
			if (prev && prev.rate) {
				const diff = ((h.rate - prev.rate) / prev.rate) * 100;
				if (Math.abs(diff) < 0.01) {
					change_html = `<span class="vcm-price-change same">—</span>`;
				} else if (diff > 0) {
					change_html = `<span class="vcm-price-change up">▲ ${diff.toFixed(1)}%</span>`;
				} else {
					change_html = `<span class="vcm-price-change down">▼ ${Math.abs(diff).toFixed(1)}%</span>`;
				}
			}
			return `
				<tr>
					<td>${frappe.datetime.str_to_user(h.date) || h.date || "—"}</td>
					<td><strong>${_fmt_currency(h.rate)}</strong></td>
					<td>${change_html}</td>
					<td><a href="/app/purchase-order/${encodeURIComponent(h.po)}" target="_blank"
					       style="color:#3b82f6;font-size:11px">${frappe.utils.escape_html(h.po)} ↗</a></td>
				</tr>
			`;
		})
		.join("") || `<tr><td colspan="4" style="text-align:center;color:var(--text-muted);padding:20px">
			${__("No pricing history available")}</td></tr>`;

	// ── Full dialog HTML ─────────────────────────────────────────────────────
	const content_html = `
		<div class="vcm-dialog-body">
			<!-- Header -->
			<div class="vcm-dialog-supplier-header">
				<div class="vcm-dialog-avatar">${initials}</div>
				<div style="flex:1">
					<h3 class="vcm-dialog-supplier-name">${frappe.utils.escape_html(supplier_name)}</h3>
					<div class="vcm-dialog-supplier-meta">
						${frappe.utils.escape_html(s.supplier)}
						${s.vendor_category ? " · " + frappe.utils.escape_html(s.vendor_category) : ""}
						${s.scorecard_status ? " · " + frappe.utils.escape_html(s.scorecard_status) : ""}
					</div>
					<div style="margin-top:8px">${_stars_html(custom_rating)}</div>
				</div>
				<div style="text-align:right">
					<a href="/app/supplier/${encodeURIComponent(s.supplier)}" target="_blank"
					   style="color:#63b3ed;font-size:12px;text-decoration:none">
						${__("Open Supplier")} ↗
					</a>
				</div>
			</div>

			<!-- Tabs -->
			<div class="vcm-dialog-tabs">
				<div class="vcm-dialog-tab active" data-tab="overview">${__("Overview")}</div>
				<div class="vcm-dialog-tab" data-tab="pricing">${__("Pricing History")}</div>
				<div class="vcm-dialog-tab" data-tab="ratings">${__("Ratings Breakdown")}</div>
			</div>

			<!-- Tab: Overview -->
			<div class="vcm-dialog-panel active" data-panel="overview">
				<div class="vcm-metric-grid">
					<div class="vcm-metric-card">
						<div class="vcm-metric-label">${__("Last Price")}</div>
						<div class="vcm-metric-value">${_fmt_currency(s.last_rate)}</div>
						<div class="vcm-metric-sub">${__("Most recent PO rate")}</div>
					</div>
					<div class="vcm-metric-card">
						<div class="vcm-metric-label">${__("Avg Price")}</div>
						<div class="vcm-metric-value">${_fmt_currency(s.avg_rate)}</div>
						<div class="vcm-metric-sub">${__("Historical average")}</div>
					</div>
					<div class="vcm-metric-card">
						<div class="vcm-metric-label">${__("Qty Supplied")}</div>
						<div class="vcm-metric-value">${_fmt_qty(total_qty)}</div>
						<div class="vcm-metric-sub">${__("Total units received")}</div>
					</div>
					<div class="vcm-metric-card">
						<div class="vcm-metric-label">${__("On-Time Rate")}</div>
						<div class="vcm-metric-value" style="color:${on_time >= 80 ? "#059669" : on_time >= 60 ? "#d97706" : "#dc2626"}">
							${on_time > 0 ? on_time.toFixed(0) + "%" : "—"}
						</div>
						<div class="vcm-metric-sub">${__("Delivery score ≥ 3")}</div>
					</div>
					<div class="vcm-metric-card">
						<div class="vcm-metric-label">${__("Scorecard Score")}</div>
						<div class="vcm-metric-value" style="color:${scorecard >= 80 ? "#059669" : scorecard >= 60 ? "#d97706" : "#dc2626"}">
							${scorecard > 0 ? scorecard.toFixed(0) : "—"}
						</div>
						<div class="vcm-metric-sub">${__("Supplier Scorecard")}</div>
					</div>
					<div class="vcm-metric-card">
						<div class="vcm-metric-label">${__("Short Deliveries")}</div>
						<div class="vcm-metric-value" style="color:${short_del === 0 ? "#059669" : short_del <= 2 ? "#d97706" : "#dc2626"}">
							${short_del}
						</div>
						<div class="vcm-metric-sub">${__("Delivery score < 3")}</div>
					</div>
				</div>
				${s.rate_history && s.rate_history.length >= 2 ? `
					<div class="vcm-chart-title">${__("Price Trend")}</div>
					<svg class="vcm-mini-chart vcm-detail-spark-svg"></svg>
				` : ""}
			</div>

			<!-- Tab: Pricing History -->
			<div class="vcm-dialog-panel" data-panel="pricing">
				<table class="vcm-history-table">
					<thead><tr>
						<th>${__("Date")}</th>
						<th>${__("Rate")}</th>
						<th>${__("Change")}</th>
						<th>${__("Purchase Order")}</th>
					</tr></thead>
					<tbody>${history_rows}</tbody>
				</table>
			</div>

			<!-- Tab: Ratings -->
			<div class="vcm-dialog-panel" data-panel="ratings">
				<div style="margin-bottom:20px">
					<div class="vcm-chart-title">${__("Rating Breakdown by Category")}</div>
					${_rating_breakdown_html(s)}
				</div>
				<div style="margin-top:16px;padding:14px;border-radius:10px;border:1px solid var(--border-color);background:var(--subtle-bg,var(--fg-color,#f9fafb))">
					<div style="display:flex;justify-content:space-between;align-items:center">
						<span style="font-size:12px;color:var(--text-muted)">${__("Vendor Scorecard Status")}</span>
						${s.scorecard_status
							? _status_pill(s.scorecard_status, s.scorecard_color)
							: `<span style="color:var(--text-muted);font-size:12px">${__("Not enrolled")}</span>`}
					</div>
					${scorecard > 0 ? `
						<div style="margin-top:12px">
							<div class="vcm-score-bar-wrap">
								${_score_bar(scorecard, 100, "large")}
								<span class="vcm-score-num" style="font-size:14px">${scorecard.toFixed(0)}<span style="font-size:11px;font-weight:400;color:var(--text-muted)">/100</span></span>
							</div>
						</div>
					` : ""}
				</div>
			</div>
		</div>
	`;

	// ── Create dialog ────────────────────────────────────────────────────────
	const d = new frappe.ui.Dialog({
		title: supplier_name,
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "content", options: content_html }],
		primary_action_label: __("Open Supplier"),
		primary_action() {
			window.open("/app/supplier/" + encodeURIComponent(s.supplier), "_blank");
		},
	});

	d.show();

	// ── Frappe 16: HTML field content is live in the DOM after show() ────────
	const $modal = d.$wrapper;

	// Hide the native Frappe modal header — we have our own hero header inside
	$modal.find(".modal-header").css({ background: "transparent", "border-bottom": "none" });
	$modal.find(".modal-title").text(supplier_name);

	// Ensure modal body has no padding (our HTML has its own padding)
	$modal.find(".modal-body").css("padding", "0");

	// ── Tab switching (delegated from modal wrapper) ─────────────────────────
	$modal.on("click", ".vcm-dialog-tab", function () {
		const tab = $(this).data("tab");
		$(this).closest(".vcm-dialog-body")
			.find(".vcm-dialog-tab").removeClass("active");
		$(this).addClass("active");
		$(this).closest(".vcm-dialog-body")
			.find(".vcm-dialog-panel").removeClass("active");
		$(this).closest(".vcm-dialog-body")
			.find(`.vcm-dialog-panel[data-panel="${tab}"]`).addClass("active");
	});

	// ── Draw sparkline after modal renders ───────────────────────────────────
	if (s.rate_history && s.rate_history.length >= 2) {
		setTimeout(() => {
			const spark_el = $modal.find(".vcm-detail-spark-svg")[0];
			if (spark_el) _draw_sparkline_large_el(spark_el, s.rate_history);
		}, 120);
	}
}

/* ══════════════════════════════════════════════════════════════════════════
   Sparkline SVG helpers
   ══════════════════════════════════════════════════════════════════════════ */

function _draw_sparkline(selector, history) {
	const el = document.querySelector(selector);
	if (!el) return;

	// history is newest‑first; reverse for left→right display
	const data = [...history].reverse().map((h) => parseFloat(h.rate) || 0);
	if (!data.length) return;

	const W = 120,
		H = 36,
		pad = 4;
	const min_v = Math.min(...data);
	const max_v = Math.max(...data);
	const range = max_v - min_v || 1;

	const xs = data.map((_, i) => pad + (i / Math.max(data.length - 1, 1)) * (W - pad * 2));
	const ys = data.map((v) => H - pad - ((v - min_v) / range) * (H - pad * 2));

	// Gradient area
	const area_d =
		`M${xs[0]},${H - pad} ` +
		xs.map((x, i) => `L${x},${ys[i]}`).join(" ") +
		` L${xs[xs.length - 1]},${H - pad} Z`;

	// Line path
	const line_d = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x},${ys[i]}`).join(" ");

	const gradient_id = `vcm-grad-${Math.random().toString(36).slice(2)}`;
	const color = "#3b82f6";

	el.innerHTML = `
		<defs>
			<linearGradient id="${gradient_id}" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color="${color}" stop-opacity="0.35"/>
				<stop offset="100%" stop-color="${color}" stop-opacity="0"/>
			</linearGradient>
		</defs>
		<path d="${area_d}" fill="url(#${gradient_id})"/>
		<path d="${line_d}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
		<circle cx="${xs[xs.length - 1]}" cy="${ys[ys.length - 1]}" r="2.5" fill="${color}"/>
	`;
}

// Element-based variant used by the dialog (avoids global ID lookup)
function _draw_sparkline_large_el(el, history) {
	if (!el) return;
	_draw_sparkline_large_core(el, history);
}

function _draw_sparkline_large(selector, history) {
	const el = document.querySelector(selector);
	if (!el) return;
	_draw_sparkline_large_core(el, history);
}

function _draw_sparkline_large_core(el, history) {
	const data = [...history].reverse().map((h) => parseFloat(h.rate) || 0);
	const labels = [...history].reverse().map((h) => (h.date ? h.date.slice(0, 10) : ""));
	if (!data.length) return;

	const W = el.getBoundingClientRect().width || 680;
	const H = 140;
	const pad = { top: 12, right: 16, bottom: 32, left: 56 };
	const inner_w = W - pad.left - pad.right;
	const inner_h = H - pad.top - pad.bottom;

	const min_v = Math.min(...data);
	const max_v = Math.max(...data);
	const range = max_v - min_v || 1;

	const xs = data.map((_, i) => pad.left + (i / Math.max(data.length - 1, 1)) * inner_w);
	const ys = data.map((v) => pad.top + inner_h - ((v - min_v) / range) * inner_h);

	const area_d =
		`M${xs[0]},${pad.top + inner_h} ` +
		xs.map((x, i) => `L${x},${ys[i]}`).join(" ") +
		` L${xs[xs.length - 1]},${pad.top + inner_h} Z`;

	const line_d = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x},${ys[i]}`).join(" ");

	const gid = `vcm-lg-${Math.random().toString(36).slice(2)}`;
	const color = "#3b82f6";
	const text_color = "var(--text-muted)";

	// Y-axis labels (3 points)
	const y_labels = [min_v, (min_v + max_v) / 2, max_v].map((v, i) => {
		const y = pad.top + inner_h - (i / 2) * inner_h;
		return `<text x="${pad.left - 6}" y="${y + 4}" text-anchor="end" font-size="10" fill="${text_color}">${_fmt_currency(v, true)}</text>`;
	});

	// X-axis labels (show up to 5)
	const x_step = Math.max(1, Math.floor(data.length / 5));
	const x_labels = labels
		.filter((_, i) => i % x_step === 0 || i === labels.length - 1)
		.map((lbl, i, arr) => {
			const orig_i = i === arr.length - 1 ? labels.length - 1 : i * x_step;
			return `<text x="${xs[orig_i]}" y="${H - 4}" text-anchor="middle" font-size="10" fill="${text_color}">${lbl}</text>`;
		});

	// Dots
	const dots = xs.map(
		(x, i) =>
			`<circle cx="${x}" cy="${ys[i]}" r="3.5" fill="${color}" stroke="#fff" stroke-width="1.5">
				<title>${labels[i]}: ${_fmt_currency(data[i])}</title>
			</circle>`
	);

	el.setAttribute("viewBox", `0 0 ${W} ${H}`);
	el.innerHTML = `
		<defs>
			<linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color="${color}" stop-opacity="0.3"/>
				<stop offset="100%" stop-color="${color}" stop-opacity="0.02"/>
			</linearGradient>
		</defs>
		<line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${pad.top + inner_h}" stroke="var(--border-color)" stroke-width="1"/>
		<line x1="${pad.left}" y1="${pad.top + inner_h}" x2="${pad.left + inner_w}" y2="${pad.top + inner_h}" stroke="var(--border-color)" stroke-width="1"/>
		${y_labels.join("")}
		${x_labels.join("")}
		<path d="${area_d}" fill="url(#${gid})"/>
		<path d="${line_d}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
		${dots.join("")}
	`;
}

/* ══════════════════════════════════════════════════════════════════════════
   UI Widget helpers
   ══════════════════════════════════════════════════════════════════════════ */

function _score_bar(value, max, size) {
	const pct = Math.min(100, Math.max(0, (value / max) * 100));
	const cls =
		pct >= 80 ? "excellent" : pct >= 60 ? "good" : pct >= 40 ? "average" : "poor";
	const h = size === "large" ? "10px" : "6px";
	return `
		<div class="vcm-score-bar-track" style="height:${h}">
			<div class="vcm-score-bar-fill ${cls}" style="width:${pct}%"></div>
		</div>
	`;
}

function _score_bar_5(value) {
	return _score_bar(value, 5);
}

function _stars_html(rating) {
	// rating is 0-5
	const full = Math.floor(rating);
	const half = rating - full >= 0.4 && rating - full < 0.9;
	const stars = [];
	for (let i = 1; i <= 5; i++) {
		if (i <= full) stars.push(`<span class="vcm-star filled">★</span>`);
		else if (i === full + 1 && half) stars.push(`<span class="vcm-star half">★</span>`);
		else stars.push(`<span class="vcm-star">★</span>`);
	}
	return `<div class="vcm-stars">${stars.join("")}<span class="vcm-rating-num">${rating > 0 ? rating.toFixed(1) : "—"}</span></div>`;
}

function _delivery_badge(score) {
	if (!score) return "";
	const cls =
		score >= 4 ? "excellent" : score >= 3 ? "good" : score >= 2 ? "average" : "poor";
	const label =
		score >= 4 ? __("Excellent") : score >= 3 ? __("Good") : score >= 2 ? __("Average") : __("Poor");
	return `
		<div class="vcm-delivery-badge ${cls}">
			<div class="vcm-delivery-dot"></div>
			${label}
		</div>
	`;
}

function _status_pill(status, color) {
	if (!status) return "";
	const color_map = {
		Green: "green",
		Orange: "orange",
		Red: "red",
	};
	const cls = color_map[color] || "grey";
	return `<span class="vcm-status-pill ${cls}">${frappe.utils.escape_html(status)}</span>`;
}

function _rating_breakdown_html(s) {
	const categories = [
		{ key: "delivery", label: __("Delivery"), value: parseFloat(s.delivery_score) || 0, color: "#3b82f6" },
		{ key: "quality", label: __("Quality"), value: parseFloat(s.quality_score) || 0, color: "#8b5cf6" },
	];

	return categories
		.map((cat) => {
			const pct = (cat.value / 5) * 100;
			return `
				<div class="vcm-rating-row">
					<span class="vcm-rating-label">${cat.label}</span>
					<div class="vcm-rating-bar-track">
						<div class="vcm-rating-bar-fill" style="width:${pct}%;background:${cat.color}"></div>
					</div>
					<span class="vcm-rating-score">${cat.value > 0 ? cat.value.toFixed(1) : "—"}</span>
				</div>
			`;
		})
		.join("");
}

/* ══════════════════════════════════════════════════════════════════════════
   Sorting helpers
   ══════════════════════════════════════════════════════════════════════════ */

function _sort_suppliers(arr, sort) {
	switch (sort) {
		case "price_asc":
			return arr.sort((a, b) => (parseFloat(a.last_rate) || 999999) - (parseFloat(b.last_rate) || 999999));
		case "price_desc":
			return arr.sort((a, b) => (parseFloat(b.last_rate) || 0) - (parseFloat(a.last_rate) || 0));
		case "delivery":
			return arr.sort((a, b) => (parseFloat(b.delivery_score) || 0) - (parseFloat(a.delivery_score) || 0));
		case "rating":
			return arr.sort((a, b) => (parseFloat(b.custom_rating) || 0) - (parseFloat(a.custom_rating) || 0));
		case "scorecard":
		default:
			return arr.sort((a, b) => (parseFloat(b.scorecard_score) || 0) - (parseFloat(a.scorecard_score) || 0));
	}
}

/* ══════════════════════════════════════════════════════════════════════════
   Formatting helpers
   ══════════════════════════════════════════════════════════════════════════ */

function _fmt_currency(val, compact) {
	const v = parseFloat(val) || 0;
	if (!v) return "—";
	if (compact) {
		if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
		if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
		return v.toFixed(0);
	}
	return frappe.format(v, { fieldtype: "Currency" });
}

function _fmt_qty(val) {
	const v = parseFloat(val) || 0;
	if (!v) return "—";
	if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
	if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
	return v.toLocaleString();
}
