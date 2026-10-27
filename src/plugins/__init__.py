"""Dynamic tool plugin architecture with `@register_tool_plugin` and `entry_points` discovery."""

from src.plugins.registry import (
    GLOBAL_PLUGIN_REGISTRY,
    PluginRegistry,
    PluginValidationError,
    ToolPluginSpec,
    get_noaa_plugin_spec,
    get_nps_plugin_spec,
    get_usgs_plugin_spec,
    noaa_weather_forecast_plugin,
    nps_campsite_lookup_plugin,
    register_tool_plugin,
    usgs_topographic_elevation_plugin,
)

__all__ = [
    "GLOBAL_PLUGIN_REGISTRY",
    "PluginRegistry",
    "PluginValidationError",
    "ToolPluginSpec",
    "get_noaa_plugin_spec",
    "get_nps_plugin_spec",
    "get_usgs_plugin_spec",
    "noaa_weather_forecast_plugin",
    "nps_campsite_lookup_plugin",
    "register_tool_plugin",
    "usgs_topographic_elevation_plugin",
]
