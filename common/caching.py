from django.core.cache import cache
from rest_framework.response import Response


def cache_response_decorator(cache_prefix: str, cache_timeout: int = 60 * 10, per_user:bool=False):
    """
    Decorator to cache the response of a view function.
    
    This decorator caches API responses to improve performance by avoiding repeated database queries.
    The cache key is constructed using the provided prefix, HTTP method, and full request path.
    For user-specific caching, the user id of the currently logged in user can be included in the cache key.

    Args:
        cache_prefix (str): The prefix to use for the cache key
        cache_timeout (int): The timeout for the cache in seconds (default is 10 minutes) 
        per_user (bool): Whether to include the user ID in the cache key (default is False)

    Returns:
        The cached response if available, otherwise executes the view function and caches the response

    Example:
        @cache_response_decorator('my_view', cache_timeout=300, per_user=True)
        def get(self, request):
            # View logic here
            return Response(data)
    """
    def decorator(view_func):
        def wrapper(self, request, *args, **kwargs):
            # if per_user is True, the cache key will contain the user id, this is intended for invalidating cache for a specific user
            cache_key = f"{cache_prefix}_{request.user.id}_{request.method}_{request.get_full_path()}" if per_user else f"{cache_prefix}_{request.method}_{request.get_full_path()}"

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

