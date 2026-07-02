# =============================================================================
#  vendor_portal/hooks.py
#
#  Central Frappe configuration file for the Vendor Portal app.
#  Every registration — document events, class overrides, scheduled tasks,
#  fixtures, frontend assets, Jinja helpers, and permission hooks — lives here.
#
#  Sections (use Ctrl-F / Cmd-F on the section headings to jump quickly):
#    1.  App Metadata
#    2.  DocType Class Overrides
#    3.  Document Events
#    4.  Scheduled Background Jobs (scheduler_events)
#    5.  Fixtures  (data exported via `bench export-fixtures`)
#    6.  Frontend Assets
#    7.  Jinja Extensions
#    8.  Permission Hooks
# =============================================================================


# -----------------------------------------------------------------------------
#  1. App Metadata
#  Standard boilerplate required by Frappe's app registry.
# -----------------------------------------------------------------------------

app_name        = "vendor_portal"
app_title       = "Vendor Portal"
app_publisher   = "renish"
app_description = "Vendor management module for ERPNext"
app_email       = "renish@sanskartechnolab.com"
app_license     = "mit"


# -----------------------------------------------------------------------------
#  1b. Website & Self-Service Portal
#
#  website_route_rules maps URL slugs → www/ page files so Frappe's web server
#  serves them as public (guest-accessible) pages.
#
#  guest_methods whitelists the dotted Python paths that unauthenticated
#  browsers may call via frappe.call().  Without this entry Frappe would
#  return a 403 for the form submission on /vendor-register.
# -----------------------------------------------------------------------------

website_route_rules = [
	{"from_route": "/vendor-register", "to_route": "vendor-register"},
	{"from_route": "/vendor-status",   "to_route": "vendor-status"},
]

guest_methods = [
	"vendor_portal.vendor_portal.www.portal_api.get_vendor_categories",
	"vendor_portal.vendor_portal.www.portal_api.submit_vendor_application",
]


# -----------------------------------------------------------------------------
#  2. DocType Class Overrides
#
#  Replaces ERPNext's built-in PurchaseOrder controller with a custom subclass.
#  The custom class inherits from PurchaseOrder so all standard behaviour is
#  preserved; only vendor-portal additions are injected.
#
#  VERIFIED PATH:
#    File  : vendor_portal/vendor_portal/buying/custom/purchase_order.py
#    Class : CustomPurchaseOrder  (line 8)
#    Module: vendor_portal.vendor_portal.buying.custom.purchase_order
#
#  Reference: https://frappeframework.com/docs/user/en/python-api/document
# -----------------------------------------------------------------------------

override_doctype_class = {
	"Purchase Order": (
		"vendor_portal.vendor_portal.buying.custom.purchase_order.CustomPurchaseOrder"
	),
}


# -----------------------------------------------------------------------------
#  3. Document Events
#
#  Hooks into Frappe's document lifecycle for specific DocTypes.
#  Multiple hooks for the same event can be expressed as a list of strings.
#
#  VERIFIED PATHS:
#    Purchase Receipt  → overrides/purchase_receipt.py  (validate, on_submit — separate fns)
#    Vendor Onboarding → events/vendor_onboarding.py    (send_welcome_email)
#    Supplier          → events/supplier.py              (check_blacklist_status)
#
#  NOTE: The user's requirement asked for a single `handle` function for PR,
#  but the actual file on disk defines separate `validate` and `on_submit`
#  functions.  hooks.py is corrected to match the file that actually exists.
#
#  Reference: https://frappeframework.com/docs/user/en/python-api/hooks#document-hooks
# -----------------------------------------------------------------------------

doc_events = {

	# ── Purchase Receipt ─────────────────────────────────────────────────────
	# File: vendor_portal/overrides/purchase_receipt.py
	# • validate  — detects short deliveries, sets doc.flags.has_short_delivery
	# • on_submit — auto-creates a Vendor Rating Log (Delivery type)
	"Purchase Receipt": {
		"validate":  "vendor_portal.overrides.purchase_receipt.validate",
		"on_submit": "vendor_portal.overrides.purchase_receipt.on_submit",
	},

	# ── Vendor Onboarding ────────────────────────────────────────────────────
	# Fires immediately after a new Vendor Onboarding record is inserted.
	# Sends a welcome/acknowledgement email to the applicant.
	# File: vendor_portal/events/vendor_onboarding.py
	"Vendor Onboarding": {
		"after_insert": (
			"vendor_portal.events.vendor_onboarding.send_welcome_email"
		),
	},

	# ── Supplier ─────────────────────────────────────────────────────────────
	# Runs whenever a Supplier document is saved/updated.
	# Evaluates the custom_is_blacklisted flag and triggers downstream actions
	# (e.g., cancelling open POs, alerting Purchase Managers).
	# File: vendor_portal/events/supplier.py
	"Supplier": {
		"on_update": (
			"vendor_portal.events.supplier.check_blacklist_status"
		),
	},
}


# -----------------------------------------------------------------------------
#  4. Scheduled Background Jobs
#
#  Frappe v15 scheduler_events keys:
#    "all"     — every ~3 minutes (avoid for expensive ops)
#    "hourly"  — once per hour
#    "daily"   — once per day  (run time set in site_config.json, default 00:00)
#    "weekly"  — once per week (Monday at the daily run time)
#    "monthly" — once per month
#    "cron"    — arbitrary cron expression
#
#  Each standard key maps to a LIST of fully-qualified Python function paths.
#  The "cron" key is a nested dict: { "<cron_expr>": { "functions": [...] } }
#
#  VERIFIED FUNCTION NAMES (grep against tasks.py):
#    Line  91 → calculate_vendor_ratings         (mapped as daily[0])
#    Line 262 → auto_rate_deliveries              (mapped as hourly[0])
#    Line 484 → send_vendor_performance_digest    (mapped as weekly[0])
#    Line 742 → expire_stale_onboardings          (mapped as cron)
#
#  NOTE: tasks.py does NOT define `auto_calculate_vendor_ratings`,
#  `daily_stale_onboarding_check`, `vendor_performance_digest`, or
#  `auto_expire_stale_onboardings`.  hooks.py is corrected to exactly
#  match the function names that exist in tasks.py.
#
#  Reference: https://frappeframework.com/docs/user/en/python-api/hooks#scheduler-events
#  Implementation: see vendor_portal/tasks.py
# -----------------------------------------------------------------------------

scheduler_events = {

	# ── Daily ─────────────────────────────────────────────────────────────────
	# Frappe calls all functions in this list sequentially, once per day.
	"daily": [
		# tasks.py:91  — Recalculate weighted vendor ratings for every active
		# Supplier and dispatch low-rating alert emails to Vendor Managers.
		"vendor_portal.tasks.calculate_vendor_ratings",
	],

	# ── Hourly ────────────────────────────────────────────────────────────────
	# tasks.py:262 — Auto-create Delivery Vendor Rating Log entries for
	# submitted Purchase Receipts from the past 2 hours not yet rated.
	"hourly": [
		"vendor_portal.tasks.auto_rate_deliveries",
	],

	# ── Weekly ────────────────────────────────────────────────────────────────
	# tasks.py:484 — Compile and email a rich HTML vendor performance digest
	# to all Vendor Manager role users (top/bottom 5, KPIs, threshold list).
	"weekly": [
		"vendor_portal.tasks.send_vendor_performance_digest",
	],

	# ── Cron ──────────────────────────────────────────────────────────────────
	# "0 9 * * *" → runs at 09:00 AM server time every day.
	# tasks.py:742 — Scan "Under Review" onboardings:
	#   • > 7 days  → send reminder to Vendor Managers
	#   • > 14 days → auto-reject the application and notify
	#
	# This cron job runs at a fixed morning hour so auto-rejection notifications
	# arrive at the start of the business day, separate from the midnight daily run.
	#
	# NOTE: This Frappe version's scheduler (insert_cron_jobs) expects the cron
	# expression to map DIRECTLY to a list of method paths — NOT a nested
	# {"functions": [...]} dict. Using the dict form makes the sync iterate the
	# literal key "functions", producing: "functions is not a valid method".
	"cron": {
		"0 9 * * *": [
			"vendor_portal.tasks.expire_stale_onboardings",
		],
	},
}


# -----------------------------------------------------------------------------
#  5. Fixtures
#
#  Defines which configuration records are exported when running:
#    bench --site <site> export-fixtures
#
#  Each entry is a dict with:
#    "dt"      → DocType name (required)
#    "filters" → optional list of [fieldname, operator, value] filter tuples
#                (same syntax as frappe.get_all filters)
#
#  Best practice: keep filters as tight as possible so fixtures don't export
#  unrelated records from other apps installed on the same site.
#
#  Reference: https://frappeframework.com/docs/user/en/python-api/hooks#fixtures
# -----------------------------------------------------------------------------

fixtures = [

	# ── Custom Fields ──────────────────────────────────────────────────────────
	# Export only the custom fields this app adds to the Supplier DocType.
	# Filtering by both `dt` and `fieldname` prevents accidentally exporting
	# custom fields created by other apps on the same Supplier form.
	{
		"dt": "Custom Field",
		"filters": [
			["dt", "=", "Supplier"],
			["fieldname", "in", [
				"custom_vendor_category",
				"custom_vendor_rating",
				"custom_total_rating_count",
				"custom_onboarding_reference",
				"custom_is_blacklisted",
				"custom_blacklist_reason",
			]],
		],
	},

	# ── Property Setters ───────────────────────────────────────────────────────
	# Captures form-level property overrides applied to the Supplier DocType
	# (e.g., field order changes, mandatory overrides, hidden fields).
	{
		"dt": "Property Setter",
		"filters": [
			["doc_type", "=", "Supplier"],
		],
	},

	# ── Workflow ───────────────────────────────────────────────────────────────
	# Export only the workflow owned by this app.
	{
		"dt": "Workflow",
		"filters": [
			["name", "=", "Vendor Onboarding Workflow"],
		],
	},

	# ── Workflow support records ───────────────────────────────────────────────
	# Workflow Action Master and Workflow State are referenced by the workflow
	# above; exported unconditionally (small, system-level records).
	{"dt": "Workflow Action Master"},
	{"dt": "Workflow State"},

	# ── Roles ─────────────────────────────────────────────────────────────────
	# Export only the custom roles introduced by this app.
	{
		"dt": "Role",
		"filters": [
			["name", "in", ["Vendor Manager", "Purchase Team"]],
		],
	},

	# ── Custom DocPerms ────────────────────────────────────────────────────────
	# Export permission records tied to this app's custom roles so that
	# a fresh install gets the correct role-based access out of the box.
	{
		"dt": "Custom DocPerm",
		"filters": [
			["role", "in", [
				"Vendor Manager",
				"Purchase Manager",
				"Purchase User",
				"Purchase Team",
			]],
		],
	},
]


# -----------------------------------------------------------------------------
#  6. Frontend Assets
#
#  app_include_js / app_include_css
#  ────────────────────────────────
#  Files listed here are injected into *every* Frappe desk page for logged-in
#  users.  Use sparingly — prefer doctype_js for form-specific code.
#
#  VERIFIED PATHS (files that exist on disk):
#    public/js/vendor_portal.bundle.js  ✅  (the compiled bundle — use this)
#    public/js/purchase_order.js        ✅
#    public/js/purchase_order_list.js   ✅
#    public/js/supplier.js              ✅
#    public/css/                        ⚠️  directory exists but is EMPTY
#
#  app_include_js must use the FULL app-prefixed path for global includes.
#  doctype_js uses the shorter relative `public/...` path.
#
#  NOTE on app_include_css: the css/ directory currently has no files.
#  The key is kept here so it takes effect the moment the CSS file is created.
#  Remove or comment it out until vendor_portal.css is committed.
#
#  Reference: https://frappeframework.com/docs/user/en/python-api/hooks#assets
# -----------------------------------------------------------------------------

# Global JS — injected on every desk page.
# Uses the compiled bundle (vendor_portal.bundle.js) which is the file
# that actually exists. Create vendor_portal.js as an alias or rename as needed.
app_include_js = "vendor_portal/public/js/vendor_portal.bundle.js"

# Global CSS — injected on every desk page.
# ⚠️  public/css/ is currently empty. Create this file before enabling.
# app_include_css = "vendor_portal/public/css/vendor_portal.css"

# Form-specific client scripts (loaded only when that DocType form is open)
doctype_js = {
	"Item":           "public/js/item.js",
	"Purchase Order": "public/js/purchase_order.js",
	"Supplier":       "public/js/supplier.js",
}

# List-view specific client scripts
doctype_list_js = {
	"Purchase Order": "public/js/purchase_order_list.js",
}


# -----------------------------------------------------------------------------
#  7. Jinja Extensions
#
#  Extends the Jinja2 environment used by Frappe's print formats, web pages,
#  and email templates.
#
#  Two sub-keys are supported:
#    "methods" → dict of { "name": "dotted.path.to_function" }
#               Exposed as global callables in any Jinja template.
#    "filters" → list of "dotted.path.to_function" strings
#               The function's own name becomes the Jinja filter name.
#
#  VERIFIED:
#    File: vendor_portal/utils/jinja_filters.py
#    Defined function: `stars` (line 4)  ← only this function exists
#    `star_rating` does NOT exist in the file.
#
#  The `methods` key registers `stars` as a named global callable too,
#  so templates can use it both ways:
#    Filter  : {{ doc.custom_vendor_rating | stars }}
#    Method  : {{ stars(doc.custom_vendor_rating) }}
#
#  Reference: https://frappeframework.com/docs/user/en/python-api/jinja
# -----------------------------------------------------------------------------

jinja = {
	# Named callable — use in templates as: {{ stars(score) }}
	# Points to the verified `stars` function in jinja_filters.py.
	"methods": [
		"vendor_portal.utils.jinja_filters.stars",
		"vendor_portal.utils.jinja_filters.scorecard_badge",
	],

	# Traditional filter — use in templates as: {{ score | stars }}
	"filters": [
		"vendor_portal.utils.jinja_filters.stars",
		"vendor_portal.utils.jinja_filters.scorecard_badge",
	],
}


# -----------------------------------------------------------------------------
#  8. Permission Hooks
#
#  has_permission
#  ──────────────
#  Called by Frappe for every document-level permission check.
#  The function signature must be: fn(doc, ptype, user) → True | False | None
#  Returning None defers to standard role-based permission evaluation.
#
#  permission_query_conditions
#  ───────────────────────────
#  Called when Frappe builds a list-view SQL query (frappe.get_list).
#  The function signature must be: fn(user) → SQL WHERE-clause string | ""
#
#  VERIFIED PATHS:
#    File: vendor_portal/vendor_portal/permissions.py
#    Functions defined:
#      vendor_rating_log_has_permission(doc, ptype, user)  → line 3
#      vendor_onboarding_query_conditions(user)            → line 16
#
#  The hooks.py previously pointed these two DocTypes to a non-existent unified
#  `vendor_portal.permissions` module.  Corrected below to the functions that
#  actually exist in vendor_portal.vendor_portal.permissions.
#
#  Reference: https://frappeframework.com/docs/user/en/python-api/hooks#permission-hooks
# -----------------------------------------------------------------------------

has_permission = {
	# Vendor Rating Log — restricts write access: only the rated_by user or
	# a Vendor Manager can modify a rating log.
	# Function: vendor_rating_log_has_permission(doc, ptype, user)
	"Vendor Rating Log": (
		"vendor_portal.vendor_portal.permissions.vendor_rating_log_has_permission"
	),
}

permission_query_conditions = {
	# Vendor Onboarding — Vendor Managers see all records; Purchase Users see
	# only records they own; all others see nothing extra.
	# Function: vendor_onboarding_query_conditions(user)
	"Vendor Onboarding": (
		"vendor_portal.vendor_portal.permissions.vendor_onboarding_query_conditions"
	),
}
