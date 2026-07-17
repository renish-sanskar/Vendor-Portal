# Override Strategies: `override_doctype_class` vs `doc_events`

Frappe v16 offers two mechanisms to extend standard DocType behaviour. This project
uses both — each chosen for the problem it solves best.

---

## Approaches used in this project

| DocType | Mechanism | File |
|---|---|---|
| Purchase Order | `override_doctype_class` | `vendor_portal/buying/custom/purchase_order.py` |
| Purchase Receipt | `doc_events` | `vendor_portal/overrides/purchase_receipt.py` |

---

## `override_doctype_class` — Class inheritance

**How it works:** You subclass the original controller and register it via
`hooks.py`. Frappe replaces the original class with your subclass at runtime.
Your methods call `super()` to preserve the original logic.

**When to use:**
- You need to **add** logic before/after existing methods (validate, on_submit,
  on_cancel, etc.)
- You need to **intercept** existing method logic — call `super()` at the
  right point in your override
- You want access to `self` (the document) and full class-level features
- Your extension is tightly coupled to the DocType's lifecycle

**Trade-offs:**
- ✅ Full access to the class — `self`, instance methods, properties
- ✅ You control the call order — place `super()` wherever you need it
- ✅ Works for any method, including ones not exposed as hooks
- ❌ Only one app can override a given DocType — conflict if two apps try
- ❌ Harder to debug — the original class is replaced at import time
- ❌ Must re-export fixtures if the DocType structure changes

---

## `doc_events` — Event-driven hooks

**How it works:** You register standalone functions in `hooks.py` under
`doc_events`. Frappe calls your function **in addition to** the original
controller method — think of it as an event listener.

**When to use:**
- You only need to react to a few events (`validate`, `on_submit`, etc.)
- You want loose coupling — your code runs alongside the original logic
- Multiple apps need to hook into the same DocType (no conflicts)
- Your logic is simple enough to fit in stateless functions

**Trade-offs:**
- ✅ Multiple apps can hook the same event without conflicts
- ✅ Lightweight — no class hierarchy to maintain
- ✅ Easy to test — functions accept `(doc, method)` and are pure
- ✅ Easy to toggle on/off — just remove the hook entry
- ❌ No access to `self` — you receive the `doc` object as a parameter
- ❌ You cannot control **when** your code runs relative to the original
  method (it always fires after the original `validate`/`on_submit` etc.)
- ❌ Cannot override methods that aren't hook points (e.g. `autoname`)

---

## Recommendation

**Prefer `override_doctype_class`** when your extension needs to:

- Control the execution order (e.g. validate before `super()`)
- Access internal methods of the original class
- Override methods that aren't standard hook points

**Prefer `doc_events`** when your extension:

- Only reacts to standard events (`validate`, `on_submit`, `on_cancel`)
- Needs to coexist with other apps hooking the same DocType
- Is a cross-cutting concern (logging, audit, notifications)
- Should be easy to add/remove without touching the core logic

### In this project

The **Purchase Order** override uses `override_doctype_class` because it needs
to call `super().validate()` before running custom checks, and because it adds
methods (`_check_blacklist`, `_check_rating_threshold`) that are tightly coupled
to the PO lifecycle.

The **Purchase Receipt** override uses `doc_events` because it only reacts to
two events (`validate` and `on_submit`) with self-contained logic that doesn't
need to modify the original class behaviour — it just observes and creates
rating log entries.
