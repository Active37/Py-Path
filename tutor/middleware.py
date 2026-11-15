import json
import logging
from time import perf_counter

from django.urls import Resolver404, resolve


logger = logging.getLogger("tutor.access")


class RequestAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        try:
            response = self.get_response(request)
        except Exception:
            self._log_request(request, 500, started)
            raise

        self._log_request(request, response.status_code, started)
        return response

    @staticmethod
    def _log_request(request, status_code, started):
        user = getattr(request, "user", None)
        actor = None
        if user is not None and user.is_authenticated:
            actor = {
                "id": user.pk,
                "username": user.get_username(),
                "email": user.email,
            }

        route_match = getattr(request, "resolver_match", None)
        if route_match is None:
            try:
                route_match = resolve(request.path_info)
            except Resolver404:
                route_match = None
        route = getattr(route_match, "route", None)
        event = {
            "event": "http_request",
            "method": request.method,
            "route": (route or "<unresolved>")[:200],
            "status": status_code,
            "duration_ms": round((perf_counter() - started) * 1000, 2),
            "user": actor,
        }
        logger.info(json.dumps(event, separators=(",", ":"), ensure_ascii=True))
