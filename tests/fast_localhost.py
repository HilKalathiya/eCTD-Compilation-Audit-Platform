"""Test helper: makes the name "localhost" resolve to IPv4 only, because on this Windows machine the IPv6 try (::1) costs about 2 s per new connection to Ollama."""
import socket

_real_getaddrinfo = socket.getaddrinfo


def _ipv4_first_for_localhost(host, *args, **kwargs):
    """Same answer as the real lookup, but for "localhost" the IPv6 addresses are left out (when an IPv4 one exists)."""
    found = _real_getaddrinfo(host, *args, **kwargs)
    if host == "localhost":
        v4 = [f for f in found if f[0] == socket.AF_INET]
        return v4 or found
    return found


def install():
    """Idempotent; only the address list for "localhost" changes. Nothing is mocked, the real connection is still made."""
    if socket.getaddrinfo is not _ipv4_first_for_localhost:
        socket.getaddrinfo = _ipv4_first_for_localhost


install()
