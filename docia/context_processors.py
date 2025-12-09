from django.conf import settings as dj_settings


def settings(request):
    return {
        "settings": {
            "TCHAP_SUPPORT_CANAL_URL": dj_settings.TCHAP_SUPPORT_CANAL_URL,
            "MATOMO_URL": dj_settings.MATOMO_URL,
        }
    }
