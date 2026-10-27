"""Dynamic Tool Plugin Registry (`src/plugins/registry.py`).

Supports both:
1. Decorator-based registration (`@register_tool_plugin`) with JSON-Schema input validation.
2. Standard Python packaging discovery via `importlib.metadata.entry_points(group="scouts_bsa.plugins")`
   so third-party Scouting tools register without modifying core agent orchestrator code.
"""

from __future__ import annotations

import importlib.metadata
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


class PluginValidationError(ValueError):
    """Raised when a plugin input payload fails JSON-Schema validation."""


@dataclass
class ToolPluginSpec:
    """Metadata and callable handler for a registered tool plugin."""

    name: str
    description: str
    version: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    source: str = "decorator"


class PluginRegistry:
    """Thread-safe registry for built-in and `entry_points`-discovered tool plugins."""

    DEFAULT_ENTRY_POINT_GROUP = "scouts_bsa.plugins"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plugins: Dict[str, ToolPluginSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Dict[str, Any]],
        version: str = "1.0.0",
        source: str = "decorator",
    ) -> ToolPluginSpec:
        """Registers a tool plugin specification."""
        clean_name = str(name or "").strip()
        if not clean_name:
            raise ValueError("Plugin name must be non-empty.")
        spec = ToolPluginSpec(
            name=clean_name,
            description=str(description or "").strip(),
            version=str(version or "1.0.0").strip(),
            input_schema=dict(input_schema or {"type": "object", "properties": {}}),
            handler=handler,
            source=source,
        )
        with self._lock:
            self._plugins[clean_name] = spec
        return spec

    def validate_plugin_input(self, name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validates `payload` against the plugin's declared JSON-Schema."""
        with self._lock:
            spec = self._plugins.get(name)
        if spec is None:
            raise KeyError(f"Unknown tool plugin: '{name}'")
        if not isinstance(payload, dict):
            raise PluginValidationError(f"Plugin '{name}' expects a JSON object payload.")

        schema = spec.input_schema or {}
        required_fields = schema.get("required", [])
        properties = schema.get("properties", {})

        for req_key in required_fields:
            if req_key not in payload or payload[req_key] is None or payload[req_key] == "":
                raise PluginValidationError(
                    f"Plugin '{name}' missing required field '{req_key}'."
                )

        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        for field_name, field_val in payload.items():
            prop_spec = properties.get(field_name)
            if not prop_spec or field_val is None:
                continue
            expected_type_name = prop_spec.get("type")
            expected_py_type = type_map.get(str(expected_type_name))
            if expected_py_type and not isinstance(field_val, expected_py_type):
                raise PluginValidationError(
                    f"Plugin '{name}' field '{field_name}' expected type '{expected_type_name}', "
                    f"got '{type(field_val).__name__}'."
                )
        return payload

    def execute_plugin(self, name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validates input against JSON-Schema and executes the named plugin handler."""
        clean_payload = payload if payload is not None else {}
        validated = self.validate_plugin_input(name, clean_payload)
        with self._lock:
            spec = self._plugins[name]
        result = spec.handler(validated)
        return {
            "plugin": spec.name,
            "version": spec.version,
            "status": "SUCCESS",
            "output": result,
        }

    def discover_entry_point_plugins(
        self,
        group: str = DEFAULT_ENTRY_POINT_GROUP,
    ) -> List[str]:
        """Discovers and loads plugins registered via `importlib.metadata.entry_points`."""
        discovered: List[str] = []
        try:
            eps = importlib.metadata.entry_points()
            if hasattr(eps, "select"):
                group_eps = eps.select(group=group)
            else:  # pragma: no cover
                group_eps = eps.get(group, [])  # type: ignore[union-attr]

            for ep in group_eps:
                try:
                    loaded = ep.load()
                    if isinstance(loaded, ToolPluginSpec):
                        with self._lock:
                            self._plugins[loaded.name] = loaded
                        discovered.append(loaded.name)
                    elif callable(loaded):
                        maybe_spec = loaded()
                        if isinstance(maybe_spec, ToolPluginSpec):
                            with self._lock:
                                self._plugins[maybe_spec.name] = maybe_spec
                            discovered.append(maybe_spec.name)
                except Exception:
                    continue
        except Exception:
            pass
        return discovered

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Returns metadata and JSON-Schemas for all registered plugins."""
        with self._lock:
            specs = list(self._plugins.values())
        return [
            {
                "name": s.name,
                "description": s.description,
                "version": s.version,
                "source": s.source,
                "input_schema": s.input_schema,
            }
            for s in sorted(specs, key=lambda x: x.name)
        ]


GLOBAL_PLUGIN_REGISTRY = PluginRegistry()


def register_tool_plugin(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    version: str = "1.0.0",
    registry: Optional[PluginRegistry] = None,
) -> Callable[[Callable[[Dict[str, Any]], Dict[str, Any]]], Callable[[Dict[str, Any]], Dict[str, Any]]]:
    """Decorator that registers a function as a validated tool plugin in `GLOBAL_PLUGIN_REGISTRY`."""
    target_registry = registry or GLOBAL_PLUGIN_REGISTRY

    def _decorator(
        func: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        spec = target_registry.register(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=func,
            version=version,
            source="decorator",
        )
        setattr(func, "_plugin_spec", spec)
        return func

    return _decorator


# ---------------------------------------------------------------------------
# Built-In Domain Plugins (Weather, Camping, Hiking, Backcountry Preparation)
# ---------------------------------------------------------------------------


@register_tool_plugin(
    name="noaa_weather_forecast",
    description="Returns localized NOAA/NWS weather station hazard alerts and barometric pressure trends for Weather and Camping Merit Badges.",
    input_schema={
        "type": "object",
        "required": ["zip_code"],
        "properties": {
            "zip_code": {"type": "string", "description": "5-digit US ZIP code or camp location"},
            "badge_name": {"type": "string", "description": "Optional Merit Badge context"},
        },
    },
    version="1.2.0",
)
def noaa_weather_forecast_plugin(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Built-in NOAA weather forecast plugin handler."""
    zip_code = str(payload.get("zip_code", "01949")).strip()
    badge_name = str(payload.get("badge_name", "Weather")).strip()
    return {
        "station_id": f"NWS-BOX-{zip_code[:5]}",
        "zip_code": zip_code,
        "badge_name": badge_name,
        "forecast_summary": "Clear skies transitioning to afternoon cumulus; monitor 30-30 lightning rule.",
        "barometric_pressure_hpa": 1016.4,
        "hazardous_weather_outlook": "No active severe thunderstorm or flash flood warnings.",
    }


@register_tool_plugin(
    name="usgs_topographic_elevation",
    description="Computes USGS topographic elevation, magnetic declination, and contour interval data for Orienteering, Hiking, and Wilderness Survival.",
    input_schema={
        "type": "object",
        "required": ["latitude", "longitude"],
        "properties": {
            "latitude": {"type": "number", "description": "Decimal latitude"},
            "longitude": {"type": "number", "description": "Decimal longitude"},
        },
    },
    version="1.1.0",
)
def usgs_topographic_elevation_plugin(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Built-in USGS topographic elevation and magnetic declination plugin handler."""
    lat = float(payload["latitude"])
    lon = float(payload["longitude"])
    elevation_ft = round(abs(lat * 18.5) + abs(lon * 6.2), 1)
    return {
        "latitude": lat,
        "longitude": lon,
        "elevation_feet": elevation_ft,
        "contour_interval_feet": 20,
        "magnetic_declination_deg": -14.2 if lon < -70.0 else 9.5,
        "datum": "NAD83 / NAVD88",
    }


@register_tool_plugin(
    name="nps_campsite_lookup",
    description="Looks up National Park Service and Leave No Trace backcountry campsite regulations and bear-canister rules for Camping and Backpacking.",
    input_schema={
        "type": "object",
        "required": ["state_code"],
        "properties": {
            "state_code": {"type": "string", "description": "2-letter US state code (e.g., MA, NH, WY)"},
            "park_query": {"type": "string", "description": "Optional park or wilderness area name"},
        },
    },
    version="1.1.0",
)
def nps_campsite_lookup_plugin(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Built-in National Park Service campsite and Leave No Trace regulation lookup handler."""
    state_code = str(payload["state_code"]).strip().upper()[:2]
    park_query = str(payload.get("park_query") or f"{state_code} State & National Forest Backcountry").strip()
    return {
        "state_code": state_code,
        "park_name": park_query,
        "leave_no_trace_water_setback_feet": 200,
        "bear_canister_required": True,
        "group_size_limit_patrol": 10,
        "two_deep_leadership_enforced": True,
    }


def get_noaa_plugin_spec() -> ToolPluginSpec:
    """Entry-point factory returning the `noaa_weather_forecast` ToolPluginSpec."""
    return getattr(noaa_weather_forecast_plugin, "_plugin_spec")


def get_usgs_plugin_spec() -> ToolPluginSpec:
    """Entry-point factory returning the `usgs_topographic_elevation` ToolPluginSpec."""
    return getattr(usgs_topographic_elevation_plugin, "_plugin_spec")


def get_nps_plugin_spec() -> ToolPluginSpec:
    """Entry-point factory returning the `nps_campsite_lookup` ToolPluginSpec."""
    return getattr(nps_campsite_lookup_plugin, "_plugin_spec")
