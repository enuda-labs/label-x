from django.core.cache import cache
from rest_framework.response import Response


def cache_user_response_decorator(cache_prefix: str, cache_timeout: int = 60 * 15):
    """
    Decorator to cache the response of a view function for a user
    Args:
        cache_prefix: The prefix to use for the cache key
        cache_timeout: The timeout for the cache in seconds (default is 15 minutes)
    Returns:
        The response from the view function
    """

    def decorator(view_func):
        def wrapper(self, request, *args, **kwargs):
            cache_key = f"{cache_prefix}_{request.user.id}_{request.method}_{request.get_full_path()}"

            cached_response = cache.get(cache_key) if cache_key else None
            if cached_response:
                return Response(
                    cached_response.get("data", {}),
                    status=cached_response.get("status", 200),
                    headers=cached_response.get("headers", {}),
                )
            response = view_func(self, request, *args, **kwargs)

            if request.method == "GET" and response.status_code == 200:
                cache_data = {
                    "data": response.data,
                    "status": response.status_code,
                    "headers": dict(response.items()),
                }
                cache.set(cache_key, cache_data, cache_timeout)
            return response

        return wrapper

    return decorator
