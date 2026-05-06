"""Time-based provider and model selection for surge pricing optimization.

This module implements time-based provider/model selection to enable users to
schedule different providers/models during different time windows. This allows
economical token management through off-peak pricing optimization.

Time windows are resolved once at session start and do not switch mid-session.
Users must use /new to re-evaluate time windows, or /model to override.

Configuration is per-profile at ~/.hermes/config.yaml or ~/.hermes/profiles/<name>/config.yaml.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def resolve_time_window(config: dict[str, Any], current_time: datetime | None = None) -> dict[str, Any]:
    """Resolve which time window is active and return its provider/model config.

    Args:
        config: time_windows configuration dict with 'timezone', 'default', and optional 'windows'
        current_time: Optional override for testing (defaults to now in configured timezone)

    Returns:
        Dict with provider, model, and optional provider_routing

    Example:
        >>> config = {
        ...     'enabled': True,
        ...     'timezone': 'America/New_York',
        ...     'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
        ...     'windows': [
        ...         {
        ...             'name': 'off-peak',
        ...             'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
        ...             'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
        ...         }
        ...     ]
        ... }
        >>> resolve_time_window(config)
        {'provider': 'openrouter', 'model': 'gemini-3-flash'}
    """
    if not config.get('enabled', True):
        logger.info("Time windows disabled, using default")
        return config['default']

    # Get current time in configured timezone
    try:
        tz = ZoneInfo(config['timezone'])
    except Exception as e:
        logger.warning(f"Invalid timezone '{config['timezone']}': {e}")
        logger.info("Falling back to default provider/model")
        return config['default']

    now = current_time or datetime.now(tz)

    # Iterate windows in order (first match wins)
    for window in config.get('windows', []):
        if not window.get('enabled', True):
            continue

        schedule = window.get('schedule', {})
        if matches_schedule(schedule, now):
            logger.info(f"Active time window: {window['name']}")
            return window['provider']

    # No window matched, use default
    logger.info("No matching time window, using default")
    return config['default']


def matches_schedule(schedule: dict[str, Any], now: datetime) -> bool:
    """Check if current time matches a schedule specification.

    Supports:
        - daily: time range within a day (supports cross-midnight)
        - weekly: day-of-week matching
        - daily with days: combination of time range and day filter

    Args:
        schedule: Schedule dict with 'type' and type-specific fields
        now: Current datetime to check against

    Returns:
        True if schedule matches current time, False otherwise
    """
    schedule_type = schedule.get('type', 'daily')

    if schedule_type == 'daily':
        return matches_daily_schedule(schedule, now)
    elif schedule_type == 'weekly':
        return matches_weekly_schedule(schedule, now)
    else:
        logger.warning(f"Unknown schedule type: {schedule_type}")
        return False


def matches_daily_schedule(schedule: dict[str, Any], now: datetime) -> bool:
    """Match a daily time range schedule, optionally filtered by day-of-week.

    Handles cross-midnight windows (e.g., 22:00 - 06:00).

    Args:
        schedule: Schedule dict with 'start_time', 'end_time', optional 'days'
        now: Current datetime

    Returns:
        True if current time falls within schedule, False otherwise
    """
    # Check day-of-week filter if specified
    if 'days' in schedule:
        today_name = now.strftime('%A').lower()
        days = [d.lower() for d in schedule['days']]

        # Handle 'weekday' and 'weekend' aliases
        if 'weekday' in days:
            if today_name in ['saturday', 'sunday']:
                return False
        elif 'weekend' in days:
            if today_name in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
                return False
        elif today_name not in days:
            return False

    # Parse time range
    try:
        start_str = schedule.get('start_time', '00:00')
        end_str = schedule.get('end_time', '23:59')
        start_time = datetime.strptime(start_str, '%H:%M').time()
        end_time = datetime.strptime(end_str, '%H:%M').time()
        current_time = now.time()
    except ValueError as e:
        logger.warning(f"Invalid time format in schedule: {e}")
        return False

    # Handle cross-midnight case
    if start_time <= end_time:
        # Normal case: start_time <= end_time (e.g., 09:00 - 17:00)
        return start_time <= current_time <= end_time
    else:
        # Cross-midnight case: start_time > end_time (e.g., 22:00 - 06:00)
        return current_time >= start_time or current_time <= end_time


def matches_weekly_schedule(schedule: dict[str, Any], now: datetime) -> bool:
    """Match a weekly schedule based on day-of-week.

    Args:
        schedule: Schedule dict with 'days' list
        now: Current datetime

    Returns:
        True if current day is in schedule, False otherwise
    """
    today_name = now.strftime('%A').lower()
    days = [d.lower() for d in schedule.get('days', [])]
    return today_name in days


def validate_time_windows_config(config: dict[str, Any]) -> list[str]:
    """Validate time_windows configuration and return list of error messages.

    Args:
        config: time_windows configuration dict

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Check required fields
    if 'timezone' not in config:
        errors.append("time_windows.timezone is required")
    else:
        # Validate timezone
        try:
            ZoneInfo(config['timezone'])
        except Exception as e:
            errors.append(f"time_windows.timezone must be valid IANA timezone: {e}")

    # Check default
    if 'default' not in config:
        errors.append("time_windows.default is required")
    else:
        default = config['default']
        if 'provider' not in default:
            errors.append("time_windows.default.provider is required")
        if 'model' not in default:
            errors.append("time_windows.default.model is required")

    # Validate windows
    for i, window in enumerate(config.get('windows', [])):
        prefix = f"time_windows.windows[{i}]"

        if 'name' not in window:
            errors.append(f"{prefix}.name is required")

        if 'schedule' not in window:
            errors.append(f"{prefix}.schedule is required")
        else:
            schedule = window['schedule']
            schedule_type = schedule.get('type', 'daily')

            if schedule_type not in ['daily', 'weekly']:
                errors.append(f"{prefix}.schedule.type must be 'daily' or 'weekly'")

            if schedule_type == 'daily':
                if 'start_time' in schedule:
                    try:
                        datetime.strptime(schedule['start_time'], '%H:%M')
                    except ValueError:
                        errors.append(f"{prefix}.schedule.start_time must be HH:MM format")
                if 'end_time' in schedule:
                    try:
                        datetime.strptime(schedule['end_time'], '%H:%M')
                    except ValueError:
                        errors.append(f"{prefix}.schedule.end_time must be HH:MM format")
                if 'days' in schedule:
                    valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'weekday', 'weekend']
                    for day in schedule['days']:
                        if day.lower() not in valid_days:
                            errors.append(f"{prefix}.schedule.days contains invalid day: {day}")

            elif schedule_type == 'weekly':
                if 'days' not in schedule:
                    errors.append(f"{prefix}.schedule.days is required for weekly schedule")
                else:
                    valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'weekday', 'weekend']
                    for day in schedule['days']:
                        if day.lower() not in valid_days:
                            errors.append(f"{prefix}.schedule.days contains invalid day: {day}")

        if 'provider' not in window:
            errors.append(f"{prefix}.provider is required")
        else:
            provider = window['provider']
            if 'provider' not in provider:
                errors.append(f"{prefix}.provider.provider is required")
            if 'model' not in provider:
                errors.append(f"{prefix}.provider.model is required")

    return errors


# Convenience function for testing
def get_active_window_name(config: dict[str, Any], current_time: datetime | None = None) -> str | None:
    """Get the name of the active time window (for testing/logging).

    Args:
        config: time_windows configuration dict
        current_time: Optional override for testing

    Returns:
        Window name if one is active, None if using default
    """
    if not config.get('enabled', True):
        return None

    try:
        tz = ZoneInfo(config['timezone'])
    except Exception:
        return None

    now = current_time or datetime.now(tz)

    for window in config.get('windows', []):
        if not window.get('enabled', True):
            continue

        schedule = window.get('schedule', {})
        if matches_schedule(schedule, now):
            return window.get('name')

    return None