import aiosqlite
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
import logging
from contextlib import asynccontextmanager
import sqlite3
try:
    from .schema_validator import SchemaValidator
except ImportError:
    # Handle case when running as script directly
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.getenv('DATABASE_PATH', 'meeting_minutes.db')
        self.db_path = db_path
        self.schema_validator = SchemaValidator(self.db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the database with legacy approach"""
        try:
            # Run legacy initialization (handles all table creation)
            logger.info("Initializing database tables...")
            self._legacy_init_db()
            
            # Validate schema integrity
            logger.info("Validating schema integrity...")
            self.schema_validator.validate_schema()
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise



    def _legacy_init_db(self):
        """Legacy database initialization (for backward compatibility)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create meetings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    folder_path TEXT
                )
            """)

            # Migration: Add folder_path column to existing meetings table
            try:
                cursor.execute("ALTER TABLE meetings ADD COLUMN folder_path TEXT")
                logger.info("Added folder_path column to meetings table")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Create transcripts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    summary TEXT,
                    action_items TEXT,
                    key_points TEXT,
                    audio_start_time REAL,
                    audio_end_time REAL,
                    duration REAL,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id)
                )
            """)

            # Add new columns to existing transcripts table (migration for old databases)
            try:
                cursor.execute("ALTER TABLE transcripts ADD COLUMN audio_start_time REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                cursor.execute("ALTER TABLE transcripts ADD COLUMN audio_end_time REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                cursor.execute("ALTER TABLE transcripts ADD COLUMN duration REAL")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Create summary_processes table (keeping existing functionality)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summary_processes (
                    meeting_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT,
                    result TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    chunk_count INTEGER DEFAULT 0,
                    processing_time REAL DEFAULT 0.0,
                    metadata TEXT,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcript_chunks (
                    meeting_id TEXT PRIMARY KEY,
                    meeting_name TEXT,
                    transcript_text TEXT NOT NULL,
                    model TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    chunk_size INTEGER,
                    overlap INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id)
                )
            """)

            # Create settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    whisperModel TEXT NOT NULL,
                    groqApiKey TEXT,
                    openaiApiKey TEXT,
                    anthropicApiKey TEXT,
                    ollamaApiKey TEXT,
                    openRouterApiKey TEXT
                )
            """)

            # Create transcript_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcript_settings (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    whisperApiKey TEXT,
                    deepgramApiKey TEXT,
                    elevenLabsApiKey TEXT,
                    groqApiKey TEXT,
                    openaiApiKey TEXT
                )
            """)

            # Create summary_templates table for custom summary templates
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summary_templates (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    schema_json TEXT NOT NULL,
                    prompt_template TEXT,
                    is_default INTEGER DEFAULT 0,
                    is_preset INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Create chat_conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_conversations (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    title TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                )
            """)

            # Create chat_messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context_chunks TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE
                )
            """)

            # Create speakers table for speaker identification
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS speakers (
                    id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    color TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                )
            """)

            # Create diarization_processes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS diarization_processes (
                    meeting_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
                )
            """)

            # Add speaker columns to transcripts table (migration for existing databases)
            try:
                cursor.execute("ALTER TABLE transcripts ADD COLUMN speaker_id TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            try:
                cursor.execute("ALTER TABLE transcripts ADD COLUMN speaker_label TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Create calendar_accounts table for Google Calendar integration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_accounts (
                    id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL DEFAULT 'google',
                    email TEXT NOT NULL,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Create calendar_events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    meeting_url TEXT,
                    attendees TEXT,
                    meeting_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (account_id) REFERENCES calendar_accounts(id) ON DELETE CASCADE
                )
            """)

            # Create auto_join_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_join_settings (
                    id TEXT PRIMARY KEY DEFAULT '1',
                    enabled INTEGER DEFAULT 0,
                    auto_record INTEGER DEFAULT 1,
                    reminder_minutes INTEGER DEFAULT 5,
                    supported_platforms TEXT DEFAULT '["zoom","teams","meet"]'
                )
            """)

            # Create meeting_join_log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meeting_join_log (
                    id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES calendar_events(id) ON DELETE CASCADE
                )
            """)

            # Initialize auto_join_settings if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO auto_join_settings (id, enabled, auto_record, reminder_minutes, supported_platforms)
                VALUES ('1', 0, 1, 5, '["zoom","teams","meet"]')
            """)

            conn.commit()

    @asynccontextmanager
    async def _get_connection(self):
        """Get a new database connection"""
        conn = await aiosqlite.connect(self.db_path)
        try:
            yield conn
        finally:
            await conn.close()

    async def create_process(self, meeting_id: str) -> str:
        """Create a new process entry or update existing one and return its ID"""
        now = datetime.utcnow().isoformat()
        
        try:
            async with self._get_connection() as conn:
                # Begin transaction
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    # First try to update existing process
                    await conn.execute(
                        """
                        UPDATE summary_processes 
                        SET status = ?, updated_at = ?, start_time = ?, error = NULL, result = NULL
                        WHERE meeting_id = ?
                        """,
                        ("PENDING", now, now, meeting_id)
                    )
                    
                    # If no rows were updated, insert a new one
                    if conn.total_changes == 0:
                        await conn.execute(
                            "INSERT INTO summary_processes (meeting_id, status, created_at, updated_at, start_time) VALUES (?, ?, ?, ?, ?)",
                            (meeting_id, "PENDING", now, now, now)
                        )
                    
                    await conn.commit()
                    logger.info(f"Successfully created/updated process for meeting_id: {meeting_id}")
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Failed to create process for meeting_id {meeting_id}: {str(e)}", exc_info=True)
                    raise
                    
        except Exception as e:
            logger.error(f"Database connection error in create_process: {str(e)}", exc_info=True)
            raise
        
        return meeting_id

    async def update_process(self, meeting_id: str, status: str, result: Optional[Dict] = None, error: Optional[str] = None, 
                           chunk_count: Optional[int] = None, processing_time: Optional[float] = None, 
                           metadata: Optional[Dict] = None):
        """Update a process status and result"""
        now = datetime.utcnow().isoformat()
        
        try:
            async with self._get_connection() as conn:
                # Begin transaction
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    update_fields = ["status = ?", "updated_at = ?"]
                    params = [status, now]
                    
                    if result:
                        # Validate result can be JSON serialized
                        try:
                            result_json = json.dumps(result)
                            update_fields.append("result = ?")
                            params.append(result_json)
                        except (TypeError, ValueError) as e:
                            logger.error(f"Failed to serialize result for meeting_id {meeting_id}: {str(e)}")
                            raise ValueError("Result data cannot be JSON serialized")
                            
                    if error:
                        # Sanitize error message to prevent log injection
                        sanitized_error = str(error).replace('\n', ' ').replace('\r', '')[:1000]
                        update_fields.append("error = ?")
                        params.append(sanitized_error)
                        
                    if chunk_count is not None:
                        update_fields.append("chunk_count = ?")
                        params.append(chunk_count)
                        
                    if processing_time is not None:
                        update_fields.append("processing_time = ?")
                        params.append(processing_time)
                        
                    if metadata:
                        # Validate metadata can be JSON serialized
                        try:
                            metadata_json = json.dumps(metadata)
                            update_fields.append("metadata = ?")
                            params.append(metadata_json)
                        except (TypeError, ValueError) as e:
                            logger.error(f"Failed to serialize metadata for meeting_id {meeting_id}: {str(e)}")
                            # Don't fail the whole operation for metadata serialization issues
                            
                    if status.upper() in ['COMPLETED', 'FAILED']:
                        update_fields.append("end_time = ?")
                        params.append(now)
                        
                    params.append(meeting_id)
                    query = f"UPDATE summary_processes SET {', '.join(update_fields)} WHERE meeting_id = ?"
                    
                    cursor = await conn.execute(query, params)
                    if cursor.rowcount == 0:
                        logger.warning(f"No process found to update for meeting_id: {meeting_id}")
                        
                    await conn.commit()
                    logger.debug(f"Successfully updated process status to {status} for meeting_id: {meeting_id}")
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Failed to update process for meeting_id {meeting_id}: {str(e)}", exc_info=True)
                    raise
                    
        except Exception as e:
            logger.error(f"Database connection error in update_process: {str(e)}", exc_info=True)
            raise

    async def save_transcript(self, meeting_id: str, transcript_text: str, model: str, model_name: str, 
                            chunk_size: int, overlap: int):
        """Save transcript data"""
        # Input validation
        if not meeting_id or not meeting_id.strip():
            raise ValueError("meeting_id cannot be empty")
        if not transcript_text or not transcript_text.strip():
            raise ValueError("transcript_text cannot be empty")
        if chunk_size <= 0 or overlap < 0:
            raise ValueError("Invalid chunk_size or overlap values")
        if len(transcript_text) > 10_000_000:  # 10MB limit
            raise ValueError("Transcript text too large (>10MB)")
            
        now = datetime.utcnow().isoformat()
        
        try:
            async with self._get_connection() as conn:
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    # First try to update existing transcript
                    await conn.execute("""
                        UPDATE transcript_chunks 
                        SET transcript_text = ?, model = ?, model_name = ?, chunk_size = ?, overlap = ?, created_at = ?
                        WHERE meeting_id = ?
                    """, (transcript_text, model, model_name, chunk_size, overlap, now, meeting_id))
                    
                    # If no rows were updated, insert a new one
                    if conn.total_changes == 0:
                        await conn.execute("""
                            INSERT INTO transcript_chunks (meeting_id, transcript_text, model, model_name, chunk_size, overlap, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (meeting_id, transcript_text, model, model_name, chunk_size, overlap, now))
                    
                    await conn.commit()
                    logger.info(f"Successfully saved transcript for meeting_id: {meeting_id} (size: {len(transcript_text)} chars)")
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Failed to save transcript for meeting_id {meeting_id}: {str(e)}", exc_info=True)
                    raise
                    
        except Exception as e:
            logger.error(f"Database connection error in save_transcript: {str(e)}", exc_info=True)
            raise

    async def update_meeting_name(self, meeting_id: str, meeting_name: str):
        """Update meeting name in both meetings and transcript_chunks tables"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            # Update meetings table
            await conn.execute("""
                UPDATE meetings
                SET title = ?, updated_at = ?
                WHERE id = ?
            """, (meeting_name, now, meeting_id))
            
            # Update transcript_chunks table
            await conn.execute("""
                UPDATE transcript_chunks
                SET meeting_name = ?
                WHERE meeting_id = ?
            """, (meeting_name, meeting_id))
            
            await conn.commit()

    async def get_transcript_data(self, meeting_id: str):
        """Get transcript data for a meeting"""
        async with self._get_connection() as conn:
            async with conn.execute("""
                SELECT t.*, p.status, p.result, p.error 
                FROM transcript_chunks t 
                JOIN summary_processes p ON t.meeting_id = p.meeting_id 
                WHERE t.meeting_id = ?
            """, (meeting_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(zip([col[0] for col in cursor.description], row))
                return None

    async def save_meeting(self, meeting_id: str, title: str, folder_path: str = None):
        """Save or update a meeting"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check if meeting exists
                cursor.execute("SELECT id FROM meetings WHERE id = ? OR title = ?", (meeting_id, title))
                existing_meeting = cursor.fetchone()

                if not existing_meeting:
                    # Create new meeting with local timestamp and folder path
                    cursor.execute("""
                        INSERT INTO meetings (id, title, created_at, updated_at, folder_path)
                        VALUES (?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'), ?)
                    """, (meeting_id, title, folder_path))
                    logger.info(f"Saved meeting {meeting_id} with folder_path: {folder_path}")
                else:
                    # If we get here and meeting exists, throw error since we don't want duplicates
                    raise Exception(f"Meeting with ID {meeting_id} already exists")
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving meeting: {str(e)}")
            raise

    async def save_meeting_transcript(self, meeting_id: str, transcript: str, timestamp: str,
                                     summary: str = "", action_items: str = "", key_points: str = "",
                                     audio_start_time: float = None, audio_end_time: float = None, duration: float = None):
        """Save a transcript for a meeting with optional recording-relative timestamps"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Save transcript with NEW timestamp fields for playback sync
                cursor.execute("""
                    INSERT INTO transcripts (
                        meeting_id, transcript, timestamp, summary, action_items, key_points,
                        audio_start_time, audio_end_time, duration
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (meeting_id, transcript, timestamp, summary, action_items, key_points,
                      audio_start_time, audio_end_time, duration))

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving transcript: {str(e)}")
            raise

    async def get_meeting(self, meeting_id: str):
        """Get a meeting by ID with all its transcripts"""
        try:
            async with self._get_connection() as conn:
                # Get meeting details
                cursor = await conn.execute("""
                    SELECT id, title, created_at, updated_at
                    FROM meetings
                    WHERE id = ?
                """, (meeting_id,))
                meeting = await cursor.fetchone()
                
                if not meeting:
                    return None
                
                # Get all transcripts for this meeting with NEW timestamp fields
                cursor = await conn.execute("""
                    SELECT transcript, timestamp, audio_start_time, audio_end_time, duration
                    FROM transcripts
                    WHERE meeting_id = ?
                """, (meeting_id,))
                transcripts = await cursor.fetchall()

                return {
                    'id': meeting[0],
                    'title': meeting[1],
                    'created_at': meeting[2],
                    'updated_at': meeting[3],
                    'transcripts': [{
                        'id': meeting_id,
                        'text': transcript[0],
                        'timestamp': transcript[1],
                        # NEW: Recording-relative timestamps for playback sync
                        'audio_start_time': transcript[2],
                        'audio_end_time': transcript[3],
                        'duration': transcript[4]
                    } for transcript in transcripts]
                }
        except Exception as e:
            logger.error(f"Error getting meeting: {str(e)}")
            raise

    async def update_meeting_title(self, meeting_id: str, new_title: str):
        """Update a meeting's title"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            await conn.execute("""
                UPDATE meetings
                SET title = ?, updated_at = ?
                WHERE id = ?
            """, (new_title, now, meeting_id))
            await conn.commit()

    async def get_all_meetings(self):
        """Get all meetings with basic information"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, title, created_at
                FROM meetings
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            return [{
                'id': row[0],
                'title': row[1],
                'created_at': row[2]
            } for row in rows]

    async def delete_meeting(self, meeting_id: str):
        """Delete a meeting and all its associated data"""
        if not meeting_id or not meeting_id.strip():
            raise ValueError("meeting_id cannot be empty")
            
        try:
            async with self._get_connection() as conn:
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    # Check if meeting exists before deletion
                    cursor = await conn.execute("SELECT id FROM meetings WHERE id = ?", (meeting_id,))
                    meeting = await cursor.fetchone()
                    
                    if not meeting:
                        logger.warning(f"Meeting {meeting_id} not found for deletion")
                        await conn.rollback()
                        return False
                    
                    # Delete in proper order to respect foreign key constraints
                    # Delete from transcript_chunks
                    await conn.execute("DELETE FROM transcript_chunks WHERE meeting_id = ?", (meeting_id,))
                    
                    # Delete from summary_processes
                    await conn.execute("DELETE FROM summary_processes WHERE meeting_id = ?", (meeting_id,))
                    
                    # Delete from transcripts
                    await conn.execute("DELETE FROM transcripts WHERE meeting_id = ?", (meeting_id,))
                    
                    # Delete from meetings
                    cursor = await conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
                    
                    if cursor.rowcount == 0:
                        logger.error(f"Failed to delete meeting {meeting_id} - no rows affected")
                        await conn.rollback()
                        return False
                    
                    await conn.commit()
                    logger.info(f"Successfully deleted meeting {meeting_id} and all associated data")
                    return True
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Failed to delete meeting {meeting_id}: {str(e)}", exc_info=True)
                    return False
                    
        except Exception as e:
            logger.error(f"Database connection error in delete_meeting: {str(e)}", exc_info=True)
            return False

    async def get_model_config(self):
        """Get the current model configuration"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT provider, model, whisperModel FROM settings")
            row = await cursor.fetchone()
            return dict(zip([col[0] for col in cursor.description], row)) if row else None

    async def save_model_config(self, provider: str, model: str, whisperModel: str):
        """Save the model configuration"""
        # Input validation
        if not provider or not provider.strip():
            raise ValueError("Provider cannot be empty")
        if not model or not model.strip():
            raise ValueError("Model cannot be empty")
        if not whisperModel or not whisperModel.strip():
            raise ValueError("Whisper model cannot be empty")
            
        try:
            async with self._get_connection() as conn:
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    # Check if the configuration already exists
                    cursor = await conn.execute("SELECT id FROM settings")
                    existing_config = await cursor.fetchone()
                    if existing_config:
                        # Update existing configuration
                        await conn.execute("""
                            UPDATE settings 
                            SET provider = ?, model = ?, whisperModel = ?
                            WHERE id = '1'    
                        """, (provider, model, whisperModel))
                    else:
                        # Insert new configuration
                        await conn.execute("""
                            INSERT INTO settings (id, provider, model, whisperModel)
                            VALUES (?, ?, ?, ?)
                        """, ('1', provider, model, whisperModel))
                    
                    await conn.commit()
                    logger.info(f"Successfully saved model configuration: {provider}/{model}")
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Failed to save model configuration: {str(e)}", exc_info=True)
                    raise
                    
        except Exception as e:
            logger.error(f"Database connection error in save_model_config: {str(e)}", exc_info=True)
            raise


    async def save_api_key(self, api_key: str, provider: str):
        """Save the API key"""
        provider_list = ["openai", "claude", "groq", "ollama", "openrouter"]
        if provider not in provider_list:
            raise ValueError(f"Invalid provider: {provider}")
        if provider == "openai":
            api_key_name = "openaiApiKey"
        elif provider == "claude":
            api_key_name = "anthropicApiKey"
        elif provider == "groq":
            api_key_name = "groqApiKey"
        elif provider == "ollama":
            api_key_name = "ollamaApiKey"
        elif provider == "openrouter":
            api_key_name = "openRouterApiKey"
            
        try:
            async with self._get_connection() as conn:
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    # Check if settings row exists
                    cursor = await conn.execute("SELECT id FROM settings WHERE id = '1'")
                    existing_config = await cursor.fetchone()
                    
                    if existing_config:
                        # Update existing configuration
                        await conn.execute(f"UPDATE settings SET {api_key_name} = ? WHERE id = '1'", (api_key,))
                    else:
                        # Insert new configuration with default values and the API key
                        await conn.execute(f"""
                            INSERT INTO settings (id, provider, model, whisperModel, {api_key_name})
                            VALUES (?, ?, ?, ?, ?)
                        """, ('1', 'openai', 'gpt-4o-2024-11-20', 'large-v3', api_key))
                        
                    await conn.commit()
                    logger.info(f"Successfully saved API key for provider: {provider}")
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Failed to save API key for provider {provider}: {str(e)}", exc_info=True)
                    raise
                    
        except Exception as e:
            logger.error(f"Database connection error in save_api_key: {str(e)}", exc_info=True)
            raise

    async def get_api_key(self, provider: str):
        """Get the API key"""
        provider_list = ["openai", "claude", "groq", "ollama", "openrouter"]
        if provider not in provider_list:
            raise ValueError(f"Invalid provider: {provider}")
        if provider == "openai":
            api_key_name = "openaiApiKey"
        elif provider == "claude":
            api_key_name = "anthropicApiKey"
        elif provider == "groq":
            api_key_name = "groqApiKey"
        elif provider == "ollama":
            api_key_name = "ollamaApiKey"
        elif provider == "openrouter":
            api_key_name = "openRouterApiKey"
        async with self._get_connection() as conn:
            cursor = await conn.execute(f"SELECT {api_key_name} FROM settings WHERE id = '1'")
            row = await cursor.fetchone()
            return row[0] if row and row[0] else ""

    async def get_transcript_config(self):
        """Get the current transcript configuration"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT provider, model FROM transcript_settings")
            row = await cursor.fetchone()
            if row:
                return dict(zip([col[0] for col in cursor.description], row))
            else:
                # Return default configuration if no transcript settings exist
                return {
                    "provider": "localWhisper",
                    "model": "large-v3"
                }

    async def save_transcript_config(self, provider: str, model: str):
        """Save the transcript settings"""
        # Input validation
        if not provider or not provider.strip():
            raise ValueError("Provider cannot be empty")
        if not model or not model.strip():
            raise ValueError("Model cannot be empty")
            
        try:
            async with self._get_connection() as conn:
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    # Check if the configuration already exists
                    cursor = await conn.execute("SELECT id FROM transcript_settings")
                    existing_config = await cursor.fetchone()
                    if existing_config:
                        # Update existing configuration
                        await conn.execute("""
                            UPDATE transcript_settings 
                            SET provider = ?, model = ?
                            WHERE id = '1'
                        """, (provider, model))
                    else:
                        # Insert new configuration
                        await conn.execute("""
                            INSERT INTO transcript_settings (id, provider, model)
                            VALUES (?, ?, ?)
                        """, ('1', provider, model))
                    
                    await conn.commit()
                    logger.info(f"Successfully saved transcript configuration: {provider}/{model}")
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Failed to save transcript configuration: {str(e)}", exc_info=True)
                    raise
                    
        except Exception as e:
            logger.error(f"Database connection error in save_transcript_config: {str(e)}", exc_info=True)
            raise

    async def save_transcript_api_key(self, api_key: str, provider: str):
        """Save the transcript API key"""
        provider_list = ["localWhisper","deepgram","elevenLabs","groq","openai"]
        if provider not in provider_list:
            raise ValueError(f"Invalid provider: {provider}")
        if provider == "localWhisper":
            api_key_name = "whisperApiKey"
        elif provider == "deepgram":
            api_key_name = "deepgramApiKey"
        elif provider == "elevenLabs":
            api_key_name = "elevenLabsApiKey"
        elif provider == "groq":
            api_key_name = "groqApiKey"
        elif provider == "openai":
            api_key_name = "openaiApiKey"
            
        try:
            async with self._get_connection() as conn:
                await conn.execute("BEGIN TRANSACTION")
                
                try:
                    # Check if transcript settings row exists
                    cursor = await conn.execute("SELECT id FROM transcript_settings WHERE id = '1'")
                    existing_config = await cursor.fetchone()
                    
                    if existing_config:
                        # Update existing configuration
                        await conn.execute(f"UPDATE transcript_settings SET {api_key_name} = ? WHERE id = '1'", (api_key,))
                    else:
                        # Insert new configuration with default values and the API key
                        await conn.execute(f"""
                            INSERT INTO transcript_settings (id, provider, model, {api_key_name})
                            VALUES (?, ?, ?, ?)
                        """, ('1', 'localWhisper', 'large-v3', api_key))
                        
                    await conn.commit()
                    logger.info(f"Successfully saved transcript API key for provider: {provider}")
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Failed to save transcript API key for provider {provider}: {str(e)}", exc_info=True)
                    raise
                    
        except Exception as e:
            logger.error(f"Database connection error in save_transcript_api_key: {str(e)}", exc_info=True)
            raise


    async def get_transcript_api_key(self, provider: str):
        """Get the transcript API key"""
        provider_list = ["localWhisper","deepgram","elevenLabs","groq","openai"]
        if provider not in provider_list:
            raise ValueError(f"Invalid provider: {provider}")
        if provider == "localWhisper":
            api_key_name = "whisperApiKey"
        elif provider == "deepgram":
            api_key_name = "deepgramApiKey"
        elif provider == "elevenLabs":
            api_key_name = "elevenLabsApiKey"
        elif provider == "groq":
            api_key_name = "groqApiKey"
        elif provider == "openai":
            api_key_name = "openaiApiKey"
        async with self._get_connection() as conn:
            cursor = await conn.execute(f"SELECT {api_key_name} FROM transcript_settings WHERE id = '1'")
            row = await cursor.fetchone()
            return row[0] if row and row[0] else ""

    async def search_transcripts(self, query: str):
        """Search through meeting transcripts for the given query"""
        if not query or query.strip() == "":
            return []
            
        # Convert query to lowercase for case-insensitive search
        search_query = f"%{query.lower()}%"
        
        try:
            async with self._get_connection() as conn:
                # Search in transcripts table
                cursor = await conn.execute("""
                    SELECT m.id, m.title, t.transcript, t.timestamp
                    FROM meetings m
                    JOIN transcripts t ON m.id = t.meeting_id
                    WHERE LOWER(t.transcript) LIKE ?
                    ORDER BY m.created_at DESC
                """, (search_query,))
                
                rows = await cursor.fetchall()
                
                # Also search in transcript_chunks for full transcripts
                cursor2 = await conn.execute("""
                    SELECT m.id, m.title, tc.transcript_text
                    FROM meetings m
                    JOIN transcript_chunks tc ON m.id = tc.meeting_id
                    WHERE LOWER(tc.transcript_text) LIKE ?
                    AND m.id NOT IN (SELECT DISTINCT meeting_id FROM transcripts WHERE LOWER(transcript) LIKE ?)
                    ORDER BY m.created_at DESC
                """, (search_query, search_query))
                
                chunk_rows = await cursor2.fetchall()
                
                # Format the results
                results = []
                
                # Process transcript matches
                for row in rows:
                    meeting_id, title, transcript, timestamp = row
                    
                    # Find the matching context (snippet around the match)
                    transcript_lower = transcript.lower()
                    match_index = transcript_lower.find(query.lower())
                    
                    # Extract context around the match (100 chars before and after)
                    start_index = max(0, match_index - 100)
                    end_index = min(len(transcript), match_index + len(query) + 100)
                    context = transcript[start_index:end_index]
                    
                    # Add ellipsis if we truncated the text
                    if start_index > 0:
                        context = "..." + context
                    if end_index < len(transcript):
                        context += "..."
                    
                    results.append({
                        'id': meeting_id,
                        'title': title,
                        'matchContext': context,
                        'timestamp': timestamp
                    })
                
                # Process transcript_chunks matches
                for row in chunk_rows:
                    meeting_id, title, transcript_text = row
                    
                    # Find the matching context (snippet around the match)
                    transcript_lower = transcript_text.lower()
                    match_index = transcript_lower.find(query.lower())
                    
                    # Extract context around the match (100 chars before and after)
                    start_index = max(0, match_index - 100)
                    end_index = min(len(transcript_text), match_index + len(query) + 100)
                    context = transcript_text[start_index:end_index]
                    
                    # Add ellipsis if we truncated the text
                    if start_index > 0:
                        context = "..." + context
                    if end_index < len(transcript_text):
                        context += "..."
                    
                    results.append({
                        'id': meeting_id,
                        'title': title,
                        'matchContext': context,
                        'timestamp': datetime.utcnow().isoformat()  # Use current time as fallback
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Error searching transcripts: {str(e)}")
            raise
        
    async def delete_api_key(self, provider: str):
        """Delete the API key"""
        provider_list = ["openai", "claude", "groq", "ollama"]
        if provider not in provider_list:
            raise ValueError(f"Invalid provider: {provider}")
        if provider == "openai":
            api_key_name = "openaiApiKey"
        elif provider == "claude":
            api_key_name = "anthropicApiKey"
        elif provider == "groq":
            api_key_name = "groqApiKey"
        elif provider == "ollama":
            api_key_name = "ollamaApiKey"
        async with self._get_connection() as conn:
            await conn.execute(f"UPDATE settings SET {api_key_name} = NULL WHERE id = '1'")
            await conn.commit()
    
    async def update_meeting_summary(self, meeting_id: str, summary: dict):
        """Update a meeting's summary"""
        now = datetime.utcnow().isoformat()
        try:
            async with self._get_connection() as conn:
                # Check if the meeting exists
                cursor = await conn.execute("SELECT id FROM meetings WHERE id = ?", (meeting_id,))
                meeting = await cursor.fetchone()
                
                if not meeting:
                    raise ValueError(f"Meeting with ID {meeting_id} not found")
                
                # Update the summary in the summary_processes table
                await conn.execute("""
                    UPDATE summary_processes
                    SET result = ?, updated_at = ?
                    WHERE meeting_id = ?
                """, (json.dumps(summary), now, meeting_id))
                
                # Update the meeting's updated_at timestamp
                await conn.execute("""
                    UPDATE meetings
                    SET updated_at = ?
                    WHERE id = ?
                """, (now, meeting_id))
                
                await conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating meeting summary: {str(e)}")
            raise

    # ==================== SUMMARY TEMPLATES ====================

    async def get_all_templates(self):
        """Get all summary templates"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, name, description, schema_json, prompt_template,
                       is_default, is_preset, created_at, updated_at
                FROM summary_templates
                ORDER BY is_preset DESC, name ASC
            """)
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def get_template_by_id(self, template_id: str):
        """Get a specific template by ID"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, name, description, schema_json, prompt_template,
                       is_default, is_preset, created_at, updated_at
                FROM summary_templates WHERE id = ?
            """, (template_id,))
            row = await cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
            return None

    async def get_default_template(self):
        """Get the default template"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, name, description, schema_json, prompt_template,
                       is_default, is_preset, created_at, updated_at
                FROM summary_templates WHERE is_default = 1
            """)
            row = await cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
            return None

    async def create_template(self, template_data: dict) -> str:
        """Create a new summary template"""
        import uuid
        template_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT INTO summary_templates
                (id, name, description, schema_json, prompt_template, is_default, is_preset, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template_id,
                template_data.get('name', 'Untitled Template'),
                template_data.get('description', ''),
                json.dumps(template_data.get('schema', {})),
                template_data.get('prompt_template', ''),
                0,  # is_default
                template_data.get('is_preset', 0),
                now,
                now
            ))
            await conn.commit()
            logger.info(f"Created template: {template_id}")
            return template_id

    async def update_template(self, template_id: str, template_data: dict) -> bool:
        """Update an existing template"""
        now = datetime.utcnow().isoformat()

        async with self._get_connection() as conn:
            # Check if template exists and is not a preset
            cursor = await conn.execute(
                "SELECT is_preset FROM summary_templates WHERE id = ?",
                (template_id,)
            )
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Template not found: {template_id}")
            if row[0] == 1:
                raise ValueError("Cannot modify preset templates")

            await conn.execute("""
                UPDATE summary_templates
                SET name = ?, description = ?, schema_json = ?, prompt_template = ?, updated_at = ?
                WHERE id = ?
            """, (
                template_data.get('name'),
                template_data.get('description', ''),
                json.dumps(template_data.get('schema', {})),
                template_data.get('prompt_template', ''),
                now,
                template_id
            ))
            await conn.commit()
            logger.info(f"Updated template: {template_id}")
            return True

    async def delete_template(self, template_id: str) -> bool:
        """Delete a template"""
        async with self._get_connection() as conn:
            # Check if template exists and is not a preset
            cursor = await conn.execute(
                "SELECT is_preset, is_default FROM summary_templates WHERE id = ?",
                (template_id,)
            )
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Template not found: {template_id}")
            if row[0] == 1:
                raise ValueError("Cannot delete preset templates")
            if row[1] == 1:
                raise ValueError("Cannot delete the default template")

            await conn.execute("DELETE FROM summary_templates WHERE id = ?", (template_id,))
            await conn.commit()
            logger.info(f"Deleted template: {template_id}")
            return True

    async def set_default_template(self, template_id: str) -> bool:
        """Set a template as the default"""
        async with self._get_connection() as conn:
            # Check if template exists
            cursor = await conn.execute(
                "SELECT id FROM summary_templates WHERE id = ?",
                (template_id,)
            )
            if not await cursor.fetchone():
                raise ValueError(f"Template not found: {template_id}")

            # Unset current default
            await conn.execute("UPDATE summary_templates SET is_default = 0 WHERE is_default = 1")
            # Set new default
            await conn.execute("UPDATE summary_templates SET is_default = 1 WHERE id = ?", (template_id,))
            await conn.commit()
            logger.info(f"Set default template: {template_id}")
            return True

    async def initialize_preset_templates(self):
        """Initialize preset templates if they don't exist"""
        # Check if presets already exist
        async with self._get_connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM summary_templates WHERE is_preset = 1")
            count = (await cursor.fetchone())[0]
            if count > 0:
                return  # Presets already initialized

        presets = [
            {
                'name': 'Standard',
                'description': 'Comprehensive meeting summary with all key sections',
                'is_preset': 1,
                'schema': {
                    'sections': [
                        {'key': 'MeetingName', 'title': 'Meeting Name', 'type': 'text'},
                        {'key': 'People', 'title': 'People', 'type': 'list'},
                        {'key': 'SessionSummary', 'title': 'Session Summary', 'type': 'blocks'},
                        {'key': 'CriticalDeadlines', 'title': 'Critical Deadlines', 'type': 'blocks'},
                        {'key': 'KeyItemsDecisions', 'title': 'Key Items & Decisions', 'type': 'blocks'},
                        {'key': 'ImmediateActionItems', 'title': 'Immediate Action Items', 'type': 'blocks'},
                        {'key': 'NextSteps', 'title': 'Next Steps', 'type': 'blocks'},
                        {'key': 'MeetingNotes', 'title': 'Meeting Notes', 'type': 'notes'}
                    ]
                },
                'prompt_template': ''
            },
            {
                'name': 'Action-Focused',
                'description': 'Emphasizes decisions, action items, and deadlines',
                'is_preset': 1,
                'schema': {
                    'sections': [
                        {'key': 'MeetingName', 'title': 'Meeting Name', 'type': 'text'},
                        {'key': 'KeyDecisions', 'title': 'Key Decisions Made', 'type': 'blocks'},
                        {'key': 'ActionItems', 'title': 'Action Items', 'type': 'blocks'},
                        {'key': 'Deadlines', 'title': 'Deadlines & Due Dates', 'type': 'blocks'},
                        {'key': 'Owners', 'title': 'Task Owners', 'type': 'blocks'},
                        {'key': 'Blockers', 'title': 'Blockers & Risks', 'type': 'blocks'}
                    ]
                },
                'prompt_template': 'Focus primarily on extracting actionable items, decisions, owners, and deadlines from this meeting.'
            },
            {
                'name': 'Brief',
                'description': 'Executive summary in 1-2 paragraphs',
                'is_preset': 1,
                'schema': {
                    'sections': [
                        {'key': 'MeetingName', 'title': 'Meeting Name', 'type': 'text'},
                        {'key': 'ExecutiveSummary', 'title': 'Executive Summary', 'type': 'blocks'},
                        {'key': 'KeyTakeaways', 'title': 'Key Takeaways', 'type': 'blocks'}
                    ]
                },
                'prompt_template': 'Provide a brief, executive-level summary in 1-2 paragraphs. Focus only on the most important points.'
            },
            {
                'name': 'Technical',
                'description': 'Detailed technical discussions and architecture notes',
                'is_preset': 1,
                'schema': {
                    'sections': [
                        {'key': 'MeetingName', 'title': 'Meeting Name', 'type': 'text'},
                        {'key': 'TechnicalDiscussion', 'title': 'Technical Discussion', 'type': 'blocks'},
                        {'key': 'ArchitectureDecisions', 'title': 'Architecture Decisions', 'type': 'blocks'},
                        {'key': 'CodeChanges', 'title': 'Code/Implementation Changes', 'type': 'blocks'},
                        {'key': 'TechnicalDebt', 'title': 'Technical Debt', 'type': 'blocks'},
                        {'key': 'Dependencies', 'title': 'Dependencies & Integrations', 'type': 'blocks'},
                        {'key': 'ActionItems', 'title': 'Technical Action Items', 'type': 'blocks'}
                    ]
                },
                'prompt_template': 'Focus on technical details, architecture decisions, code changes, and implementation specifics.'
            },
            {
                'name': 'Sales/Customer',
                'description': 'Customer meeting notes with pain points and follow-ups',
                'is_preset': 1,
                'schema': {
                    'sections': [
                        {'key': 'MeetingName', 'title': 'Meeting Name', 'type': 'text'},
                        {'key': 'CustomerInfo', 'title': 'Customer/Prospect Info', 'type': 'blocks'},
                        {'key': 'PainPoints', 'title': 'Pain Points & Challenges', 'type': 'blocks'},
                        {'key': 'Requirements', 'title': 'Requirements & Needs', 'type': 'blocks'},
                        {'key': 'Objections', 'title': 'Objections & Concerns', 'type': 'blocks'},
                        {'key': 'Competitors', 'title': 'Competitor Mentions', 'type': 'blocks'},
                        {'key': 'NextSteps', 'title': 'Follow-up Actions', 'type': 'blocks'},
                        {'key': 'DealStatus', 'title': 'Deal Status/Notes', 'type': 'blocks'}
                    ]
                },
                'prompt_template': 'This is a customer/sales meeting. Focus on customer pain points, requirements, objections, and follow-up actions.'
            }
        ]

        # Create presets
        for preset in presets:
            template_id = await self.create_template(preset)
            # Set Standard as default
            if preset['name'] == 'Standard':
                await self.set_default_template(template_id)

        logger.info(f"Initialized {len(presets)} preset templates")

    # ==================== CHAT CONVERSATIONS ====================

    async def create_conversation(self, meeting_id: str, title: str = None) -> str:
        """Create a new chat conversation for a meeting"""
        import uuid
        conversation_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT INTO chat_conversations (id, meeting_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation_id, meeting_id, title or f"Chat {now[:10]}", now, now))
            await conn.commit()
            logger.info(f"Created conversation: {conversation_id} for meeting: {meeting_id}")
            return conversation_id

    async def get_conversations_for_meeting(self, meeting_id: str):
        """Get all conversations for a meeting"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, meeting_id, title, created_at, updated_at
                FROM chat_conversations
                WHERE meeting_id = ?
                ORDER BY updated_at DESC
            """, (meeting_id,))
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def get_conversation_by_id(self, conversation_id: str):
        """Get a specific conversation"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, meeting_id, title, created_at, updated_at
                FROM chat_conversations WHERE id = ?
            """, (conversation_id,))
            row = await cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
            return None

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and its messages"""
        async with self._get_connection() as conn:
            # Messages are deleted via CASCADE
            result = await conn.execute(
                "DELETE FROM chat_conversations WHERE id = ?",
                (conversation_id,)
            )
            await conn.commit()
            return result.rowcount > 0

    async def save_chat_message(self, conversation_id: str, role: str, content: str, context_chunks: list = None) -> str:
        """Save a chat message"""
        import uuid
        message_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT INTO chat_messages (id, conversation_id, role, content, context_chunks, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                message_id,
                conversation_id,
                role,
                content,
                json.dumps(context_chunks) if context_chunks else None,
                now
            ))
            # Update conversation's updated_at
            await conn.execute("""
                UPDATE chat_conversations SET updated_at = ? WHERE id = ?
            """, (now, conversation_id))
            await conn.commit()
            return message_id

    async def get_conversation_messages(self, conversation_id: str):
        """Get all messages for a conversation"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, conversation_id, role, content, context_chunks, created_at
                FROM chat_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            """, (conversation_id,))
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            messages = []
            for row in rows:
                msg = dict(zip(columns, row))
                if msg.get('context_chunks'):
                    msg['context_chunks'] = json.loads(msg['context_chunks'])
                messages.append(msg)
            return messages

    async def get_meeting_transcript_text(self, meeting_id: str) -> str:
        """Get the full transcript text for a meeting (for chat context)"""
        async with self._get_connection() as conn:
            # First try transcript_chunks table
            cursor = await conn.execute("""
                SELECT transcript_text FROM transcript_chunks WHERE meeting_id = ?
            """, (meeting_id,))
            row = await cursor.fetchone()
            if row and row[0]:
                return row[0]

            # Fallback to concatenating transcripts table
            cursor = await conn.execute("""
                SELECT transcript FROM transcripts WHERE meeting_id = ? ORDER BY timestamp ASC
            """, (meeting_id,))
            rows = await cursor.fetchall()
            if rows:
                return "\n".join(row[0] for row in rows if row[0])
            return ""

    # Aliases for API compatibility
    async def create_chat_conversation(self, meeting_id: str, title: str = None) -> str:
        """Alias for create_conversation"""
        return await self.create_conversation(meeting_id, title)

    async def get_chat_conversations(self, meeting_id: str):
        """Alias for get_conversations_for_meeting"""
        return await self.get_conversations_for_meeting(meeting_id)

    async def add_chat_message(self, conversation_id: str, role: str, content: str, context_chunks: list = None) -> str:
        """Alias for save_chat_message"""
        return await self.save_chat_message(conversation_id, role, content, context_chunks)

    async def get_chat_messages(self, conversation_id: str):
        """Alias for get_conversation_messages"""
        return await self.get_conversation_messages(conversation_id)

    async def delete_chat_conversation(self, conversation_id: str) -> bool:
        """Alias for delete_conversation"""
        return await self.delete_conversation(conversation_id)

    # ==================== SPEAKER IDENTIFICATION ====================

    async def create_speaker(self, meeting_id: str, label: str, color: str = None) -> str:
        """Create a new speaker for a meeting"""
        import uuid
        speaker_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT INTO speakers (id, meeting_id, label, color, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (speaker_id, meeting_id, label, color, now))
            await conn.commit()
            logger.info(f"Created speaker: {speaker_id} for meeting: {meeting_id}")
            return speaker_id

    async def get_speakers_for_meeting(self, meeting_id: str):
        """Get all speakers for a meeting"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, meeting_id, label, color, created_at
                FROM speakers
                WHERE meeting_id = ?
                ORDER BY label ASC
            """, (meeting_id,))
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def update_speaker(self, speaker_id: str, label: str = None, color: str = None) -> bool:
        """Update a speaker's label or color"""
        async with self._get_connection() as conn:
            updates = []
            params = []
            if label is not None:
                updates.append("label = ?")
                params.append(label)
            if color is not None:
                updates.append("color = ?")
                params.append(color)

            if not updates:
                return False

            params.append(speaker_id)
            result = await conn.execute(
                f"UPDATE speakers SET {', '.join(updates)} WHERE id = ?",
                params
            )
            await conn.commit()
            return result.rowcount > 0

    async def delete_speaker(self, speaker_id: str) -> bool:
        """Delete a speaker"""
        async with self._get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM speakers WHERE id = ?",
                (speaker_id,)
            )
            await conn.commit()
            return result.rowcount > 0

    async def assign_speaker_to_transcript(self, transcript_id: str, speaker_id: str, speaker_label: str = None):
        """Assign a speaker to a transcript segment"""
        async with self._get_connection() as conn:
            await conn.execute("""
                UPDATE transcripts
                SET speaker_id = ?, speaker_label = ?
                WHERE id = ?
            """, (speaker_id, speaker_label, transcript_id))
            await conn.commit()

    async def update_speaker_label_on_transcripts(self, speaker_id: str, new_label: str):
        """Update the speaker label on all transcripts that have this speaker assigned"""
        async with self._get_connection() as conn:
            await conn.execute("""
                UPDATE transcripts
                SET speaker_label = ?
                WHERE speaker_id = ?
            """, (new_label, speaker_id))
            await conn.commit()

    async def get_diarization_status(self, meeting_id: str):
        """Get the diarization status for a meeting"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT status, error, created_at, updated_at
                FROM diarization_processes
                WHERE meeting_id = ?
            """, (meeting_id,))
            row = await cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
            return None

    async def create_diarization_process(self, meeting_id: str) -> str:
        """Create a new diarization process"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO diarization_processes (meeting_id, status, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            """, (meeting_id, "pending", now, now))
            await conn.commit()
            return meeting_id

    async def update_diarization_process(self, meeting_id: str, status: str, error: str = None):
        """Update a diarization process status"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            await conn.execute("""
                UPDATE diarization_processes
                SET status = ?, error = ?, updated_at = ?
                WHERE meeting_id = ?
            """, (status, error, now, meeting_id))
            await conn.commit()

    # ==================== CALENDAR INTEGRATION ====================

    async def create_calendar_account(self, provider: str, email: str, access_token: str,
                                      refresh_token: str, token_expires_at: str) -> str:
        """Create a new calendar account"""
        import uuid
        account_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT INTO calendar_accounts (id, provider, email, access_token, refresh_token, token_expires_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (account_id, provider, email, access_token, refresh_token, token_expires_at, now, now))
            await conn.commit()
            logger.info(f"Created calendar account: {account_id} for email: {email}")
            return account_id

    async def get_calendar_accounts(self):
        """Get all calendar accounts"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, provider, email, token_expires_at, created_at, updated_at
                FROM calendar_accounts
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def get_calendar_account_by_id(self, account_id: str):
        """Get a calendar account by ID (includes tokens for internal use)"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, provider, email, access_token, refresh_token, token_expires_at, created_at, updated_at
                FROM calendar_accounts WHERE id = ?
            """, (account_id,))
            row = await cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, row))
            return None

    async def update_calendar_account_tokens(self, account_id: str, access_token: str,
                                            refresh_token: str = None, token_expires_at: str = None):
        """Update calendar account tokens"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            updates = ["access_token = ?", "updated_at = ?"]
            params = [access_token, now]

            if refresh_token:
                updates.append("refresh_token = ?")
                params.append(refresh_token)
            if token_expires_at:
                updates.append("token_expires_at = ?")
                params.append(token_expires_at)

            params.append(account_id)
            await conn.execute(
                f"UPDATE calendar_accounts SET {', '.join(updates)} WHERE id = ?",
                params
            )
            await conn.commit()

    async def delete_calendar_account(self, account_id: str) -> bool:
        """Delete a calendar account"""
        async with self._get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM calendar_accounts WHERE id = ?",
                (account_id,)
            )
            await conn.commit()
            return result.rowcount > 0

    async def upsert_calendar_event(self, account_id: str, external_id: str, title: str,
                                    start_time: str, end_time: str, description: str = None,
                                    meeting_url: str = None, attendees: list = None) -> str:
        """Insert or update a calendar event"""
        import uuid
        now = datetime.utcnow().isoformat()

        async with self._get_connection() as conn:
            # Check if event exists
            cursor = await conn.execute(
                "SELECT id FROM calendar_events WHERE account_id = ? AND external_id = ?",
                (account_id, external_id)
            )
            existing = await cursor.fetchone()

            if existing:
                # Update existing event
                await conn.execute("""
                    UPDATE calendar_events
                    SET title = ?, description = ?, start_time = ?, end_time = ?,
                        meeting_url = ?, attendees = ?, updated_at = ?
                    WHERE id = ?
                """, (
                    title, description, start_time, end_time,
                    meeting_url, json.dumps(attendees) if attendees else None,
                    now, existing[0]
                ))
                await conn.commit()
                return existing[0]
            else:
                # Insert new event
                event_id = str(uuid.uuid4())
                await conn.execute("""
                    INSERT INTO calendar_events (id, account_id, external_id, title, description,
                                                start_time, end_time, meeting_url, attendees, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id, account_id, external_id, title, description,
                    start_time, end_time, meeting_url,
                    json.dumps(attendees) if attendees else None,
                    now, now
                ))
                await conn.commit()
                return event_id

    async def get_upcoming_events(self, limit: int = 10):
        """Get upcoming calendar events"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT e.id, e.account_id, e.external_id, e.title, e.description,
                       e.start_time, e.end_time, e.meeting_url, e.attendees, e.meeting_id,
                       a.email as account_email
                FROM calendar_events e
                JOIN calendar_accounts a ON e.account_id = a.id
                WHERE e.start_time >= ?
                ORDER BY e.start_time ASC
                LIMIT ?
            """, (now, limit))
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            events = []
            for row in rows:
                event = dict(zip(columns, row))
                if event.get('attendees'):
                    event['attendees'] = json.loads(event['attendees'])
                events.append(event)
            return events

    async def get_events_for_account(self, account_id: str, start_date: str = None, end_date: str = None):
        """Get events for a specific account"""
        async with self._get_connection() as conn:
            query = """
                SELECT id, account_id, external_id, title, description,
                       start_time, end_time, meeting_url, attendees, meeting_id
                FROM calendar_events
                WHERE account_id = ?
            """
            params = [account_id]

            if start_date:
                query += " AND start_time >= ?"
                params.append(start_date)
            if end_date:
                query += " AND end_time <= ?"
                params.append(end_date)

            query += " ORDER BY start_time ASC"

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            events = []
            for row in rows:
                event = dict(zip(columns, row))
                if event.get('attendees'):
                    event['attendees'] = json.loads(event['attendees'])
                events.append(event)
            return events

    async def link_event_to_meeting(self, event_id: str, meeting_id: str):
        """Link a calendar event to a meeting recording"""
        now = datetime.utcnow().isoformat()
        async with self._get_connection() as conn:
            await conn.execute("""
                UPDATE calendar_events SET meeting_id = ?, updated_at = ? WHERE id = ?
            """, (meeting_id, now, event_id))
            await conn.commit()

    async def delete_calendar_event(self, event_id: str) -> bool:
        """Delete a calendar event"""
        async with self._get_connection() as conn:
            result = await conn.execute(
                "DELETE FROM calendar_events WHERE id = ?",
                (event_id,)
            )
            await conn.commit()
            return result.rowcount > 0

    # ==================== AUTO-JOIN SETTINGS ====================

    async def get_auto_join_settings(self):
        """Get auto-join settings"""
        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT id, enabled, auto_record, reminder_minutes, supported_platforms
                FROM auto_join_settings WHERE id = '1'
            """)
            row = await cursor.fetchone()
            if row:
                columns = [col[0] for col in cursor.description]
                settings = dict(zip(columns, row))
                if settings.get('supported_platforms'):
                    settings['supported_platforms'] = json.loads(settings['supported_platforms'])
                return settings
            return {
                'enabled': False,
                'auto_record': True,
                'reminder_minutes': 5,
                'supported_platforms': ['zoom', 'teams', 'meet']
            }

    async def update_auto_join_settings(self, enabled: bool = None, auto_record: bool = None,
                                       reminder_minutes: int = None, supported_platforms: list = None):
        """Update auto-join settings"""
        async with self._get_connection() as conn:
            updates = []
            params = []

            if enabled is not None:
                updates.append("enabled = ?")
                params.append(1 if enabled else 0)
            if auto_record is not None:
                updates.append("auto_record = ?")
                params.append(1 if auto_record else 0)
            if reminder_minutes is not None:
                updates.append("reminder_minutes = ?")
                params.append(reminder_minutes)
            if supported_platforms is not None:
                updates.append("supported_platforms = ?")
                params.append(json.dumps(supported_platforms))

            if updates:
                params.append('1')
                await conn.execute(
                    f"UPDATE auto_join_settings SET {', '.join(updates)} WHERE id = ?",
                    params
                )
                await conn.commit()

    async def log_meeting_join(self, event_id: str, action: str) -> str:
        """Log a meeting join action"""
        import uuid
        log_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        async with self._get_connection() as conn:
            await conn.execute("""
                INSERT INTO meeting_join_log (id, event_id, action, timestamp)
                VALUES (?, ?, ?, ?)
            """, (log_id, event_id, action, now))
            await conn.commit()
            return log_id

    async def get_upcoming_auto_join_candidates(self, minutes_ahead: int = 30):
        """Get upcoming events that are candidates for auto-join"""
        now = datetime.utcnow()
        cutoff = (now + timedelta(minutes=minutes_ahead)).isoformat()

        async with self._get_connection() as conn:
            cursor = await conn.execute("""
                SELECT e.id, e.title, e.start_time, e.end_time, e.meeting_url,
                       a.email as account_email
                FROM calendar_events e
                JOIN calendar_accounts a ON e.account_id = a.id
                WHERE e.start_time >= ? AND e.start_time <= ? AND e.meeting_url IS NOT NULL
                ORDER BY e.start_time ASC
            """, (now.isoformat(), cutoff))
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def get_meeting_join_log(self, event_id: str = None, limit: int = 50):
        """Get meeting join logs"""
        async with self._get_connection() as conn:
            if event_id:
                cursor = await conn.execute("""
                    SELECT id, event_id, action, timestamp
                    FROM meeting_join_log
                    WHERE event_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (event_id, limit))
            else:
                cursor = await conn.execute("""
                    SELECT id, event_id, action, timestamp
                    FROM meeting_join_log
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]



