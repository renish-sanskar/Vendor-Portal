"""
Vendor Portal — hooks.py completeness verifier.

Checks every registered path in hooks.py resolves to the correct callable
or file on disk.  Run with:

    bench --site <site> execute vendor_portal.verify_hooks.run
"""
import os
import importlib

# Resolve the bench root from this file's absolute path.
# This file lives at:  <bench>/apps/vendor_portal/vendor_portal/verify_hooks.py
# dirname x1 → <bench>/apps/vendor_portal/vendor_portal/
# dirname x2 → <bench>/apps/vendor_portal/
# dirname x3 → <bench>/apps/
# dirname x4 → <bench>/   ← bench root
_THIS_FILE  = os.path.abspath(__file__)
_BENCH_ROOT = os.path.dirname(  # x4 = bench root
    os.path.dirname(            # x3 = apps/
        os.path.dirname(        # x2 = apps/vendor_portal/
            os.path.dirname(    # x1 = apps/vendor_portal/vendor_portal/
                _THIS_FILE
            )
        )
    )
)


def _bench(rel):
    """Return an absolute path relative to the bench root."""
    return os.path.join(_BENCH_ROOT, rel)


# ─────────────────────────────────────────────────────────────────────────────
#  Checks table
#  Each entry: (label, module_path, attr_name, expected_kind)
#  expected_kind: "function" | "class" | "any"
# ─────────────────────────────────────────────────────────────────────────────

PYTHON_CHECKS = [
    # doc_events
    ("doc_events / Purchase Receipt.validate",
     "vendor_portal.overrides.purchase_receipt", "validate", "function"),
    ("doc_events / Purchase Receipt.on_submit",
     "vendor_portal.overrides.purchase_receipt", "on_submit", "function"),
    ("doc_events / Vendor Onboarding.after_insert",
     "vendor_portal.events.vendor_onboarding", "send_welcome_email", "function"),
    ("doc_events / Supplier.on_update",
     "vendor_portal.events.supplier", "check_blacklist_status", "function"),
    # override_doctype_class
    ("override_doctype_class / Purchase Order",
     "vendor_portal.vendor_portal.buying.custom.purchase_order",
     "CustomPurchaseOrder", "class"),
    # scheduler_events
    ("scheduler daily   / calculate_vendor_ratings",
     "vendor_portal.tasks", "calculate_vendor_ratings", "function"),
    ("scheduler hourly  / auto_rate_deliveries",
     "vendor_portal.tasks", "auto_rate_deliveries", "function"),
    ("scheduler weekly  / send_vendor_performance_digest",
     "vendor_portal.tasks", "send_vendor_performance_digest", "function"),
    ("scheduler cron    / expire_stale_onboardings",
     "vendor_portal.tasks", "expire_stale_onboardings", "function"),
    # jinja
    ("jinja.methods / stars",
     "vendor_portal.utils.jinja_filters", "stars", "function"),
    ("jinja.methods / scorecard_badge",
     "vendor_portal.utils.jinja_filters", "scorecard_badge", "function"),
    # permission hooks
    ("has_permission / Vendor Rating Log",
     "vendor_portal.vendor_portal.permissions",
     "vendor_rating_log_has_permission", "function"),
    ("permission_query_conditions / Vendor Onboarding",
     "vendor_portal.vendor_portal.permissions",
     "vendor_onboarding_query_conditions", "function"),
    # guest_methods
    ("guest_methods / get_vendor_categories",
     "vendor_portal.vendor_portal.www.portal_api",
     "get_vendor_categories", "function"),
    ("guest_methods / submit_vendor_application",
     "vendor_portal.vendor_portal.www.portal_api",
     "submit_vendor_application", "function"),
]

JS_FILES = [
    ("app_include_js",
     _bench("apps/vendor_portal/vendor_portal/public/js/vendor_portal.bundle.js")),
    ("doctype_js / Item",
     _bench("apps/vendor_portal/vendor_portal/public/js/item.js")),
    ("doctype_js / Purchase Order",
     _bench("apps/vendor_portal/vendor_portal/public/js/purchase_order.js")),
    ("doctype_js / Supplier",
     _bench("apps/vendor_portal/vendor_portal/public/js/supplier.js")),
    ("doctype_list_js / Purchase Order",
     _bench("apps/vendor_portal/vendor_portal/public/js/purchase_order_list.js")),
]

FIXTURE_BASE = _bench("apps/vendor_portal/vendor_portal/fixtures/")

FIXTURE_FILES = [
    "custom_docperm.json",
    "custom_field.json",
    "property_setter.json",
    "role.json",
    "workflow.json",
    "workflow_action_master.json",
    "workflow_state.json",
]


def _sep(title=""):
    w = 60
    print(f"\n{'─' * 3} {title} {'─' * (w - len(title) - 4)}" if title else "─" * w)


def run():
    passed = failed = 0

    # ── Python callables ─────────────────────────────────────────────────────
    _sep("Python callables")
    for label, mod_path, attr, kind in PYTHON_CHECKS:
        try:
            mod = importlib.import_module(mod_path)
            obj = getattr(mod, attr, None)
            if obj is None:
                raise AttributeError(f"{attr!r} not found in {mod_path}")
            if kind == "function" and not callable(obj):
                raise TypeError(f"{attr!r} exists but is not callable")
            if kind == "class" and not isinstance(obj, type):
                raise TypeError(f"{attr!r} exists but is not a class")
            print(f"  ✅  {label}")
            passed += 1
        except Exception as exc:
            print(f"  ❌  {label}")
            print(f"       → {exc}")
            failed += 1

    # ── JavaScript files ─────────────────────────────────────────────────────
    _sep("JavaScript files")
    for label, path in JS_FILES:
        if os.path.isfile(path):
            size = os.path.getsize(path)
            print(f"  ✅  {label}  ({size:,} bytes)")
            passed += 1
        else:
            print(f"  ❌  MISSING: {label}  →  {path}")
            failed += 1

    # ── Fixture JSON files ───────────────────────────────────────────────────
    _sep("Fixture files")
    for fname in FIXTURE_FILES:
        path = FIXTURE_BASE + fname
        if os.path.isfile(path):
            size = os.path.getsize(path)
            print(f"  ✅  {fname}  ({size:,} bytes)")
            passed += 1
        else:
            print(f"  ❌  MISSING: {fname}")
            failed += 1

    # ── hooks.py self-consistency via importlib ───────────────────────────────
    _sep("hooks.py structure")
    try:
        hooks = importlib.import_module("vendor_portal.hooks")

        se = hooks.scheduler_events
        assert "vendor_portal.tasks.calculate_vendor_ratings"       in se.get("daily",  [])
        assert "vendor_portal.tasks.auto_rate_deliveries"            in se.get("hourly", [])
        assert "vendor_portal.tasks.send_vendor_performance_digest"  in se.get("weekly", [])
        # Cron maps the expression directly to a list of method paths
        # (this Frappe version does NOT support the {"functions": [...]} wrapper).
        cron_fns = [fn for methods in se.get("cron", {}).values() for fn in methods]
        assert "vendor_portal.tasks.expire_stale_onboardings" in cron_fns
        print("  ✅  scheduler_events — all 4 entries registered correctly")

        assert "Purchase Order" in hooks.override_doctype_class
        print("  ✅  override_doctype_class — Purchase Order present")

        assert "Purchase Receipt" in hooks.doc_events
        assert "Vendor Onboarding" in hooks.doc_events
        assert "Supplier" in hooks.doc_events
        print("  ✅  doc_events — Purchase Receipt, Vendor Onboarding, Supplier")

        assert len(hooks.jinja.get("methods", [])) >= 2
        assert len(hooks.jinja.get("filters", [])) >= 2
        print("  ✅  jinja — methods and filters both populated")

        assert "Vendor Rating Log" in hooks.has_permission
        assert "Vendor Onboarding" in hooks.permission_query_conditions
        print("  ✅  permission hooks — has_permission + permission_query_conditions")

        assert len(hooks.fixtures) >= 6
        print(f"  ✅  fixtures — {len(hooks.fixtures)} entries defined")

        passed += 6
    except Exception as exc:
        print(f"  ❌  hooks structure check failed: {exc}")
        failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    _sep()
    total = passed + failed
    print(f"\n  Result: {passed}/{total} checks passed", end="")
    if failed:
        print(f"  —  {failed} FAILED ❌")
    else:
        print("  —  ALL PASS ✅")
    print()
