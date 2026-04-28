from fastapi import HTTPException, Security, Depends, Response, Cookie, Query, Request
from fastapi.security import APIKeyHeader
from config import config

api_key_header = APIKeyHeader(name='X-API-Key', auto_error=False)

async def get_api_key(
    request: Request,
    response: Response,
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Query(None, alias='api_key'),
    api_key_cookie: str = Cookie(None, alias='api_key')
):
    if not config.api_key:
        return None # Dev mode or not configured
    
    # Always set Referrer-Policy to ensure sub-resources can send the full URL in the referer.
    # This is critical for iframes where the API key is in the query string.
    response.headers['Referrer-Policy'] = 'no-referrer-when-downgrade'

    # Primary check: direct credentials
    key = api_key_header or api_key_query or api_key_cookie
    
    # Fallback check: Referer header
    if not key:
        referer = request.headers.get('referer')
        if referer:
            # Case 1: API key is explicitly in the referer query string
            if f'api_key={config.api_key}' in referer:
                key = config.api_key
            # Case 2: Referer is from our own backend origin (e.g. sub-resources of a validly loaded page)
            elif referer.startswith(str(request.base_url)):
                 key = config.api_key

    if key == config.api_key:
        if not api_key_cookie:
            is_https = request.url.scheme == 'https'
            response.set_cookie(
                key='api_key',
                value=key,
                httponly=True,
                samesite='none' if is_https else 'lax',
                secure=is_https,
                path='/'
            )
        return key
        
    raise HTTPException(
        status_code=403,
        detail='Could not validate credentials',
    )
