from django.utils import timezone
from .signals import trigger_cleanup_on_request

class CleanupMiddleware:
    """
    Middleware to trigger cleanup on page visits
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # List of paths where cleanup should run
        self.cleanup_paths = ['/', '/shop/', '/cart/', '/checkout/', '/orders/']

    def __call__(self, request):
        # Only run cleanup on specific paths
        if request.path in self.cleanup_paths:
            trigger_cleanup_on_request(request)
        
        response = self.get_response(request)
        return response