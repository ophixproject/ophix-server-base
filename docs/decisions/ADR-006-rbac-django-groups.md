# ADR-006: RBAC for admin UI using Django groups

**Date:** 2026-05-04
**Status:** Accepted — not yet implemented

## Context

Ophix is a multi-operator platform. As the fleet grows, different operators need scoped visibility into the admin UI — a user responsible for the London DC should not see credentials or hosts belonging to the Frankfurt DC, and a read-only auditor should not be able to modify artifacts they can view.

So far there is only one operator (superuser), so no access control beyond Django's built-in superuser flag has been needed. Before adding additional operators this must be designed correctly.

The threat being defended against is **inadvertent exposure**: an operator who never configures RBAC should not accidentally expose sensitive artifacts to an unprivileged user. The model must be secure by default with access explicitly granted, not explicitly revoked.

Fleet clients (token + IP authentication) are entirely unaffected — this is a human-operator, admin-UI-only concern.

## Decision

### Security posture: allowlist, not blocklist

An entity with no groups assigned is **invisible to all non-superuser staff**. Access is added, never removed. Superusers always see everything regardless of group membership.

### Data model: two M2M fields per entity

Each entity that requires scoping carries two `ManyToManyField(Group, blank=True)` fields:

- `view_groups` — membership of any listed group grants read-only access
- `edit_groups` — membership of any listed group grants read/write access; edit implies view

Using two separate fields rather than a through model with a `can_change` boolean was chosen for simplicity: the query pattern is straightforward (`view_groups__in=user.groups.all()`), and the admin form rendering is clean. A through model would add ceremony without meaningful benefit at the scale of Django admin group management.

Group membership uses **OR semantics**: a user who belongs to any one of an entity's assigned groups can see it. There is no AND requirement. This reflects the intent — groups are organisational lenses, not capability sets.

### Affected models

Structural changes (new fields + migrations) are required in:

- `ophix-server-base` — `Host`, `Client`
- Every domain package — artifact model (`Credential`, `Configuration`, `CertBundle`, `RecordSlot`, etc.)

This cannot be delivered as a plugin. The fields land on core models in existing packages and require migrations in each.

### Admin enforcement: GroupScopedAdminMixin

A mixin in `ophix.core.admin` overrides four `ModelAdmin` methods:

- `get_queryset(request)` — filters to entities where `view_groups` or `edit_groups` intersects the user's groups; superusers receive the unfiltered queryset
- `has_view_permission(request, obj)` — False if the user has no group overlap with either field on the object
- `has_change_permission(request, obj)` — False unless the user has overlap with `edit_groups`
- `has_delete_permission(request, obj)` — same condition as change; delete is an edit-tier operation

The mixin is applied to `HostAdmin` and `ClientAdmin` in server-base, and to each domain's artifact `ModelAdmin`.

### Widget override

The default `FilteredSelectMultiple` widget (double-panel drag-and-drop) is replaced with `CheckboxSelectMultiple` for `view_groups` and `edit_groups` on all affected admin forms. Groups number in the tens at most; a flat checkbox list is faster to read and operate than a select widget.

### List filter

`view_groups` and `edit_groups` are added to `list_filter` on all affected `ModelAdmin` classes. This gives the operator the group-centric view ("show me everything in group london-dc") without a custom page.

### Bulk assignment via list actions

Each affected `ModelAdmin` exposes two list actions:

- **Add to group** — select N entities, pick a group, assign to `view_groups` or `edit_groups`
- **Remove from group** — select N entities, pick a group, remove from either field

These are the primary tool for bulk onboarding (e.g. assigning a new DC's 40 hosts to a group in one step). Without them, group assignment is per-entity and does not scale.

### Group admin

Django's built-in `GroupAdmin` is replaced with a custom implementation that shows a summary of assigned Ophix entities per group — how many hosts, clients, and artifacts of each type are in each group. Domain plugins contribute their counts via a registration point on the custom `GroupAdmin`, following the same `register_column` / `register_inline` pattern already used by `HostAdmin` and `ClientAdmin`. Server-base knows nothing about artifact models directly.

### User → group assignment

Django's built-in `UserAdmin` handles user-to-group assignment. The `groups` M2M widget is overridden to `CheckboxSelectMultiple` for consistency. No custom model or logic is required here.

## Consequences

- Non-superuser staff see only entities explicitly assigned to their groups — secure by default
- Adding a new operator: create Django user, assign to relevant groups — no Ophix-specific setup required
- Adding a new entity to a group: open the entity, tick the checkbox — or use the bulk list action for many at once
- Migrations required in server-base and every domain package; this is a coordinated release
- `import_legacy_credserver` management command assigns no groups to imported credentials — they will be invisible to non-superusers until explicitly grouped; document this in the migration guide
- The fleet API (token + IP) is completely unaffected — no changes to `ClientTokenAuthentication`, views, or serializers in any domain
- **Existing deployments: superuser experience is unchanged.** All existing entities land with empty `view_groups` and `edit_groups` after migration. The superuser bypass in `get_queryset` means the superuser sees exactly what they saw before — the only visible difference is two new (empty) checkbox fields on each entity's change form and two new (empty) sidebar filters on each list view. The RBAC machinery is entirely dormant until an operator creates a Django Group, assigns it to an entity, and assigns it to a user. Until that first deliberate act the server behaves identically to a pre-RBAC deployment.
- Superuser operators who never configure groups experience no change in behaviour beyond the additional form fields
