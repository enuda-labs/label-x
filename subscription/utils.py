from urllib.parse import urlparse

def get_request_origin(request):
    origin = request.META.get("HTTP_ORIGIN", None)
    print('the origin is', origin)
    referrer = request.META.get('HTTP_REFERER', origin)
    
    if referrer:
        parsed_url = urlparse(referrer)
        origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
        return origin
    return "http://label-x-website.onrender.com"