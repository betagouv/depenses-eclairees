import logging
import socket

logger = logging.getLogger(__name__)


def init_custom_dns_resolver(dns_mapping: dict = None):
    from django.conf import settings

    # Override default socket.getaddrinfo() and pass ip instead of host
    # if override is detected
    def custom_getaddrinfo(host, *args, **kwargs):
        dns_cache = settings.FILE_SYNC_DNS
        if host in dns_cache:
            ip = dns_cache[host]
            logger.debug("Forcing FQDN: {%s} to IP: {%s}", host, ip)
            return og_getaddrinfo(ip, *args, **kwargs)
        else:
            return og_getaddrinfo(host, *args, **kwargs)

    if socket.getaddrinfo.__module__ == "socket":
        logger.warning("Patching socket.getaddrinfo")
        og_getaddrinfo = socket.getaddrinfo
        # Only patch if the original function is still in place
        socket.getaddrinfo = custom_getaddrinfo
