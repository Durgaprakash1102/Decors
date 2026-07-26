from django.conf import settings


def normalize_domain(domain: str) -> str:
    """
    Normalize a domain for comparison.

    Examples:
        localhost:8000      -> localhost
        127.0.0.1:8000      -> localhost (DEBUG only)
        www.abc.com         -> abc.com
        ABC.COM             -> abc.com
        abc.com.            -> abc.com
    """

    if not domain:
        return ""

    # Remove port
    domain = domain.split(":")[0]

    # Lowercase
    domain = domain.lower().strip()

    # Remove trailing dot
    domain = domain.rstrip(".")

    # Development aliases
    if settings.DEBUG and domain in ("localhost", "127.0.0.1"):
        return "localhost"

    # Treat www as the same domain
    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def get_current_domain(request):
    """
    Returns the normalized current domain.
    """

    return normalize_domain(request.get_host())