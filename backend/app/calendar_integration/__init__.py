"""Calendar integration module for Google Calendar."""
try:
    from .google import GoogleCalendarClient, extract_meeting_url, is_google_calendar_available
except ImportError:
    # Fallback if Google libraries not installed
    GoogleCalendarClient = None
    extract_meeting_url = None
    is_google_calendar_available = lambda: False
