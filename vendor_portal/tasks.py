# vendor_portal/tasks.py
#
# Scheduled background jobs for the Vendor Portal app.
#
# Job summary
# ───────────────────────────────────────────────────────────────────────────
#  Function                        Frequency       hooks.py key
#  ─────────────────────────────── ──────────────  ───────────────────────
#  calculate_vendor_ratings         daily           scheduler_events.daily
#  auto_rate_deliveries             hourly          scheduler_events.hourly
#  send_vendor_performance_digest   weekly          scheduler_events.weekly
#  expire_stale_onboardings         cron 0 9 * * *  scheduler_events.cron
# ───────────────────────────────────────────────────────────────────────────
#
# Design decisions
# ─────────────────
# • frappe.get_all   → lightweight field projection; never loads full documents.
# • frappe.db.set_value → single UPDATE statement; no Document overhead.
# • frappe.get_single_value → one-shot value fetch from a Single DocType.
# • All functions are wrapped in try/except; errors are captured with
#   frappe.log_error() so one bad vendor never breaks the entire scheduler run.
# • No os / subprocess imports; only the Frappe standard library is used.

import frappe
from frappe.utils import (
	add_days,
	add_to_date,
	getdate,
	get_datetime,
	nowdate,
	now_datetime,
	flt,
	cint,
	get_first_day,
	get_last_day,
)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_settings():
	"""
	Return a lightweight dict of Vendor Portal Settings values.
	Using frappe.get_single is cheaper than individual get_single_value calls
	when we need many fields together (one DB round-trip vs. many).
	"""
	settings = frappe.get_single("Vendor Portal Settings")
	return {
		"auto_rating_enabled": cint(settings.auto_rating_enabled),
		"low_rating_threshold": flt(settings.low_rating_threshold) or 2.5,
		"weight_delivery":      flt(settings.rating_weight_delivery)      or 0.30,
		"weight_quality":       flt(settings.rating_weight_quality)       or 0.30,
		"weight_pricing":       flt(settings.rating_weight_pricing)       or 0.20,
		"weight_communication": flt(settings.rating_weight_communication) or 0.20,
	}


def _get_vendor_manager_emails():
	"""
	Return a deduplicated list of email addresses for enabled users that hold
	the 'Vendor Manager' role.

	Has Role.parent stores the User email, so we query it directly, then
	verify the user is enabled before adding to the result list.
	"""
	managers = frappe.get_all(
		"Has Role",
		filters={"role": "Vendor Manager", "parenttype": "User"},
		fields=["parent as email"],
	)

	emails = []
	for row in managers:
		user_email = row.get("email", "")
		if not user_email or "@" not in user_email:
			continue
		# Check the user is enabled; db.get_value avoids a full User doc load
		enabled = frappe.db.get_value("User", user_email, "enabled")
		if cint(enabled):
			emails.append(user_email)

	return list(set(emails))   # Deduplicate in case of duplicate Has Role rows


# ─────────────────────────────────────────────────────────────────────────────
#  TASK 1 — Daily: Auto-Calculate Vendor Ratings
# ─────────────────────────────────────────────────────────────────────────────

def calculate_vendor_ratings():
	"""
	Scheduled daily job.

	For every active Supplier that has a custom_vendor_category set:
	  1. Fetch all Vendor Rating Log entries for that supplier.
	  2. Compute a weighted average score using per-type weights from
	     Vendor Portal Settings.
	  3. Write the result back to the Supplier's custom_vendor_rating and
	     custom_total_rating_count custom fields via a single db.set_value call.
	  4. If the new rating falls below low_rating_threshold, send an alert
	     email to all Vendor Manager role users.
	"""
	frappe.logger("vendor_portal.tasks").info("Starting: calculate_vendor_ratings")

	try:
		settings = _get_settings()
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"calculate_vendor_ratings: could not load Vendor Portal Settings",
		)
		return

	# Map of rating_type → configured weight
	weight_map = {
		"Delivery":      settings["weight_delivery"],
		"Quality":       settings["weight_quality"],
		"Pricing":       settings["weight_pricing"],
		"Communication": settings["weight_communication"],
	}
	threshold  = settings["low_rating_threshold"]
	mgr_emails = _get_vendor_manager_emails()

	# Fetch all active suppliers that have a vendor category assigned.
	# get_all with field projection avoids loading full Supplier documents.
	suppliers = frappe.get_all(
		"Supplier",
		filters={
			"disabled": 0,
			"custom_vendor_category": ["is", "set"],
		},
		fields=["name", "supplier_name"],
		order_by="name asc",
	)

	if not suppliers:
		frappe.logger("vendor_portal.tasks").info(
			"calculate_vendor_ratings: no eligible suppliers found"
		)
		return

	for supplier in suppliers:
		try:
			_recalculate_single_supplier_rating(
				supplier_id=supplier["name"],
				supplier_name=supplier["supplier_name"],
				weight_map=weight_map,
				threshold=threshold,
				mgr_emails=mgr_emails,
			)
		except Exception:
			# Log per-supplier failure silently; continue to next supplier
			frappe.log_error(
				frappe.get_traceback(),
				f"calculate_vendor_ratings: error processing supplier {supplier['name']}",
			)

	frappe.logger("vendor_portal.tasks").info(
		f"Completed: calculate_vendor_ratings — processed {len(suppliers)} supplier(s)"
	)


def _recalculate_single_supplier_rating(
	supplier_id, supplier_name, weight_map, threshold, mgr_emails
):
	"""
	Core rating recalculation for a single supplier.
	Separated from the loop so the outer function can catch per-supplier
	failures independently without aborting the whole run.

	Weighted average formula:
	  Σ( avg_score_for_type × weight_for_type )
	  ─────────────────────────────────────────
	  Σ( weights_of_types_that_have_at_least_one_log )

	Only types that actually have data contribute to the denominator,
	so a supplier with only Delivery and Quality logs won't be penalised
	for having no Pricing/Communication logs.
	"""
	# Fetch all rating log records for this supplier (lightweight field projection)
	logs = frappe.get_all(
		"Vendor Rating Log",
		filters={"supplier": supplier_id},
		fields=["rating_type", "score"],
	)

	if not logs:
		# No logs yet — do not touch the supplier record
		return

	# Accumulate scores per rating_type
	type_scores = {}   # { "Delivery": [5.0, 4.0, ...], "Quality": [3.0], ... }
	for log in logs:
		rtype = log.get("rating_type") or "Delivery"
		score = flt(log.get("score") or 0)
		type_scores.setdefault(rtype, []).append(score)

	weighted_sum     = 0.0
	effective_weight = 0.0

	for rtype, weight in weight_map.items():
		if rtype in type_scores:
			avg_for_type      = sum(type_scores[rtype]) / len(type_scores[rtype])
			weighted_sum     += avg_for_type * weight
			effective_weight += weight

	if effective_weight == 0:
		# Guard against division-by-zero (no recognized rating types found)
		return

	final_rating_1to5 = round(weighted_sum / effective_weight, 2)
	total_count        = len(logs)   # Total log entries across all types

	# custom_vendor_rating is a Frappe Rating fieldtype — stored as 0–1
	final_rating_0to1 = final_rating_1to5 / 5.0

	# Single UPDATE statement — no full document load needed
	frappe.db.set_value(
		"Supplier",
		supplier_id,
		{
			"custom_vendor_rating":      final_rating_0to1,
			"custom_total_rating_count": total_count,
		},
		update_modified=False,   # Don't bump modified for a background recalc
	)

	frappe.logger("vendor_portal.tasks").debug(
		f"  → {supplier_id}: rating={final_rating_1to5}/5, total_logs={total_count}"
	)

	# Send alert email if the rating dropped below the configured threshold
	if final_rating_1to5 < threshold and mgr_emails:
		subject = f"⚠️ Low Vendor Rating Alert — {supplier_name}"
		message = f"""
<p>Dear Vendor Manager,</p>
<p>The vendor <strong>{supplier_name}</strong> ({supplier_id}) has a recalculated
rating of <strong>{final_rating_1to5} / 5.0</strong>, which is below the configured
low-rating threshold of <strong>{threshold}</strong>.</p>
<p>Please review this vendor's performance and take appropriate action.</p>
<br>
<p style="color:#888; font-size:12px;">
  This is an automated alert from the Vendor Portal scheduler (daily run on {nowdate()}).
</p>
"""
		try:
			frappe.sendmail(
				recipients=mgr_emails,
				subject=subject,
				message=message,
				delayed=False,   # Send immediately via background worker, not queued
			)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"calculate_vendor_ratings: failed to send low-rating alert for {supplier_id}",
			)


# ─────────────────────────────────────────────────────────────────────────────
#  TASK 2 — Hourly: Auto-Rate Deliveries from Purchase Receipts
# ─────────────────────────────────────────────────────────────────────────────

def auto_rate_deliveries():
	"""
	Scheduled hourly job.

	Finds submitted Purchase Receipts with a posting_datetime in the last
	2 hours that do not yet have a 'Delivery' Vendor Rating Log, then
	auto-creates one by evaluating two dimensions:

	  1. Timeliness  — Posting Date vs. earliest schedule_date in PR Items
	  2. Qty accuracy — Received Qty vs. Accepted Qty aggregated across items

	Scoring rubric (scale 1.0 – 5.0):

	  Timeliness:
	    On time or early → 5.0
	    1–3 days late    → 3.5
	    4–7 days late    → 2.5
	    > 7 days late    → 1.0
	    No date set      → 3.0 (neutral)

	  Qty accuracy (acceptance rate = accepted / received × 100):
	    ≥ 100%           → 5.0
	    90–99%           → 4.0
	    75–89%           → 3.0
	    50–74%           → 2.0
	    < 50%            → 1.0
	    No qty data      → 3.0 (neutral)

	  Final score = average(timeliness, qty_accuracy), clamped to [1.0, 5.0].
	"""
	frappe.logger("vendor_portal.tasks").info("Starting: auto_rate_deliveries")

	# Compute the 2-hour look-back window
	two_hours_ago = add_to_date(now_datetime(), hours=-2)

	try:
		# Fetch submitted PRs created/posted within the last 2 hours
		recent_receipts = frappe.get_all(
			"Purchase Receipt",
			filters={
				"docstatus": 1,                           # Submitted only
				"posting_date": [">=", two_hours_ago],   # Within the 2-hour window
			},
			fields=["name", "supplier", "posting_date"],
			order_by="posting_date asc",
		)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"auto_rate_deliveries: error fetching Purchase Receipts",
		)
		return

	if not recent_receipts:
		frappe.logger("vendor_portal.tasks").info(
			"auto_rate_deliveries: no recent Purchase Receipts found"
		)
		return

	# Bulk-fetch the PR names that already have a Delivery VRL — one query
	# avoids N+1 lookups inside the loop below.
	pr_names = [r["name"] for r in recent_receipts]
	already_rated = set(
		row["purchase_receipt"]
		for row in frappe.get_all(
			"Vendor Rating Log",
			filters={
				"rating_type": "Delivery",
				"purchase_receipt": ["in", pr_names],
			},
			fields=["purchase_receipt"],
		)
	)

	created_count = 0
	for receipt in recent_receipts:
		if receipt["name"] in already_rated:
			continue   # Skip: already has a Delivery rating log

		try:
			_create_delivery_rating_log(receipt)
			created_count += 1
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"auto_rate_deliveries: error creating rating for PR {receipt['name']}",
			)

	frappe.logger("vendor_portal.tasks").info(
		f"Completed: auto_rate_deliveries — created {created_count} Vendor Rating Log(s)"
	)


def _create_delivery_rating_log(receipt):
	"""
	Calculates and inserts a single 'Delivery' Vendor Rating Log for the
	given Purchase Receipt dict.
	"""
	pr_name      = receipt["name"]
	supplier     = receipt.get("supplier")
	posting_date = getdate(receipt.get("posting_date") or nowdate())

	# ── 1. Timeliness score ─────────────────────────────────────────────────
	# Pull the earliest schedule_date from PR items to determine expected date.
	item_date_rows = frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": pr_name},
		fields=["schedule_date"],
		order_by="schedule_date asc",
		limit=1,
	)

	timeliness_score  = 3.0
	timeliness_remark = "No expected delivery date set on PR items — neutral score."

	if item_date_rows and item_date_rows[0].get("schedule_date"):
		expected_date = getdate(item_date_rows[0]["schedule_date"])
		days_late     = (posting_date - expected_date).days   # Negative = early

		if days_late <= 0:
			timeliness_score  = 5.0
			timeliness_remark = (
				f"On time / early delivery "
				f"(expected: {expected_date}, actual: {posting_date})."
			)
		elif days_late <= 3:
			timeliness_score  = 3.5
			timeliness_remark = f"Delivered {days_late} day(s) late (minor delay)."
		elif days_late <= 7:
			timeliness_score  = 2.5
			timeliness_remark = f"Delivered {days_late} day(s) late (moderate delay)."
		else:
			timeliness_score  = 1.0
			timeliness_remark = f"Delivered {days_late} day(s) late (severe overdue)."

	# ── 2. Qty accuracy score ───────────────────────────────────────────────
	# Aggregate received_qty and accepted_qty from all PR item rows.
	items = frappe.get_all(
		"Purchase Receipt Item",
		filters={"parent": pr_name},
		fields=["received_qty", "accepted_qty"],
	)

	total_received = sum(flt(i.get("received_qty") or 0) for i in items)
	total_accepted = sum(flt(i.get("accepted_qty") or 0) for i in items)

	qty_score  = 3.0
	qty_remark = "No quantity data available — neutral score."

	if total_received > 0:
		acceptance_pct = (total_accepted / total_received) * 100
		if acceptance_pct >= 100:
			qty_score  = 5.0
			qty_remark = (
				f"Perfect acceptance: {total_accepted} / {total_received} units accepted (100%)."
			)
		elif acceptance_pct >= 90:
			qty_score  = 4.0
			qty_remark = (
				f"{acceptance_pct:.1f}% accepted "
				f"({total_accepted} / {total_received} units) — minor shortfall."
			)
		elif acceptance_pct >= 75:
			qty_score  = 3.0
			qty_remark = (
				f"{acceptance_pct:.1f}% accepted "
				f"({total_accepted} / {total_received} units) — moderate shortfall."
			)
		elif acceptance_pct >= 50:
			qty_score  = 2.0
			qty_remark = (
				f"{acceptance_pct:.1f}% accepted "
				f"({total_accepted} / {total_received} units) — significant rejections."
			)
		else:
			qty_score  = 1.0
			qty_remark = (
				f"{acceptance_pct:.1f}% accepted "
				f"({total_accepted} / {total_received} units) — critical rejection rate."
			)

	# ── 3. Final composite score ────────────────────────────────────────────
	raw_score   = (timeliness_score + qty_score) / 2
	final_score = round(max(1.0, min(5.0, raw_score)), 2)   # Clamp to [1.0, 5.0]

	combined_remarks = (
		f"Auto-rated by Vendor Portal scheduler.\n"
		f"Timeliness ({timeliness_score}/5): {timeliness_remark}\n"
		f"Qty Accuracy ({qty_score}/5): {qty_remark}"
	)

	# Fetch the linked Purchase Order (first item's PO, if any)
	po_name = frappe.db.get_value(
		"Purchase Receipt Item",
		{"parent": pr_name},
		"purchase_order",
	)

	# Insert a new Vendor Rating Log (naming series auto-applied via DocType config)
	log_doc = frappe.get_doc({
		"doctype":          "Vendor Rating Log",
		"supplier":         supplier,
		"purchase_receipt": pr_name,
		"purchase_order":   po_name,
		"rating_type":      "Delivery",
		"score":            final_score,
		"remarks":          combined_remarks,
		"rated_by":         "Administrator",   # System-originated entry
		"rating_date":      nowdate(),
	})
	log_doc.insert(ignore_permissions=True)

	frappe.logger("vendor_portal.tasks").debug(
		f"  → PR {pr_name}: timeliness={timeliness_score}, qty={qty_score}, "
		f"final={final_score}"
	)


# ─────────────────────────────────────────────────────────────────────────────
#  TASK 3 — Weekly: Vendor Performance Digest
# ─────────────────────────────────────────────────────────────────────────────

def send_vendor_performance_digest():
	"""
	Scheduled weekly job.

	Compiles a weekly vendor performance summary and emails it to all users
	holding the 'Vendor Manager' role. The digest includes:
	  • KPI tiles: POs raised, new onboardings, vendors below threshold
	  • Top-5 vendors by average rating this week
	  • Bottom-5 vendors by average rating this week
	  • Full list of vendors currently below the low-rating threshold
	"""
	frappe.logger("vendor_portal.tasks").info("Starting: send_vendor_performance_digest")

	try:
		settings   = _get_settings()
		mgr_emails = _get_vendor_manager_emails()
		threshold  = settings["low_rating_threshold"]
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"send_vendor_performance_digest: setup phase failed",
		)
		return

	if not mgr_emails:
		frappe.logger("vendor_portal.tasks").info(
			"send_vendor_performance_digest: no Vendor Manager emails found — skipping"
		)
		return

	# Week boundary: from the Monday of the current week through today
	today      = getdate(nowdate())
	week_start = get_first_day(today)   # Frappe's get_first_day returns Mon of the week
	week_end   = today

	try:
		html_body = _build_digest_html(threshold, week_start, week_end)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"send_vendor_performance_digest: HTML build failed",
		)
		return

	subject = f"📊 Weekly Vendor Performance Digest — week ending {week_end}"

	try:
		frappe.sendmail(
			recipients=mgr_emails,
			subject=subject,
			message=html_body,
			delayed=False,
		)
		frappe.logger("vendor_portal.tasks").info(
			f"Completed: send_vendor_performance_digest — "
			f"sent to {len(mgr_emails)} recipient(s)"
		)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"send_vendor_performance_digest: sendmail failed",
		)


def _build_digest_html(threshold, week_start, week_end):
	"""
	Builds and returns the full HTML body string for the weekly digest.
	All data is fetched from the database with lightweight get_all calls.
	"""
	# ── Weekly rating logs ───────────────────────────────────────────────────
	weekly_logs = frappe.get_all(
		"Vendor Rating Log",
		filters={"rating_date": ["between", [week_start, week_end]]},
		fields=["supplier", "score"],
	)

	# Build per-supplier score lists
	supplier_scores = {}
	for log in weekly_logs:
		sid = log["supplier"]
		supplier_scores.setdefault(sid, []).append(flt(log["score"]))

	# Rank suppliers by average score
	ranked = []
	for sid, scores in supplier_scores.items():
		avg  = round(sum(scores) / len(scores), 2)
		sname = frappe.db.get_value("Supplier", sid, "supplier_name") or sid
		ranked.append({
			"id":    sid,
			"name":  sname,
			"avg":   avg,
			"count": len(scores),
		})

	ranked.sort(key=lambda x: x["avg"], reverse=True)
	top_5    = ranked[:5]
	bottom_5 = list(reversed(ranked[-5:]))   # Lowest first

	# ── Purchase Orders raised this week ────────────────────────────────────
	po_count = frappe.db.count(
		"Purchase Order",
		filters={
			"docstatus": 1,
			"transaction_date": ["between", [week_start, week_end]],
		},
	)

	# ── New vendor onboardings this week ────────────────────────────────────
	new_onboardings = frappe.db.count(
		"Vendor Onboarding",
		filters={"creation": ["between", [week_start, week_end]]},
	)

	# ── Vendors currently below the threshold ────────────────────────────────
	# custom_vendor_rating is stored as 0–1; threshold is 1–5.
	threshold_0to1 = threshold / 5.0
	below_threshold = frappe.get_all(
		"Supplier",
		filters={
			"disabled": 0,
			"custom_vendor_rating": ["not in", [0, ""]],
			"custom_vendor_rating": ["<", threshold_0to1],
		},
		fields=["name", "supplier_name", "custom_vendor_rating"],
		order_by="custom_vendor_rating asc",
	)

	# ── HTML helpers ─────────────────────────────────────────────────────────
	TH_STYLE = "padding:8px 14px; text-align:left;"
	TD_STYLE = "padding:7px 14px;"

	def _vendor_table(rows, heading, row_bg):
		if not rows:
			return (
				f"<h3 style='color:#333; margin-top:24px;'>{heading}</h3>"
				"<p style='color:#888;'><em>No data for this period.</em></p>"
			)
		header = (
			f"<h3 style='color:#1a1a2e; margin-top:24px;'>{heading}</h3>"
			"<table style='width:100%; border-collapse:collapse; font-size:14px; "
			"border:1px solid #ddd;'>"
			"<thead><tr style='background:#1a1a2e; color:#fff;'>"
			f"<th style='{TH_STYLE}'>#</th>"
			f"<th style='{TH_STYLE}'>Supplier ID</th>"
			f"<th style='{TH_STYLE}'>Supplier Name</th>"
			f"<th style='{TH_STYLE}'>Avg Rating (This Week)</th>"
			f"<th style='{TH_STYLE}'>Ratings This Week</th>"
			"</tr></thead><tbody>"
		)
		body = "".join(
			f"<tr style='background:{row_bg};'>"
			f"<td style='{TD_STYLE}'>{i + 1}</td>"
			f"<td style='{TD_STYLE}'>{r['id']}</td>"
			f"<td style='{TD_STYLE}'>{r['name']}</td>"
			f"<td style='{TD_STYLE}'><strong>{r['avg']} / 5.0</strong></td>"
			f"<td style='{TD_STYLE}'>{r['count']}</td>"
			"</tr>"
			for i, r in enumerate(rows)
		)
		return header + body + "</tbody></table>"

	top_table    = _vendor_table(top_5,    "🏆 Top 5 Vendors — This Week",    "#e8f5e9")
	bottom_table = _vendor_table(bottom_5, "⚠️ Bottom 5 Vendors — This Week", "#fff8e1")

	# Below-threshold section
	if below_threshold:
		bt_rows = "".join(
			f"<tr style='background:#ffebee;'>"
			f"<td style='{TD_STYLE}'>{s['name']}</td>"
			f"<td style='{TD_STYLE}'>{s['supplier_name']}</td>"
			f"<td style='{TD_STYLE}; color:#c62828; font-weight:bold;'>"
			f"{flt(s['custom_vendor_rating'] * 5)} / 5.0</td>"
			"</tr>"
			for s in below_threshold
		)
		bt_section = (
			f"<h3 style='color:#c62828; margin-top:24px;'>🚨 Vendors Below "
			f"Rating Threshold (&lt; {threshold})</h3>"
			"<table style='width:100%; border-collapse:collapse; font-size:14px; "
			"border:1px solid #ddd;'>"
			"<thead><tr style='background:#c62828; color:#fff;'>"
			f"<th style='{TH_STYLE}'>Supplier ID</th>"
			f"<th style='{TH_STYLE}'>Supplier Name</th>"
			f"<th style='{TH_STYLE}'>Current Rating</th>"
			"</tr></thead><tbody>"
			+ bt_rows
			+ "</tbody></table>"
		)
	else:
		bt_section = (
			"<h3 style='color:#2e7d32; margin-top:24px;'>✅ All Vendors Above Threshold</h3>"
			f"<p>No vendors are currently below the {threshold} rating threshold. "
			"Great work!</p>"
		)

	# ── Assemble full HTML ───────────────────────────────────────────────────
	html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0; padding:24px; background:#f0f2f5;
             font-family:'Segoe UI',Arial,sans-serif; color:#222;">
  <div style="max-width:780px; margin:auto; background:#fff; border-radius:10px;
              padding:36px; box-shadow:0 4px 16px rgba(0,0,0,.10);">

    <!-- Header -->
    <h1 style="margin:0 0 4px; color:#1a1a2e; font-size:24px;">
      📊 Weekly Vendor Performance Digest
    </h1>
    <p style="margin:0 0 24px; color:#666; font-size:14px;">
      Period: <strong>{week_start}</strong> → <strong>{week_end}</strong>
    </p>

    <!-- KPI tiles -->
    <table style="width:100%; border-collapse:separate; border-spacing:12px 0;
                  margin-bottom:8px;">
      <tr>
        <td style="background:#e8f5e9; border-radius:8px; padding:18px;
                   text-align:center; width:33%;">
          <div style="font-size:30px; font-weight:700; color:#2e7d32;">{po_count}</div>
          <div style="font-size:12px; color:#555; margin-top:4px;">Purchase Orders Raised</div>
        </td>
        <td style="background:#e3f2fd; border-radius:8px; padding:18px;
                   text-align:center; width:33%;">
          <div style="font-size:30px; font-weight:700; color:#1565c0;">{new_onboardings}</div>
          <div style="font-size:12px; color:#555; margin-top:4px;">New Vendor Onboardings</div>
        </td>
        <td style="background:#ffebee; border-radius:8px; padding:18px;
                   text-align:center; width:33%;">
          <div style="font-size:30px; font-weight:700; color:#c62828;">{len(below_threshold)}</div>
          <div style="font-size:12px; color:#555; margin-top:4px;">
            Vendors Below Threshold ({threshold})
          </div>
        </td>
      </tr>
    </table>

    <!-- Vendor ranking tables -->
    {top_table}
    <br>
    {bottom_table}
    <br>
    {bt_section}

    <!-- Footer -->
    <hr style="margin:32px 0 16px; border:none; border-top:1px solid #eee;">
    <p style="font-size:11px; color:#aaa; margin:0;">
      Auto-generated by Vendor Portal scheduler on
      {now_datetime().strftime("%Y-%m-%d %H:%M:%S")}. Do not reply to this email.
    </p>
  </div>
</body>
</html>"""
	return html


# ─────────────────────────────────────────────────────────────────────────────
#  TASK 4 — Cron (0 9 * * *): Auto-Expire Stale Onboardings
# ─────────────────────────────────────────────────────────────────────────────

def expire_stale_onboardings():
	"""
	Cron job that runs every day at 09:00 AM server time.

	Scans all Vendor Onboarding records with status "Under Review":

	  • > 7 days old  → Send a reminder email to Vendor Managers warning that
	                     auto-rejection is approaching.
	  • > 14 days old → Auto-reject: set status to "Rejected", write the system
	                     rejection reason, and notify Vendor Managers.

	We use the record's `modified` timestamp as a proxy for when the status
	transitioned to "Under Review" (the workflow sets it at that point).
	Using frappe.db.set_value bypasses the read_only constraint on
	onboarding_status — the correct pattern for system-side overrides in Frappe.
	"""
	frappe.logger("vendor_portal.tasks").info("Starting: expire_stale_onboardings")

	today           = getdate(nowdate())
	reminder_cutoff = add_days(today, -7)    # Modified more than 7 days ago → reminder
	reject_cutoff   = add_days(today, -14)   # Modified more than 14 days ago → auto-reject

	try:
		stale_records = frappe.get_all(
			"Vendor Onboarding",
			filters={"onboarding_status": "Under Review"},
			fields=["name", "supplier_name", "email", "modified"],
			order_by="modified asc",   # Process oldest first
		)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"expire_stale_onboardings: failed to query Vendor Onboarding",
		)
		return

	if not stale_records:
		frappe.logger("vendor_portal.tasks").info(
			"expire_stale_onboardings: no 'Under Review' records found"
		)
		return

	try:
		mgr_emails = _get_vendor_manager_emails()
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"expire_stale_onboardings: could not fetch Vendor Manager emails",
		)
		mgr_emails = []

	reminder_count = 0
	rejected_count = 0

	for record in stale_records:
		record_name   = record["name"]
		supplier_name = record.get("supplier_name") or record_name
		modified_date = getdate(record["modified"])

		try:
			if modified_date <= reject_cutoff:
				# ── AUTO-REJECT (> 14 days) ──────────────────────────────────
				_auto_reject_onboarding(record_name, supplier_name, mgr_emails)
				rejected_count += 1

			elif modified_date <= reminder_cutoff:
				# ── REMINDER (7–14 days) ──────────────────────────────────────
				days_pending = (today - modified_date).days
				_send_stale_reminder(record_name, supplier_name, days_pending, mgr_emails)
				reminder_count += 1

			# < 7 days old — no action yet

		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				f"expire_stale_onboardings: error handling record {record_name}",
			)

	frappe.logger("vendor_portal.tasks").info(
		f"Completed: expire_stale_onboardings — "
		f"{reminder_count} reminder(s) sent, {rejected_count} auto-rejected"
	)


def _auto_reject_onboarding(record_name, supplier_name, mgr_emails):
	"""
	Writes the Rejected status and auto-rejection reason to the given
	Vendor Onboarding record, then emails Vendor Managers.

	frappe.db.set_value is used here intentionally to bypass the
	read_only=1 constraint on onboarding_status — this is the standard
	Frappe pattern for scheduler / system-side field updates.
	"""
	rejection_reason = (
		"Auto-rejected: Review period expired. "
		"The application remained in 'Under Review' status for more than 14 days "
		"without action. Please re-initiate the onboarding process if required."
	)

	frappe.db.set_value(
		"Vendor Onboarding",
		record_name,
		{
			"onboarding_status": "Rejected",
			"rejection_reason":  rejection_reason,
		},
		update_modified=True,   # Stamp the modification time so audits are accurate
	)

	frappe.logger("vendor_portal.tasks").info(
		f"  → Auto-rejected: {record_name} ({supplier_name})"
	)

	if not mgr_emails:
		return

	subject = f"🚫 Vendor Onboarding Auto-Rejected — {supplier_name}"
	message = f"""
<p>Dear Vendor Manager,</p>
<p>The Vendor Onboarding request <strong>{record_name}</strong> for
<strong>{supplier_name}</strong> has been <strong>automatically rejected</strong>
by the Vendor Portal scheduler because it remained in "Under Review" status for
more than <strong>14 days</strong> without a decision.</p>
<p><strong>System Rejection Reason:</strong><br>{rejection_reason}</p>
<p>If this rejection was unintended, please re-initiate the onboarding process
for this vendor.</p>
<br>
<p style="color:#888; font-size:12px;">
  This is an automated notification from the Vendor Portal scheduler — {nowdate()}.
</p>
"""
	frappe.sendmail(
		recipients=mgr_emails,
		subject=subject,
		message=message,
		delayed=False,
	)


def _send_stale_reminder(record_name, supplier_name, days_pending, mgr_emails):
	"""
	Sends a reminder email to Vendor Managers about an onboarding that has
	been sitting in "Under Review" for 7–14 days.
	"""
	if not mgr_emails:
		return   # No recipients; nothing to do

	days_remaining = 14 - days_pending
	urgency_color  = "#e65100" if days_remaining <= 3 else "#f57c00"

	subject = (
		f"⏰ Action Required: Vendor Onboarding Pending Review — {supplier_name} "
		f"({days_pending} days)"
	)
	message = f"""
<p>Dear Vendor Manager,</p>
<p>The Vendor Onboarding request <strong>{record_name}</strong> for
<strong>{supplier_name}</strong> has been awaiting review for
<strong style="color:{urgency_color};">{days_pending} day(s)</strong>.</p>
<p>⚠️ If no action is taken within
<strong style="color:{urgency_color};">{days_remaining} more day(s)</strong>,
this application will be <strong>automatically rejected</strong> by the system.</p>
<p>Please log in and approve or reject this application as soon as possible.</p>
<br>
<p style="color:#888; font-size:12px;">
  This is an automated reminder from the Vendor Portal scheduler — {nowdate()}.
</p>
"""
	frappe.sendmail(
		recipients=mgr_emails,
		subject=subject,
		message=message,
		delayed=False,
	)

	frappe.logger("vendor_portal.tasks").debug(
		f"  → Reminder sent: {record_name} ({supplier_name}), "
		f"{days_pending} days pending, {days_remaining} days until auto-reject"
	)
