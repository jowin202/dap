from fastapi import Request

_STANDARD_PORTS = {"http": 80, "https": 443}


def base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host  = request.headers.get("x-forwarded-host", request.headers.get("host", ""))

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
