"""
LM Studio auto-discovery — finds the first host on the local network
that is serving an OpenAI-compatible API on port 1234.

Priority order:
  1. VLM_BASE_URL env var (explicit override, always wins)
  2. localhost:1234
  3. All local NIC IPs on port 1234
  4. Subnet scan of every /24 reachable from local NICs

Usage:
    from mvp.discovery import find_lm_studio
    base_url = find_lm_studio()          # returns e.g. "http://192.168.1.42:1234/v1"
    base_url = find_lm_studio(port=1234) # custom port
"""

from __future__ import annotations

import os
import socket
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

_DEFAULT_PORT = 1234
_CONNECT_TIMEOUT = 0.4   # seconds per TCP probe
_HTTP_TIMEOUT = 2.0      # seconds for the /v1/models HTTP check
_MAX_WORKERS = 64


def _tcp_open(host: str, port: int) -> bool:
    """Return True if TCP port is reachable."""
    try:
        with socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT):
            return True
    except OSError:
        return False


def _is_lm_studio(host: str, port: int) -> bool:
    """Return True if the host responds to GET /v1/models like LM Studio."""
    url = f"http://{host}:{port}/v1/models"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            return resp.status == 200
    except Exception:
        return False


def _local_ips() -> list[str]:
    """Return all IPv4 addresses assigned to local NICs (excluding loopback)."""
    ips: list[str] = []
    try:
        # Works on all platforms without extra deps
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    # Also try the connect-trick to find the default outbound IP
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return list(dict.fromkeys(ips))  # deduplicate, preserve order


def _subnet_hosts(local_ip: str) -> list[str]:
    """Return all .1–.254 hosts in the /24 subnet of local_ip."""
    prefix = ".".join(local_ip.split(".")[:3])
    return [f"{prefix}.{i}" for i in range(1, 255)]


def _probe(host: str, port: int) -> Optional[str]:
    """Return base_url if host:port is a live LM Studio instance, else None."""
    if _is_lm_studio(host, port):
        return f"http://{host}:{port}/v1"
    return None


def find_lm_studio(port: int = _DEFAULT_PORT, verbose: bool = True) -> Optional[str]:
    """
    Scan the local network for a running LM Studio instance.

    Returns the first base_url found (e.g. "http://192.168.1.42:1234/v1"),
    or None if nothing is found.

    Respects the VLM_BASE_URL environment variable as an explicit override.
    """
    # 0. Env var override
    env_url = os.getenv("VLM_BASE_URL")
    if env_url:
        if verbose:
            print(f"[DISCOVERY] VLM_BASE_URL set by env → {env_url}")
        return env_url

    candidates: list[str] = []

    # 1. localhost first (fastest)
    candidates.append("127.0.0.1")

    # 2. All local NIC IPs
    local_ips = _local_ips()
    for ip in local_ips:
        if ip not in candidates:
            candidates.append(ip)

    # 3. Subnet peers
    seen: set[str] = set(candidates)
    for lip in local_ips:
        for host in _subnet_hosts(lip):
            if host not in seen:
                candidates.append(host)
                seen.add(host)

    if verbose:
        print(f"[DISCOVERY] Scanning {len(candidates)} hosts on port {port}...")

    # First pass: quick TCP probe in parallel → shortlist
    tcp_open: list[str] = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        futs = {ex.submit(_tcp_open, h, port): h for h in candidates}
        for fut in as_completed(futs):
            if fut.result():
                tcp_open.append(futs[fut])

    if not tcp_open:
        if verbose:
            print(f"[DISCOVERY] No host found with port {port} open.")
        return None

    if verbose:
        print(f"[DISCOVERY] Port {port} open on: {tcp_open}")

    # Second pass: HTTP /v1/models check on shortlist
    # Prioritise localhost and local NIC IPs so they win ties
    priority = {"127.0.0.1"} | set(local_ips)
    ordered = sorted(tcp_open, key=lambda h: (0 if h in priority else 1))

    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(ordered))) as ex:
        futs = {ex.submit(_probe, h, port): h for h in ordered}
        results: list[tuple[int, str]] = []
        for fut in as_completed(futs):
            url = fut.result()
            if url:
                host = futs[fut]
                rank = ordered.index(host)
                results.append((rank, url))

    if not results:
        if verbose:
            print("[DISCOVERY] No LM Studio instance responded to /v1/models.")
        return None

    best = min(results, key=lambda t: t[0])[1]
    if verbose:
        print(f"[DISCOVERY] Found LM Studio → {best}")
    return best


def find_lm_studio_or_default(
    port: int = _DEFAULT_PORT,
    fallback: str = "http://localhost:1234/v1",
    verbose: bool = True,
) -> str:
    """
    Like find_lm_studio() but always returns a string.
    Falls back to `fallback` if discovery fails.
    """
    result = find_lm_studio(port=port, verbose=verbose)
    if result is None:
        if verbose:
            print(f"[DISCOVERY] Discovery failed, using fallback: {fallback}")
        return fallback
    return result
