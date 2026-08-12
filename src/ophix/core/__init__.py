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
            "export_command": "export_hosts",
            "encrypted": False,
            "stable": True,
        },
        {
            "name": "clients",
            "app_label": "ophix_core",
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
            "stable": False,  # Phase B — Fernet's random IV/salt make this impossible today
        },
    ]
