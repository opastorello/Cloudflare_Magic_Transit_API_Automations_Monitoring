#!/usr/bin/env python3
"""
MCP Server for Cloudflare Magic Transit Integration.

Provides tools for dashboard APIs and local SQLite operational insights.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "db" / "magic_transit.db"
DEFAULT_DASHBOARD_URL = "http://localhost:8081"

mcp = FastMCP("cloudflare-magic-transit")
_DASHBOARD_SESSION = requests.Session()
_DASHBOARD_LOGGED_IN = False
_DASHBOARD_USERNAME: Optional[str] = None
_DASHBOARD_PASSWORD: Optional[str] = None


def _get_db_path() -> Path:
    env_path = os.getenv("MAGIC_TRANSIT_DB_PATH")
    return Path(env_path).expanduser() if env_path else DEFAULT_DB_PATH


def _query_db(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    db_path = _get_db_path()
    if not db_path.exists():
        return [{"error": f"database not found: {db_path}"}]

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def _get_dashboard_url() -> str:
    return os.getenv("DASHBOARD_BASE_URL", DEFAULT_DASHBOARD_URL).rstrip("/")


def _set_dashboard_credentials(username: Optional[str], password: Optional[str]) -> None:
    global _DASHBOARD_USERNAME, _DASHBOARD_PASSWORD
    if username:
        _DASHBOARD_USERNAME = username
    if password:
        _DASHBOARD_PASSWORD = password


def _dashboard_login() -> Dict[str, Any]:
    global _DASHBOARD_LOGGED_IN
    username = _DASHBOARD_USERNAME or os.getenv("DASHBOARD_USERNAME")
    password = _DASHBOARD_PASSWORD or os.getenv("DASHBOARD_PASSWORD")
    if not username or not password:
        return {"success": False, "error": "Missing dashboard credentials"}

    response = _DASHBOARD_SESSION.post(
        f"{_get_dashboard_url()}/login",
        json={"username": username, "password": password},
        timeout=15,
    )
    data = _parse_response(response)
    if isinstance(data, dict) and data.get("success"):
        _DASHBOARD_LOGGED_IN = True
    return data


def _parse_response(response: requests.Response) -> Any:
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        return response.json()
    return {
        "status_code": response.status_code,
        "text": response.text,
    }


def _dashboard_request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    allow_unauth: bool = False,
) -> Any:
    global _DASHBOARD_LOGGED_IN
    if not allow_unauth and not _DASHBOARD_LOGGED_IN:
        _dashboard_login()

    url = f"{_get_dashboard_url()}{path}"
    response = _DASHBOARD_SESSION.request(
        method=method.upper(),
        url=url,
        params=params,
        json=payload,
        timeout=30,
    )
    return _parse_response(response)


@mcp.tool()
def health() -> Dict[str, Any]:
    """Report MCP server health and database availability."""
    db_path = _get_db_path()
    return {
        "status": "ok",
        "database_path": str(db_path),
        "database_exists": db_path.exists(),
    }


@mcp.tool()
def dashboard_login(username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
    """Login to the dashboard to enable authenticated API calls."""
    _set_dashboard_credentials(username, password)
    return _dashboard_login()


@mcp.tool()
def recent_attacks(limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch recent attack events from the database."""
    return _query_db(
        """
        SELECT id, event_type, alert_type, attack_id, prefix, target_ip,
               attack_vector, packets_per_second, megabits_per_second, created_at
        FROM attack_events
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )


@mcp.tool()
def recent_withdrawals(limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch recent withdrawal history from the database."""
    return _query_db(
        """
        SELECT id, prefix, attack_id, withdrawn_at, protection_duration_seconds,
               withdraw_method, status, notes
        FROM withdrawal_history
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )


@mcp.tool()
def prefix_calm_status() -> List[Dict[str, Any]]:
    """Fetch current calm status for prefixes."""
    return _query_db(
        """
        SELECT prefix, calm_minutes, dropped_bits, updated_at
        FROM prefix_calm_status
        ORDER BY prefix ASC
        """
    )


@mcp.tool()
def api_change_password(
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> Any:
    """Change dashboard password."""
    return _dashboard_request(
        "POST",
        "/api/change-password",
        payload={
            "current_password": current_password,
            "new_password": new_password,
            "confirm_password": confirm_password,
        },
    )


@mcp.tool()
def api_prefixes() -> Any:
    """Fetch prefix status from the dashboard."""
    return _dashboard_request("GET", "/api/prefixes")


@mcp.tool()
def api_attacks() -> Any:
    """Fetch recent attacks from the dashboard."""
    return _dashboard_request("GET", "/api/attacks")


@mcp.tool()
def api_attack_detail(attack_id: int) -> Any:
    """Fetch a single attack detail by ID."""
    return _dashboard_request("GET", f"/api/attacks/{attack_id}")


@mcp.tool()
def api_analytics(params: Optional[Dict[str, Any]] = None) -> Any:
    """Fetch network analytics events from the dashboard."""
    return _dashboard_request("GET", "/api/analytics", params=params)


@mcp.tool()
def api_analytics_detail(analytics_id: int) -> Any:
    """Fetch a single analytics event by ID."""
    return _dashboard_request("GET", f"/api/analytics/{analytics_id}")


@mcp.tool()
def api_analytics_event_detail(event_id: str) -> Any:
    """Fetch analytics event detail for composite ID values."""
    return _dashboard_request("GET", f"/api/analytics/detail/{event_id}")


@mcp.tool()
def api_rules() -> Any:
    """Fetch MNM rules."""
    return _dashboard_request("GET", "/api/rules")


@mcp.tool()
def api_mnm_rules() -> Any:
    """Fetch MNM rules list."""
    return _dashboard_request("GET", "/api/mnm-rules")


@mcp.tool()
def api_mnm_rule_create(payload: Dict[str, Any]) -> Any:
    """Create an MNM rule."""
    return _dashboard_request("POST", "/api/mnm-rules", payload=payload)


@mcp.tool()
def api_mnm_rule_delete(rule_id: str) -> Any:
    """Delete an MNM rule by ID."""
    return _dashboard_request("DELETE", f"/api/mnm-rules/{rule_id}")


@mcp.tool()
def api_mnm_rule_update(rule_id: str, payload: Dict[str, Any]) -> Any:
    """Update an MNM rule by ID."""
    return _dashboard_request("PUT", f"/api/mnm-rules/{rule_id}", payload=payload)


@mcp.tool()
def api_ddos_sensitivity() -> Any:
    """Fetch DDoS ruleset sensitivity summary."""
    return _dashboard_request("GET", "/api/ddos-sensitivity")


@mcp.tool()
def api_ddos_rules(action: Optional[str] = None) -> Any:
    """Fetch DDoS rules, optionally filtered by action."""
    path = f"/api/ddos-rules/{action}" if action else "/api/ddos-rules"
    return _dashboard_request("GET", path)


@mcp.tool()
def api_ddos_rule_update(rule_id: str, payload: Dict[str, Any]) -> Any:
    """Update a DDoS rule action."""
    return _dashboard_request("POST", f"/api/ddos-rules/{rule_id}/update", payload=payload)


@mcp.tool()
def api_ddos_overrides() -> Any:
    """Fetch DDoS overrides."""
    return _dashboard_request("GET", "/api/ddos-overrides")


@mcp.tool()
def api_ddos_override_create(payload: Dict[str, Any]) -> Any:
    """Create a DDoS override."""
    return _dashboard_request("POST", "/api/ddos-overrides", payload=payload)


@mcp.tool()
def api_ddos_override_update(override_id: str, payload: Dict[str, Any]) -> Any:
    """Update a DDoS override."""
    return _dashboard_request("PUT", f"/api/ddos-overrides/{override_id}", payload=payload)


@mcp.tool()
def api_ddos_override_delete(override_id: str) -> Any:
    """Delete a DDoS override."""
    return _dashboard_request("DELETE", f"/api/ddos-overrides/{override_id}")


@mcp.tool()
def api_ddos_override_validate(payload: Dict[str, Any]) -> Any:
    """Validate a DDoS override expression."""
    return _dashboard_request("POST", "/api/ddos-overrides/validate", payload=payload)


@mcp.tool()
def api_ddos_override_move(override_id: str, payload: Dict[str, Any]) -> Any:
    """Move a DDoS override."""
    return _dashboard_request("POST", f"/api/ddos-overrides/{override_id}/move", payload=payload)


@mcp.tool()
def api_services() -> Any:
    """Fetch services status."""
    return _dashboard_request("GET", "/api/services")


@mcp.tool()
def api_stats() -> Any:
    """Fetch stats summary."""
    return _dashboard_request("GET", "/api/stats")


@mcp.tool()
def api_dashboard_prefs_get() -> Any:
    """Fetch dashboard preferences."""
    return _dashboard_request("GET", "/api/dashboard-prefs")


@mcp.tool()
def api_dashboard_prefs_set(payload: Dict[str, Any]) -> Any:
    """Update dashboard preferences."""
    return _dashboard_request("POST", "/api/dashboard-prefs", payload=payload)


@mcp.tool()
def api_analytics_summary() -> Any:
    """Fetch analytics summary."""
    return _dashboard_request("GET", "/api/analytics-summary")


@mcp.tool()
def api_network_flow() -> Any:
    """Fetch network flow stats."""
    return _dashboard_request("GET", "/api/network-flow")


@mcp.tool()
def api_prefix_advertise(cidr: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    """Advertise a prefix."""
    return _dashboard_request("POST", f"/api/prefix/{cidr}/advertise", payload=payload)


@mcp.tool()
def api_prefix_withdraw(cidr: str, payload: Optional[Dict[str, Any]] = None) -> Any:
    """Withdraw a prefix."""
    return _dashboard_request("POST", f"/api/prefix/{cidr}/withdraw", payload=payload)


@mcp.tool()
def api_connectors_tunnels() -> Any:
    """Fetch connector tunnels."""
    return _dashboard_request("GET", "/api/connectors/tunnels")


@mcp.tool()
def api_connectors_interconnects() -> Any:
    """Fetch connector interconnects."""
    return _dashboard_request("GET", "/api/connectors/interconnects")


@mcp.tool()
def api_connectors_tunnel(tunnel_id: str) -> Any:
    """Fetch a tunnel by ID."""
    return _dashboard_request("GET", f"/api/connectors/tunnel/{tunnel_id}")


@mcp.tool()
def api_connectors_tunnel_update(tunnel_id: str, payload: Dict[str, Any]) -> Any:
    """Update a tunnel by ID."""
    return _dashboard_request("POST", f"/api/connectors/tunnel/{tunnel_id}/update", payload=payload)


@mcp.tool()
def api_connectors_cni(cni_id: str) -> Any:
    """Fetch a CNI interconnect by ID."""
    return _dashboard_request("GET", f"/api/connectors/cni/{cni_id}")


@mcp.tool()
def api_connectors_cni_update(cni_id: str, payload: Dict[str, Any]) -> Any:
    """Update a CNI interconnect by ID."""
    return _dashboard_request("POST", f"/api/connectors/cni/{cni_id}/update", payload=payload)


@mcp.tool()
def api_connectors_tunnel_health() -> Any:
    """Fetch tunnel health."""
    return _dashboard_request("GET", "/api/connectors/tunnel-health")


@mcp.tool()
def api_connectors_health_summary() -> Any:
    """Fetch connectors health summary."""
    return _dashboard_request("GET", "/api/connectors/health-summary")


if __name__ == "__main__":
    mcp.run()
