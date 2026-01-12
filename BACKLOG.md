# Meetily Feature Backlog

This document tracks features that are planned for future development.

## In Development

### Auto-Detect Active Meetings
- **Status**: Planned
- **Description**: Automatically detect when Zoom, Teams, or Google Meet starts on the system and prompt the user to begin recording.
- **Technical Notes**:
  - Requires system-level access to detect running applications
  - May need accessibility permissions on macOS
  - Consider using process monitoring or window detection
- **Priority**: High

## Backlog Features

### Chat with Meetings (AI Q&A)
- **Status**: Backlog (UI removed, backend ready)
- **Description**: Interactive chat interface to ask questions about meeting content, get clarifications, and extract specific information from transcripts.
- **Technical Notes**:
  - Backend chat endpoints exist in `/backend/app/main.py`
  - Frontend components exist in `/frontend/src/components/Chat/`
  - Uses the same LLM provider as summarization
- **Priority**: Medium
- **Reason for Backlog**: Feature needs refinement and UX improvements before re-enabling

### Speaker Diarization Improvements
- **Status**: Backlog
- **Description**: Improved speaker identification and separation during transcription
- **Priority**: Medium

### Meeting Search
- **Status**: Backlog
- **Description**: Full-text search across all meeting transcripts and summaries
- **Priority**: Medium

### Meeting Analytics Dashboard
- **Status**: Backlog
- **Description**: Visualize meeting patterns, speaking time distribution, and topic trends
- **Priority**: Low

### Calendar-Based Auto-Recording
- **Status**: Backlog
- **Description**: Automatically start recording based on calendar events with meeting links
- **Technical Notes**:
  - Builds on existing Google Calendar integration
  - Requires auto-join settings configuration
- **Priority**: Medium

## Recently Completed Features

### v0.2.0 (Current Development)

1. **OpenRouter Integration** - Use any OpenRouter model for summarization
2. **Custom Summary Templates** - Create and customize summary formats
3. **Speaker Identification** - Assign speaker labels to transcript segments
4. **Google Calendar OAuth** - User-configurable OAuth for calendar integration
5. **Export Options** - Export summaries as PDF, DOCX, or Markdown

## Feature Requests

To request a new feature, please open an issue on GitHub with the "feature request" label.
