frappe.pages["vendor-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Vendor Dashboard",
		single_column: true,
	});

	let page = wrapper.page;
	let $body = $(wrapper).find(".page-content");

	// Quick navigation to Comparison Matrix
	page.add_menu_item(__("Vendor Comparison Matrix"), () => frappe.set_route("vendor-comparison"));

	$body.html(`
		<div class="vendor-dashboard">
			<!-- KPI Strip -->
			<div class="kpi-strip">
				<div class="kpi-card" id="kpi-suppliers">
					<div class="kpi-label">${__("Active Suppliers")}</div>
					<div class="kpi-value">—</div>
				</div>
				<div class="kpi-card" id="kpi-onboardings">
					<div class="kpi-label">${__("Pending Onboardings")}</div>
					<div class="kpi-value">—</div>
				</div>
				<div class="kpi-card" id="kpi-pos">
					<div class="kpi-label">${__("POs This Month")}</div>
					<div class="kpi-value">—</div>
				</div>
				<div class="kpi-card" id="kpi-avg-rating">
					<div class="kpi-label">${__("Avg Scorecard Score")}</div>
					<div class="kpi-value">—</div>
				</div>
				<div class="kpi-card" id="kpi-compare" style="cursor:pointer;border:1px dashed var(--border-color);background:transparent" onclick="frappe.set_route('vendor-comparison')">
					<div class="kpi-label">${__("Vendor Comparison")}</div>
					<div class="kpi-value" style="font-size:20px">⚡ <span style="font-size:13px;font-weight:600;color:#3b82f6">${__("Compare →")}</span></div>
				</div>
			</div>

			<!-- Chart Grid -->
			<div class="chart-grid">
				<div class="chart-card wide">
					<div class="chart-header">
						<h4>${__("Vendor Rating Distribution")}</h4>
						<span class="chart-subtitle">${__("Supplier Scorecard score buckets")}</span>
					</div>
					<div class="chart-wrapper" id="chart-rating-distribution"></div>
				</div>
				<div class="chart-card">
					<div class="chart-header">
						<h4>${__("Onboarding Pipeline")}</h4>
						<span class="chart-subtitle">${__("Applications by status")}</span>
					</div>
					<div class="chart-wrapper" id="chart-onboarding-pipeline"></div>
				</div>
				<div class="chart-card">
					<div class="chart-header">
						<h4>${__("PO Volume by Category")}</h4>
						<span class="chart-subtitle">${__("Total purchase value per vendor category")}</span>
					</div>
					<div class="chart-wrapper" id="chart-po-volume"></div>
				</div>
				<div class="chart-card wide">
					<div class="chart-header">
						<h4>${__("Delivery Performance Trend")}</h4>
						<span class="chart-subtitle">${__("Average monthly scorecard score (last 12 months)")}</span>
					</div>
					<div class="chart-wrapper" id="chart-delivery-trend"></div>
				</div>
			</div>
		</div>
	`);

	// Load KPI counts
	_load_kpis();

	// Load all 4 charts
	_load_chart_rating_distribution();
	_load_chart_onboarding_pipeline();
	_load_chart_po_volume();
	_load_chart_delivery_trend();
};

// ─────────────────────────────────────────────────────────────────────────
// KPI helpers
// ─────────────────────────────────────────────────────────────────────────

function _load_kpis() {
	Promise.all([
		frappe.db.count("Supplier", { disabled: 0 }),
		frappe.db.count("Vendor Onboarding", { onboarding_status: "Under Review" }),
		frappe.xcall("frappe.client.get_list", {
			doctype: "Purchase Order",
			filters: [
				["docstatus", "=", 1],
				["transaction_date", ">=", frappe.datetime.month_start()],
			],
			fields: ["name"],
			limit_page_length: 0,
		}),
		frappe.xcall("frappe.client.get_list", {
			doctype: "Supplier Scorecard",
			fields: ["supplier_score"],
			limit_page_length: 0,
		}),
	]).then(([suppliers, onboardings, pos, scorecards]) => {
		$("#kpi-suppliers .kpi-value").text(suppliers);
		$("#kpi-onboardings .kpi-value").text(onboardings);
		$("#kpi-pos .kpi-value").text(pos.length);

		let avg = 0;
		if (scorecards && scorecards.length) {
			let total = scorecards.reduce((s, r) => s + flt(r.supplier_score), 0);
			avg = (total / scorecards.length).toFixed(1);
		}
		$("#kpi-avg-rating .kpi-value").text(avg || "—");
	});
}

// ─────────────────────────────────────────────────────────────────────────
// Chart loaders
// ─────────────────────────────────────────────────────────────────────────

function _load_chart_rating_distribution() {
	frappe
		.call("vendor_portal.vendor_portal.page.vendor_dashboard.vendor_dashboard.get_rating_distribution")
		.then((r) => {
			if (!r.message) return;
			new frappe.Chart("#chart-rating-distribution", {
				data: r.message,
				type: "bar",
				height: 280,
				colors: ["#2490ef"],
				barOptions: { spaceRatio: 0.6 },
				axisOptions: { xAxisMode: "tick", yAxisMode: "span" },
			});
		});
}

function _load_chart_onboarding_pipeline() {
	frappe
		.call("vendor_portal.vendor_portal.page.vendor_dashboard.vendor_dashboard.get_onboarding_pipeline")
		.then((r) => {
			if (!r.message) return;
			new frappe.Chart("#chart-onboarding-pipeline", {
				data: r.message,
				type: "bar",
				height: 280,
				colors: ["#7c3aed"],
				barOptions: { spaceRatio: 0.5 },
				axisOptions: { xAxisMode: "tick" },
			});
		});
}

function _load_chart_po_volume() {
	frappe
		.call("vendor_portal.vendor_portal.page.vendor_dashboard.vendor_dashboard.get_po_volume_by_category")
		.then((r) => {
			if (!r.message) return;
			new frappe.Chart("#chart-po-volume", {
				data: r.message,
				type: "bar",
				height: 280,
				colors: ["#d97706"],
				barOptions: { spaceRatio: 0.5 },
				axisOptions: { xAxisMode: "tick" },
			});
		});
}

function _load_chart_delivery_trend() {
	frappe
		.call("vendor_portal.vendor_portal.page.vendor_dashboard.vendor_dashboard.get_delivery_trend")
		.then((r) => {
			if (!r.message) return;
			new frappe.Chart("#chart-delivery-trend", {
				data: r.message,
				type: "line",
				height: 280,
				colors: ["#059669"],
				lineOptions: { regionFill: 1, hideDots: 0, heatLine: 1 },
				axisOptions: { xIsSeries: 1, xAxisMode: "tick", yAxisMode: "span" },
			});
		});
}
