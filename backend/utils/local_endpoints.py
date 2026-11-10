"""Fail closed before model requests can leave this machine."""
from ipaddress import ip_address
from urllib.parse import urlsplit


def require_loopback(url: str, label: str = 'Model endpoint') -> str:
    parsed = urlsplit(url)
    host = parsed.hostname or ''
    try:
        loopback = ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() == 'localhost'
    if (parsed.scheme not in {'http', 'https'} or not loopback or
            parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError(f'{label} must use a loopback HTTP address in local-only mode.')
    return url


def validate_model_endpoints(settings):
    if not settings.local_only:
        return
    if settings.lmstudio_base_url:
        require_loopback(settings.lmstudio_base_url, 'LM Studio')
    else:
        if settings.groq_api_key:
            raise ValueError('Cloud model credentials are disabled in local-only mode.')
        if settings.ollama_base_url:
            require_loopback(settings.ollama_base_url, 'Ollama')
