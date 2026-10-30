import threading

_state = threading.local()


def get_current_user():
    """Return the user attached to the in-flight request, if any."""
    return getattr(_state, "user", None)


class CurrentUserMiddleware:
    """Stash ``request.user`` on a thread-local so audit/``created_by`` fields
    can self-populate without threading the request through every service call.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _state.user = getattr(request, "user", None)
        try:
            return self.get_response(request)
        finally:
            _state.user = None
