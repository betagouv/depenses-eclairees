from django.conf import settings

from lasuite.oidc_login.backends import (
    OIDCAuthenticationBackend as LaSuiteOIDCAuthenticationBackend,
)


class CustomOIDCBackend(LaSuiteOIDCAuthenticationBackend):
    def get_extra_claims(self, user_info):
        """
        Return extra claims from user_info.

        Args:
          user_info (dict): The user information dictionary.

        Returns:
          dict: A dictionary of extra claims.
        """
        return {
            "full_name": self.compute_full_name(user_info),
            "short_name": user_info.get(settings.OIDC_USERINFO_SHORTNAME_FIELD),
        }

    def update_user_if_needed(self, user, claims):
        """Update user claims if they have changed."""
        updated_claims = {}
        for key in claims:
            if not hasattr(user, key):
                continue

            claim_value = claims.get(key)
            if claim_value and claim_value != getattr(user, key):
                setattr(user, key, claim_value)
                updated_claims[key] = claim_value

        if updated_claims:
            user.save(update_fields=tuple(updated_claims.keys()))
