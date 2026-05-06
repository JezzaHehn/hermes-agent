"""Unit tests for time window selection functionality."""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo

from agent.time_window_selector import (
    resolve_time_window,
    matches_schedule,
    matches_daily_schedule,
    matches_weekly_schedule,
    validate_time_windows_config,
    get_active_window_name,
)


class TestResolveTimeWindow:
    """Tests for resolve_time_window function."""

    def test_disabled_time_windows(self):
        """When time_windows.enabled is False, should use default."""
        config = {
            'enabled': False,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        result = resolve_time_window(config)
        assert result['provider'] == 'openrouter'
        assert result['model'] == 'claude-opus-4.6'

    def test_no_matching_window_uses_default(self):
        """When no time window matches, should use default."""
        config = {
            'enabled': True,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        # Current time is 12:00 (noon) - no window match
        current_time = datetime(2024, 1, 1, 12, 0, tzinfo=ZoneInfo('America/New_York'))
        result = resolve_time_window(config, current_time)
        assert result['provider'] == 'openrouter'
        assert result['model'] == 'claude-opus-4.6'

    def test_matching_window_overrides_default(self):
        """When a time window matches, should use window config."""
        config = {
            'enabled': True,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        # Current time is 23:00 (11 PM) - matches night window
        current_time = datetime(2024, 1, 1, 23, 0, tzinfo=ZoneInfo('America/New_York'))
        result = resolve_time_window(config, current_time)
        assert result['provider'] == 'openrouter'
        assert result['model'] == 'gemini-3-flash'

    def test_first_window_wins(self):
        """When multiple windows match, first one wins."""
        config = {
            'enabled': True,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                },
                {
                    'name': 'late-night',
                    'schedule': {'type': 'daily', 'start_time': '00:00', 'end_time': '23:59'},
                    'provider': {'provider': 'openrouter', 'model': 'claude-sonnet-4'}
                }
            ]
        }
        # Current time is 01:00 AM - matches both windows, first one wins
        current_time = datetime(2024, 1, 1, 1, 0, tzinfo=ZoneInfo('America/New_York'))
        result = resolve_time_window(config, current_time)
        assert result['model'] == 'gemini-3-flash'

    def test_disabled_window_is_skipped(self):
        """Disabled windows should be skipped."""
        config = {
            'enabled': True,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'enabled': False,
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        # Current time is 23:00 - would match but window is disabled
        current_time = datetime(2024, 1, 1, 23, 0, tzinfo=ZoneInfo('America/New_York'))
        result = resolve_time_window(config, current_time)
        assert result['model'] == 'claude-opus-4.6'

    def test_invalid_timezone_fallback(self):
        """Invalid timezone should fall back to default."""
        config = {
            'enabled': True,
            'timezone': 'Invalid/Timezone',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': []
        }
        result = resolve_time_window(config)
        assert result['model'] == 'claude-opus-4.6'

    def test_provider_routing_included(self):
        """Provider routing config should be included in result."""
        config = {
            'enabled': True,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {
                        'provider': 'openrouter',
                        'model': 'gemini-3-flash',
                        'provider_routing': {'sort': 'price', 'data_collection': 'deny'}
                    }
                }
            ]
        }
        current_time = datetime(2024, 1, 1, 23, 0, tzinfo=ZoneInfo('America/New_York'))
        result = resolve_time_window(config, current_time)
        assert 'provider_routing' in result
        assert result['provider_routing']['sort'] == 'price'


class TestMatchesDailySchedule:
    """Tests for matches_daily_schedule function."""

    def test_normal_time_range(self):
        """Test normal time range (start < end)."""
        schedule = {'type': 'daily', 'start_time': '09:00', 'end_time': '17:00'}
        
        # Inside range
        assert matches_daily_schedule(schedule, datetime(2024, 1, 1, 12, 0))
        # Outside range
        assert not matches_daily_schedule(schedule, datetime(2024, 1, 1, 8, 0))
        assert not matches_daily_schedule(schedule, datetime(2024, 1, 1, 18, 0))

    def test_cross_midnight_range(self):
        """Test cross-midnight time range (start > end)."""
        schedule = {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'}
        
        # Inside range (before midnight)
        assert matches_daily_schedule(schedule, datetime(2024, 1, 1, 23, 0))
        # Inside range (after midnight)
        assert matches_daily_schedule(schedule, datetime(2024, 1, 1, 3, 0))
        # Outside range (daytime)
        assert not matches_daily_schedule(schedule, datetime(2024, 1, 1, 12, 0))

    def test_day_filter_weekday(self):
        """Test weekday filter."""
        schedule = {
            'type': 'daily',
            'start_time': '09:00',
            'end_time': '17:00',
            'days': ['weekday']
        }
        
        # Monday (weekday)
        monday = datetime(2024, 1, 1, 12, 0)  # Monday
        assert matches_daily_schedule(schedule, monday)
        
        # Saturday (weekend)
        saturday = datetime(2024, 1, 6, 12, 0)  # Saturday
        assert not matches_daily_schedule(schedule, saturday)

    def test_day_filter_weekend(self):
        """Test weekend filter."""
        schedule = {
            'type': 'daily',
            'start_time': '00:00',
            'end_time': '23:59',
            'days': ['weekend']
        }
        
        # Saturday
        saturday = datetime(2024, 1, 6, 12, 0)
        assert matches_daily_schedule(schedule, saturday)
        
        # Monday
        monday = datetime(2024, 1, 1, 12, 0)
        assert not matches_daily_schedule(schedule, monday)

    def test_invalid_time_format(self):
        """Test invalid time format returns False."""
        schedule = {'type': 'daily', 'start_time': 'invalid', 'end_time': '17:00'}
        assert not matches_daily_schedule(schedule, datetime(2024, 1, 1, 12, 0))


class TestMatchesWeeklySchedule:
    """Tests for matches_weekly_schedule function."""

    def test_single_day_match(self):
        """Test matching a single day."""
        schedule = {'type': 'weekly', 'days': ['monday']}
        
        monday = datetime(2024, 1, 1, 12, 0)  # Monday
        assert matches_weekly_schedule(schedule, monday)
        
        tuesday = datetime(2024, 1, 2, 12, 0)  # Tuesday
        assert not matches_weekly_schedule(schedule, tuesday)

    def test_multiple_days_match(self):
        """Test matching multiple days."""
        schedule = {'type': 'weekly', 'days': ['saturday', 'sunday']}
        
        saturday = datetime(2024, 1, 6, 12, 0)
        assert matches_weekly_schedule(schedule, saturday)
        
        sunday = datetime(2024, 1, 7, 12, 0)
        assert matches_weekly_schedule(schedule, sunday)
        
        monday = datetime(2024, 1, 1, 12, 0)
        assert not matches_weekly_schedule(schedule, monday)


class TestValidateTimeWindowsConfig:
    """Tests for validate_time_windows_config function."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = {
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        errors = validate_time_windows_config(config)
        assert len(errors) == 0

    def test_missing_timezone(self):
        """Test missing timezone."""
        config = {
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': []
        }
        errors = validate_time_windows_config(config)
        assert 'timezone is required' in errors[0]

    def test_invalid_timezone(self):
        """Test invalid timezone."""
        config = {
            'timezone': 'Invalid/Timezone',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': []
        }
        errors = validate_time_windows_config(config)
        assert any('timezone' in e for e in errors)

    def test_missing_default(self):
        """Test missing default."""
        config = {
            'timezone': 'America/New_York',
            'windows': []
        }
        errors = validate_time_windows_config(config)
        assert 'default is required' in errors[0]

    def test_invalid_time_format(self):
        """Test invalid time format in window."""
        config = {
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': 'invalid', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        errors = validate_time_windows_config(config)
        assert any('HH:MM format' in e for e in errors)

    def test_invalid_schedule_type(self):
        """Test invalid schedule type."""
        config = {
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'invalid'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        errors = validate_time_windows_config(config)
        assert any("'daily' or 'weekly'" in e for e in errors)


class TestGetActiveWindowName:
    """Tests for get_active_window_name function."""

    def test_active_window_name(self):
        """Test getting active window name."""
        config = {
            'enabled': True,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        # Matching time
        current_time = datetime(2024, 1, 1, 23, 0, tzinfo=ZoneInfo('America/New_York'))
        name = get_active_window_name(config, current_time)
        assert name == 'night'

    def test_no_active_window(self):
        """Test when no window is active."""
        config = {
            'enabled': True,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': [
                {
                    'name': 'night',
                    'schedule': {'type': 'daily', 'start_time': '22:00', 'end_time': '06:00'},
                    'provider': {'provider': 'openrouter', 'model': 'gemini-3-flash'}
                }
            ]
        }
        # Non-matching time
        current_time = datetime(2024, 1, 1, 12, 0, tzinfo=ZoneInfo('America/New_York'))
        name = get_active_window_name(config, current_time)
        assert name is None

    def test_disabled_returns_none(self):
        """Test when time windows are disabled."""
        config = {
            'enabled': False,
            'timezone': 'America/New_York',
            'default': {'provider': 'openrouter', 'model': 'claude-opus-4.6'},
            'windows': []
        }
        name = get_active_window_name(config)
        assert name is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])