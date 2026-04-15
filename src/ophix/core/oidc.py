"""
ophix.core.oidc
~~~~~~~~~~~~~~~
Custom OIDC authentication backend for Ophix admin.

Extends mozilla-django-oidc's OIDCAuthenticationBackend to:
  - Merge group claims from the ID token (Azure AD sends groups in the ID token,
    not the userinfo endpoint, when the user is a member of many groups)
  - Auto-provision new users on first login
  - Map OIDC group IDs to Django staff / superuser status

This module is only imported when OIDC_ENABLED is True (i.e. when
mozilla-django-oidc is installed and OIDC_RP_CLIENT_ID is set).
"""

import logging

from django.conf import settings
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

logger = logging.getLogger(__name__)


class OphixOIDCBackend(OIDCAuthenticationBackend):
    """
    OIDC backend that handles Azure AD group claims and auto-provisioning.
    """

    # ------------------------------------------------------------------
    # Claim extraction
    # ------------------------------------------------------------------

    def get_userinfo(self, access_token, id_token, payload):
        """
        Merge claims from the ID token into the userinfo response.

        Azure AD (and some other providers) include group memberships in the
        ID token rather than the userinfo endpoint when the user belongs to
        many groups.  We merge them here so the rest of the pipeline sees a
        single unified claims dict.
        """
        userinfo = super().get_userinfo(access_token, id_token, payload)
        # payload is the decoded ID token
        if payload and isinstance(payload, dict):
            for key in ("groups", "roles"):
                if key in payload and key not in userinfo:
                    userinfo[key] = payload[key]
        return userinfo

    # ------------------------------------------------------------------
    # User creation / update
    # ------------------------------------------------------------------

    def create_user(self, claims):
        """Create a new Django user from OIDC claims."""
        user = super().create_user(claims)
        self._apply_group_permissions(user, claims)
        return user

    def update_user(self, user, claims):
        """Update an existing user's permissions from OIDC claims."""
        user = super().update_user(user, claims)
        self._apply_group_permissions(user, claims)
        return user

    def filter_users_by_claims(self, claims):
        """
        Find existing users by email.  Auto-provisioning is always on —
        if no user is found, create_user() will be called.
        """
        email = claims.get("email") or claims.get("preferred_username", "")
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email__iexact=email)

    def get_username(self, claims):
        """Derive a username from email or preferred_username."""
        email = claims.get("email") or claims.get("preferred_username", "")
        # Django username max length is 150; trim if needed
        return email[:150] if email else super().get_username(claims)

    # ------------------------------------------------------------------
    # Group → permission mapping
    # ------------------------------------------------------------------

    def _apply_group_permissions(self, user, claims):
        """
        Inspect the groups claim and set is_staff / is_superuser flags.

        Settings consumed:
          OIDC_STAFF_GROUP_ID      — object ID (string) of the staff group
          OIDC_SUPERUSER_GROUP_ID  — object ID (string) of the superuser group

        If neither setting is configured, all SSO users are granted staff
        access (so they can log into the admin).  This is intentionally
        permissive — tighten by setting OIDC_STAFF_GROUP_ID.
        """
        groups = claims.get("groups") or []
        if isinstance(groups, str):
            groups = [groups]

        staff_group = getattr(settings, "OIDC_STAFF_GROUP_ID", "")
        superuser_group = getattr(settings, "OIDC_SUPERUSER_GROUP_ID", "")

        if superuser_group and superuser_group in groups:
            user.is_staff = True
            user.is_superuser = True
        elif staff_group and staff_group in groups:
            user.is_staff = True
            user.is_superuser = False
        elif not staff_group and not superuser_group:
            # No groups configured — grant staff to all SSO users
            user.is_staff = True
        else:
            # Groups are configured but this user is in none of them
            user.is_staff = False
            user.is_superuser = False

        user.save(update_fields=["is_staff", "is_superuser"])
