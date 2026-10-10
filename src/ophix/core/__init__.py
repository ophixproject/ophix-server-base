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
