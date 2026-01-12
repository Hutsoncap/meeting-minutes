"""
Speaker Diarization Processor for meeting transcripts.
Uses Pyannote Audio for speaker identification when available,
with fallback to basic speaker segmentation.
"""

import logging
import os
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import pyannote
PYANNOTE_AVAILABLE = False
try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
    logger.info("Pyannote Audio is available for speaker diarization")
except ImportError:
    logger.warning("Pyannote Audio not installed. Speaker diarization will be limited.")


class DiarizationProcessor:
    """Processes audio for speaker diarization."""

    def __init__(self, db):
        self.db = db
        self.pipeline = None
        self._huggingface_token = os.getenv('HF_TOKEN') or os.getenv('HUGGINGFACE_TOKEN')

    async def initialize_pipeline(self):
        """Initialize the Pyannote diarization pipeline."""
        if not PYANNOTE_AVAILABLE:
            logger.warning("Pyannote not available - cannot initialize pipeline")
            return False

        if self.pipeline is not None:
            return True

        if not self._huggingface_token:
            logger.warning("HuggingFace token not found. Set HF_TOKEN or HUGGINGFACE_TOKEN environment variable.")
            return False

        try:
            logger.info("Loading Pyannote speaker diarization pipeline...")
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self._huggingface_token
            )
            logger.info("Pyannote pipeline loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load Pyannote pipeline: {str(e)}")
            return False

    async def diarize_audio(
        self,
        meeting_id: str,
        audio_path: str
    ) -> Dict:
        """
        Perform speaker diarization on an audio file.

        Args:
            meeting_id: The meeting ID to associate speakers with
            audio_path: Path to the audio file

        Returns:
            Dict with speakers and their segments
        """
        logger.info(f"Starting diarization for meeting {meeting_id}, audio: {audio_path}")

        # Update status to processing
        await self.db.create_diarization_process(meeting_id)
        await self.db.update_diarization_process(meeting_id, "processing")

        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            # Try Pyannote if available
            if PYANNOTE_AVAILABLE and await self.initialize_pipeline():
                result = await self._diarize_with_pyannote(meeting_id, audio_path)
            else:
                # Fallback to basic speaker detection
                result = await self._basic_speaker_detection(meeting_id, audio_path)

            await self.db.update_diarization_process(meeting_id, "completed")
            return result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Diarization failed for meeting {meeting_id}: {error_msg}")
            await self.db.update_diarization_process(meeting_id, "failed", error_msg)
            raise

    async def _diarize_with_pyannote(self, meeting_id: str, audio_path: str) -> Dict:
        """Perform diarization using Pyannote."""
        logger.info(f"Running Pyannote diarization on {audio_path}")

        # Run diarization
        diarization = self.pipeline(audio_path)

        # Process results
        speakers = {}
        segments = []
        speaker_colors = [
            "#4299E1",  # blue
            "#48BB78",  # green
            "#ED8936",  # orange
            "#9F7AEA",  # purple
            "#F56565",  # red
            "#38B2AC",  # teal
            "#ECC94B",  # yellow
            "#ED64A6",  # pink
        ]

        for turn, _, speaker_label in diarization.itertracks(yield_label=True):
            # Create speaker if not exists
            if speaker_label not in speakers:
                color = speaker_colors[len(speakers) % len(speaker_colors)]
                speaker_id = await self.db.create_speaker(
                    meeting_id,
                    f"Speaker {len(speakers) + 1}",
                    color
                )
                speakers[speaker_label] = {
                    "id": speaker_id,
                    "label": f"Speaker {len(speakers) + 1}",
                    "color": color,
                    "original_label": speaker_label
                }

            segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker_id": speakers[speaker_label]["id"],
                "speaker_label": speakers[speaker_label]["label"]
            })

        # Assign speakers to transcript segments based on timestamps
        await self._assign_speakers_to_transcripts(meeting_id, segments)

        return {
            "meeting_id": meeting_id,
            "speakers": list(speakers.values()),
            "segments": segments,
            "method": "pyannote"
        }

    async def _basic_speaker_detection(self, meeting_id: str, audio_path: str) -> Dict:
        """
        Basic speaker detection fallback when Pyannote is not available.
        This creates a single speaker for the entire meeting.
        """
        logger.info(f"Using basic speaker detection for {audio_path}")

        # Create a single default speaker
        speaker_id = await self.db.create_speaker(
            meeting_id,
            "Speaker 1",
            "#4299E1"  # blue
        )

        # Get all transcripts for this meeting and assign the speaker
        transcripts = await self._get_meeting_transcripts(meeting_id)

        for transcript in transcripts:
            await self.db.assign_speaker_to_transcript(
                transcript["id"],
                speaker_id,
                "Speaker 1"
            )

        return {
            "meeting_id": meeting_id,
            "speakers": [{
                "id": speaker_id,
                "label": "Speaker 1",
                "color": "#4299E1"
            }],
            "segments": [],
            "method": "basic"
        }

    async def _assign_speakers_to_transcripts(self, meeting_id: str, segments: List[Dict]):
        """Assign speakers to transcript segments based on time overlap."""
        transcripts = await self._get_meeting_transcripts(meeting_id)

        for transcript in transcripts:
            start_time = transcript.get("audio_start_time")
            end_time = transcript.get("audio_end_time")

            if start_time is None or end_time is None:
                continue

            # Find the speaker with most overlap
            best_speaker = None
            best_overlap = 0

            for segment in segments:
                # Calculate overlap
                overlap_start = max(start_time, segment["start"])
                overlap_end = min(end_time, segment["end"])
                overlap = max(0, overlap_end - overlap_start)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = segment

            if best_speaker:
                await self.db.assign_speaker_to_transcript(
                    transcript["id"],
                    best_speaker["speaker_id"],
                    best_speaker["speaker_label"]
                )

    async def _get_meeting_transcripts(self, meeting_id: str) -> List[Dict]:
        """Get transcripts for a meeting with their timestamps."""
        from aiosqlite import connect as aiosqlite_connect

        async with aiosqlite_connect(self.db.db_path) as conn:
            cursor = await conn.execute("""
                SELECT id, audio_start_time, audio_end_time
                FROM transcripts
                WHERE meeting_id = ?
                ORDER BY audio_start_time ASC
            """, (meeting_id,))
            rows = await cursor.fetchall()
            columns = ["id", "audio_start_time", "audio_end_time"]
            return [dict(zip(columns, row)) for row in rows]

    async def get_meeting_speakers(self, meeting_id: str) -> List[Dict]:
        """Get all speakers for a meeting."""
        return await self.db.get_speakers_for_meeting(meeting_id)

    async def update_speaker_label(self, speaker_id: str, new_label: str) -> bool:
        """Update a speaker's display label."""
        return await self.db.update_speaker(speaker_id, label=new_label)

    async def get_diarization_status(self, meeting_id: str) -> Optional[Dict]:
        """Get the current diarization status for a meeting."""
        return await self.db.get_diarization_status(meeting_id)


def is_pyannote_available() -> bool:
    """Check if Pyannote is available for use."""
    return PYANNOTE_AVAILABLE
