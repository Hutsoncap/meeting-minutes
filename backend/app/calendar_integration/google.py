"""
Google Calendar Integration.
Handles OAuth authentication and event fetching from Google Calendar.
"""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import Google API libraries
GOOGLE_API_AVAILABLE = False
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
    logger.info("Google API libraries are available")
except ImportError:
    logger.warning("Google API libraries not installed. Install with: pip install google-api-python-client google-auth-oauthlib")


# OAuth 2.0 scopes for Google Calendar
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Meeting URL patterns for various platforms
MEETING_URL_PATTERNS = [
    # Zoom
    r'https?://[\w.-]*zoom\.us/j/\d+(?:\?pwd=[\w]+)?',
    # Google Meet
    r'https?://meet\.google\.com/[\w-]+',
    # Microsoft Teams
    r'https?://teams\.microsoft\.com/l/meetup-join/[\w/%@.-]+',
    # Webex
    r'https?://[\w.-]*webex\.com/[\w/.-]+',
    # GoToMeeting
    r'https?://[\w.-]*gotomeeting\.com/join/\d+',
]


def extract_meeting_url(text: str) -> Optional[str]:
    """Extract meeting URL from text (description or location)."""
    if not text:
        return None

    for pattern in MEETING_URL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return None


class GoogleCalendarClient:
    """Google Calendar API client for fetching events."""

    def __init__(self, db):
        self.db = db
        self._client_id = os.getenv('GOOGLE_CLIENT_ID')
        self._client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self._redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5167/calendar/auth/google/callback')
        self._credentials_loaded = False

    async def _load_credentials_from_db(self):
        """Load OAuth credentials from database if not set via environment"""
        if self._credentials_loaded:
            return

        if not self._client_id or not self._client_secret:
            try:
                creds = await self.db.get_google_oauth_credentials()
                if creds:
                    self._client_id = creds.get('client_id')
                    self._client_secret = creds.get('client_secret')
                    self._redirect_uri = creds.get('redirect_uri', self._redirect_uri)
                    logger.info("Loaded Google OAuth credentials from database")
            except Exception as e:
                logger.error(f"Failed to load OAuth credentials from DB: {e}")

        self._credentials_loaded = True

    @property
    def is_configured(self) -> bool:
        """Check if Google OAuth is configured."""
        return bool(self._client_id and self._client_secret)

    async def check_is_configured(self) -> bool:
        """Async check if Google OAuth is configured (loads from DB if needed)."""
        await self._load_credentials_from_db()
        return self.is_configured

    @property
    def is_available(self) -> bool:
        """Check if Google Calendar integration is available."""
        return GOOGLE_API_AVAILABLE and self.is_configured

    async def check_is_available(self) -> bool:
        """Async check if Google Calendar integration is available."""
        await self._load_credentials_from_db()
        return GOOGLE_API_AVAILABLE and self.is_configured

    async def get_auth_url(self, state: str = None) -> Optional[str]:
        """Generate OAuth authorization URL."""
        if not GOOGLE_API_AVAILABLE:
            logger.error("Google API libraries not available")
            return None

        await self._load_credentials_from_db()

        if not self.is_configured:
            logger.error("Google OAuth not configured. Set credentials via settings or environment variables.")
            return None

        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self._redirect_uri]
                    }
                },
                scopes=SCOPES
            )
            flow.redirect_uri = self._redirect_uri

            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',
                state=state
            )

            return auth_url
        except Exception as e:
            logger.error(f"Failed to generate auth URL: {str(e)}")
            return None

    async def exchange_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for tokens."""
        if not GOOGLE_API_AVAILABLE:
            return None

        await self._load_credentials_from_db()

        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self._redirect_uri]
                    }
                },
                scopes=SCOPES
            )
            flow.redirect_uri = self._redirect_uri

            flow.fetch_token(code=code)
            credentials = flow.credentials

            # Get user email
            service = build('calendar', 'v3', credentials=credentials)
            calendar = service.calendars().get(calendarId='primary').execute()
            email = calendar.get('summary', 'Unknown')

            # Calculate token expiry
            token_expires_at = None
            if credentials.expiry:
                token_expires_at = credentials.expiry.isoformat()

            # Save account to database
            account_id = await self.db.create_calendar_account(
                provider='google',
                email=email,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expires_at=token_expires_at
            )

            return {
                'account_id': account_id,
                'email': email
            }

        except Exception as e:
            logger.error(f"Failed to exchange code: {str(e)}")
            return None

    async def _get_credentials(self, account_id: str) -> Optional[Any]:
        """Get valid credentials for an account, refreshing if necessary."""
        if not GOOGLE_API_AVAILABLE:
            return None

        await self._load_credentials_from_db()

        account = await self.db.get_calendar_account_by_id(account_id)
        if not account:
            return None

        credentials = Credentials(
            token=account['access_token'],
            refresh_token=account['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=self._client_id,
            client_secret=self._client_secret
        )

        # Check if token needs refresh
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())

                # Update tokens in database
                token_expires_at = None
                if credentials.expiry:
                    token_expires_at = credentials.expiry.isoformat()

                await self.db.update_calendar_account_tokens(
                    account_id,
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    token_expires_at=token_expires_at
                )
            except Exception as e:
                logger.error(f"Failed to refresh token: {str(e)}")
                return None

        return credentials

    async def sync_events(self, account_id: str, days_ahead: int = 7) -> List[Dict]:
        """Sync events from Google Calendar for the next N days."""
        if not GOOGLE_API_AVAILABLE:
            logger.warning("Google API not available")
            return []

        credentials = await self._get_credentials(account_id)
        if not credentials:
            logger.error(f"No valid credentials for account {account_id}")
            return []

        try:
            service = build('calendar', 'v3', credentials=credentials)

            # Calculate time range
            now = datetime.utcnow()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days_ahead)).isoformat() + 'Z'

            # Fetch events
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=50,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            synced_events = []

            for event in events:
                # Extract meeting URL from description or location
                description = event.get('description', '')
                location = event.get('location', '')
                meeting_url = extract_meeting_url(description) or extract_meeting_url(location)

                # Also check for Google Meet conference data
                if not meeting_url and event.get('conferenceData'):
                    entry_points = event['conferenceData'].get('entryPoints', [])
                    for entry in entry_points:
                        if entry.get('entryPointType') == 'video':
                            meeting_url = entry.get('uri')
                            break

                # Parse start and end times
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                # Extract attendees
                attendees = []
                for attendee in event.get('attendees', []):
                    attendees.append({
                        'email': attendee.get('email'),
                        'name': attendee.get('displayName'),
                        'response': attendee.get('responseStatus')
                    })

                # Upsert event in database
                event_id = await self.db.upsert_calendar_event(
                    account_id=account_id,
                    external_id=event['id'],
                    title=event.get('summary', 'Untitled'),
                    start_time=start,
                    end_time=end,
                    description=description,
                    meeting_url=meeting_url,
                    attendees=attendees
                )

                synced_events.append({
                    'id': event_id,
                    'external_id': event['id'],
                    'title': event.get('summary', 'Untitled'),
                    'start_time': start,
                    'end_time': end,
                    'meeting_url': meeting_url,
                    'attendees': attendees
                })

            logger.info(f"Synced {len(synced_events)} events for account {account_id}")
            return synced_events

        except Exception as e:
            logger.error(f"Failed to sync events: {str(e)}")
            return []

    async def get_upcoming_events(self, limit: int = 10) -> List[Dict]:
        """Get upcoming events from all connected accounts."""
        return await self.db.get_upcoming_events(limit)


def is_google_calendar_available() -> bool:
    """Check if Google Calendar integration is available."""
    return GOOGLE_API_AVAILABLE
