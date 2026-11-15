from fastapi import Request

_STANDARD_PORTS = {"http": 80, "https": 443}
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def _host(request: Request) -> str:
    return request.headers.get("x-forwarded-host", request.headers.get("host", ""))


def base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host  = _host(request)

    # Host-Header kann "hostname:port" enthalten – Port entfernen wenn Standard
    if ":" in host:
        hostname, _, port_str = host.rpartition(":")
        try:
            if int(port_str) != _STANDARD_PORTS.get(proto):
                host = f"{hostname}:{port_str}"
            else:
                host = hostname
        except ValueError:
            pass  # kein gültiger Port, unverändert lassen

    return f"{proto}://{host}"


def curl_flags(request: Request) -> str:
    """Bei localhost wird die Zertifikatsprüfung abgeschaltet (selbstsigniertes Zertifikat)."""
    return "-sfkL" if _host(request).split(":")[0] in _LOCAL_HOSTS else "-sfL"


def download_commands(request: Request, token: str) -> dict[str, str]:
    """Fertige Einzeiler für PowerShell und Shell. Bei localhost werden Zertifikatsprüfungen
    abgeschaltet, weil dort typischerweise ein selbstsigniertes Zertifikat verwendet wird."""
    base     = base_url(request)
    is_local = _host(request).split(":")[0] in _LOCAL_HOSTS
    irm_flags  = " -SkipCertificateCheck" if is_local else ""
    return {
        "ps_cmd": f'pwsh -Command "irm{irm_flags} {base}/api/psdec/{token}/ | iex"',
        "sh_cmd": f"curl {curl_flags(request)} {base}/api/shdec/{token}/ | sh",
    }
