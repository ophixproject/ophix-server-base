from django.conf import settings
from django.http import JsonResponse


_SAFE_METHODS = frozenset(["GET", "HEAD", "OPTIONS"])


class ReadOnlyModeMiddleware:
    """
    Reject all API write requests when SERVER_READ_ONLY_MODE is True.

    Only paths under /api/ are affected. The admin interface, static files,
    and internal access logging are unaffected. Returns 503 so that Ophix
    clients treat the response as a transient failure and retry later.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            getattr(settings, "SERVER_READ_ONLY_MODE", False)
            and request.method not in _SAFE_METHODS
            and request.path.startswith("/api/")
        ):
            return JsonResponse(
                {"error": "Server is in read-only mode — no changes are permitted."},
                status=503,
            )
        return self.get_response(request)
