"""Convenience wrapper for time window resolution in CLI and gateway.

This module provides a simple interface to resolve time windows from config
and apply them to provider/model selection.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.time_window_selector import resolve_time_window, get_active_window_name

logger = logging.getLogger(__name__)


def apply_time_windows(
    config: dict[str, Any],
    provider: str | None,
    model: str | None,
    provider_routing: dict[str, Any] | None = None,
) -> tuple[str | None, str | None, dict[str, Any] | None, str | None]:
    """Apply time windows to provider/model selection.

    Args:
        config: Full config dict (must include 'time_windows' key if configured)
        provider: Provider name from config or args (None if not set)
        model: Model name from config or args (None if not set)
        provider_routing: Provider routing config from config (None if not set)

    Returns:
        Tuple of (resolved_provider, resolved_model, resolved_provider_routing, window_name)
        - resolved_provider: Time-window-resolved provider, or original if no time window
        - resolved_model: Time-window-resolved model, or original if no time window
        - resolved_provider_routing: Time-window-resolved routing, or original if no time window
        - window_name: Name of active window (None if using default)

    Example:
        >>> config = load_cli_config()
        >>> provider, model, routing, window_name = apply_time_windows(
        ...     config,
        ...     provider=config['model'].get('provider'),
        ...     model=config['model'].get('default') or config['model'].get('model'),
        ...     provider_routing=config.get('provider_routing')
        ... )
    """
    # Check if time_windows is configured
    time_windows_config = config.get('time_windows')
    if not time_windows_config or not isinstance(time_windows_config, dict):
        # No time windows configured
        return provider, model, provider_routing, None

    # Check if time windows are enabled
    if not time_windows_config.get('enabled', True):
        logger.info("Time windows disabled via configuration")
        return provider, model, provider_routing, None

    # Resolve time window
    try:
        resolved = resolve_time_window(time_windows_config)
        window_name = get_active_window_name(time_windows_config)

        # Apply resolved values
        resolved_provider = resolved.get('provider') or provider
        resolved_model = resolved.get('model') or model
        resolved_routing = resolved.get('provider_routing')

        if window_name:
            logger.info(
                f"Time window resolved: {window_name} -> "
                f"provider={resolved_provider}, model={resolved_model}"
            )
        else:
            logger.info(
                f"Using default time window -> "
                f"provider={resolved_provider}, model={resolved_model}"
            )

        return resolved_provider, resolved_model, resolved_routing, window_name

    except Exception as e:
        logger.warning(f"Time window resolution failed: {e}")
        # Fall back to original values on error
        return provider, model, provider_routing, None