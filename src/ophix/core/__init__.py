def get_revisions_targets():
    """
    Optional hook discovered by ophix-revisions (if installed). ophix-server-base
    is the one package ophix-revisions imports this from directly rather than
    via entry-point discovery, since every install already has an unconditional
    dependency on it.
    """
    return [
        {
            "name": "hosts",
            "app_label": "ophix_core",
            # Precise model match — without this, any other ophix_core
            # model save (e.g. PackageUpdateRecord) would also trigger this
            # target just for sharing the same app_label.
            "models": ["ophix_core.host"],
            "records_key": "hosts",
            "export_command": "export_hosts",
            "encrypted": False,
            "stable": True,
        },
        {
            "name": "clients",
            "app_label": "ophix_core",
            # Precise model match — see "hosts" above.
            "models": ["ophix_core.client"],
            "records_key": "clients",
            "export_command": "export_clients",
            "encrypted": False,
            "stable": True,
        },
        {
            "name": "env",
            # .env is a file write, not an ORM save — app_label=None means
            # this target is never reached via a signal, only via an
            # explicit hooks.commit_now("env", ...) call.
            "app_label": None,
            "export_command": "export_env",
            "encrypted": True,
            "stable": True,
        },
    ]


# Target names that already appear as hardcoded literal text in both
# server-backup.md's BACKUP_TARGETS example and ophix-revisions.md's
# REVISIONS_TARGETS example — they come from ophix-server-base/
# ophix-admin-settings/ophix-admin-interface, all unconditional dependencies
# of every install, so there's nothing for an operator to be guided to.
# Excluded from _discover_domain_target_names()'s output below.
_CORE_TARGET_NAMES = frozenset({"hosts", "clients", "settings", "themes", "env"})


def _discover_domain_target_names():
    """
    Enumerate every installed plugin's own get_revisions_targets() hook (if
    it has one) purely to read each target's declared `name`/`encrypted`
    fields — a plain, side-effect-free function call, not a dependency on
    ophix-revisions actually being installed or doing anything with the
    result. Used only to build an accurate, copy-pasteable BACKUP_TARGETS/
    REVISIONS_TARGETS example in documentation (see get_doc_tokens() below,
    and ophix_revisions's own get_doc_tokens(), which reuses this function
    directly rather than duplicating the entry-point iteration) — never
    hardcodes which domain packages exist, same as every other discovery
    mechanism in the project.

    Returns (plain_names, encrypted_names), both sorted, both excluding
    _CORE_TARGET_NAMES.
    """
    import importlib
    from importlib.metadata import entry_points

    plain, encrypted = set(), set()
    for ep in entry_points(group="ophix.plugins"):
        try:
            mod = importlib.import_module(ep.value)
        except ImportError:
            continue
        hook = getattr(mod, "get_revisions_targets", None)
        if hook is None:
            continue
        try:
            specs = hook() or []
        except Exception:
            continue
        for spec in specs:
            name = spec.get("name")
            if not name or name in _CORE_TARGET_NAMES:
                continue
            (encrypted if spec.get("encrypted") else plain).add(name)
    return sorted(plain), sorted(encrypted)


def _joined_with_leading_comma(names) -> str:
    """"," + comma-joined names, or "" if empty — so an example line like
    `BACKUP_TARGETS=hosts,clients,settings{{ backup_target }}` never leaves
    a dangling trailing comma when no domain plugin is installed."""
    return ("," + ",".join(names)) if names else ""


def get_doc_tokens():
    """
    Optional hook discovered by ophix-docs (if installed). Builds a
    BACKUP_TARGETS/BACKUP_TARGETS_ENCRYPTED example for server-backup.md
    that reflects whatever domain plugin(s) are actually installed on this
    server right now, instead of a hand-typed guess that drifts the moment
    a domain package's own get_revisions_targets() changes.
    """
    plain, encrypted = _discover_domain_target_names()
    return {
        "backup_target": _joined_with_leading_comma(plain),
        "backup_target_encrypted": _joined_with_leading_comma(encrypted),
    }
