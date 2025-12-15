from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from typing import Optional, List
import logging
from dotenv import load_dotenv
from db import DatabaseManager
import json
from threading import Lock
from transcript_processor import TranscriptProcessor
from chat_processor import ChatProcessor
import time

# Load environment variables
load_dotenv()

# Configure logger with line numbers and function names
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler with formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create formatter with line numbers and function names
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d - %(funcName)s()] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)

# Add handler to logger if not already added
if not logger.handlers:
    logger.addHandler(console_handler)

app = FastAPI(
    title="Meeting Summarizer API",
    description="API for processing and summarizing meeting transcripts",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],     # Allow all methods
    allow_headers=["*"],     # Allow all headers
    max_age=3600,            # Cache preflight requests for 1 hour
)

# Global database manager instance for meeting management endpoints
db = DatabaseManager()

# Initialize chat processor
chat_processor = ChatProcessor(db)

# New Pydantic models for meeting management
class Transcript(BaseModel):
    id: str
    text: str
    timestamp: str
    # Recording-relative timestamps for audio-transcript synchronization
    audio_start_time: Optional[float] = None
    audio_end_time: Optional[float] = None
    duration: Optional[float] = None

class MeetingResponse(BaseModel):
    id: str
    title: str

class MeetingDetailsResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    transcripts: List[Transcript]

class MeetingTitleUpdate(BaseModel):
    meeting_id: str
    title: str

class DeleteMeetingRequest(BaseModel):
    meeting_id: str

class SaveTranscriptRequest(BaseModel):
    meeting_title: str
    transcripts: List[Transcript]
    folder_path: Optional[str] = None  # NEW: Path to meeting folder (for new folder structure)

class SaveModelConfigRequest(BaseModel):
    provider: str
    model: str
    whisperModel: str
    apiKey: Optional[str] = None

class SaveTranscriptConfigRequest(BaseModel):
    provider: str
    model: str
    apiKey: Optional[str] = None

class TranscriptRequest(BaseModel):
    """Request model for transcript text, updated with meeting_id"""
    text: str
    model: str
    model_name: str
    meeting_id: str
    chunk_size: Optional[int] = 5000
    overlap: Optional[int] = 1000
    custom_prompt: Optional[str] = "Generate a summary of the meeting transcript."

class SummaryProcessor:
    """Handles the processing of summaries in a thread-safe way"""
    def __init__(self):
        try:
            self.db = DatabaseManager()

            logger.info("Initializing SummaryProcessor components")
            self.transcript_processor = TranscriptProcessor()
            logger.info("SummaryProcessor initialized successfully (core components)")
        except Exception as e:
            logger.error(f"Failed to initialize SummaryProcessor: {str(e)}", exc_info=True)
            raise

    async def process_transcript(self, text: str, model: str, model_name: str, chunk_size: int = 5000, overlap: int = 1000, custom_prompt: str = "Generate a summary of the meeting transcript.") -> tuple:
        """Process a transcript text"""
        try:
            if not text:
                raise ValueError("Empty transcript text provided")

            # Validate chunk_size and overlap
            if chunk_size <= 0:
                raise ValueError("chunk_size must be positive")
            if overlap < 0:
                raise ValueError("overlap must be non-negative")
            if overlap >= chunk_size:
                overlap = chunk_size - 1  # Ensure overlap is less than chunk_size

            # Ensure step size is positive
            step_size = chunk_size - overlap
            if step_size <= 0:
                chunk_size = overlap + 1  # Adjust chunk_size to ensure positive step

            logger.info(f"Processing transcript of length {len(text)} with chunk_size={chunk_size}, overlap={overlap}")
            num_chunks, all_json_data = await self.transcript_processor.process_transcript(
                text=text,
                model=model,
                model_name=model_name,
                chunk_size=chunk_size,
                overlap=overlap,
                custom_prompt=custom_prompt
            )
            logger.info(f"Successfully processed transcript into {num_chunks} chunks")

            return num_chunks, all_json_data
        except Exception as e:
            logger.error(f"Error processing transcript: {str(e)}", exc_info=True)
            raise

    def cleanup(self):
        """Cleanup resources"""
        try:
            logger.info("Cleaning up resources")
            if hasattr(self, 'transcript_processor'):
                self.transcript_processor.cleanup()
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)

# Initialize processor
processor = SummaryProcessor()

# New meeting management endpoints
@app.get("/get-meetings", response_model=List[MeetingResponse])
async def get_meetings():
    """Get all meetings with their basic information"""
    try:
        meetings = await db.get_all_meetings()
        return [{"id": meeting["id"], "title": meeting["title"]} for meeting in meetings]
    except Exception as e:
        logger.error(f"Error getting meetings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-meeting/{meeting_id}", response_model=MeetingDetailsResponse)
async def get_meeting(meeting_id: str):
    """Get a specific meeting by ID with all its details"""
    try:
        meeting = await db.get_meeting(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return meeting
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting meeting: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/save-meeting-title")
async def save_meeting_title(data: MeetingTitleUpdate):
    """Save a meeting title"""
    try:
        await db.update_meeting_title(data.meeting_id, data.title)
        return {"message": "Meeting title saved successfully"}
    except Exception as e:
        logger.error(f"Error saving meeting title: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete-meeting")
async def delete_meeting(data: DeleteMeetingRequest):
    """Delete a meeting and all its associated data"""
    try:
        success = await db.delete_meeting(data.meeting_id)
        if success:
            return {"message": "Meeting deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete meeting")
    except Exception as e:
        logger.error(f"Error deleting meeting: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def process_transcript_background(process_id: str, transcript: TranscriptRequest, custom_prompt: str):
    """Background task to process transcript"""
    try:
        logger.info(f"Starting background processing for process_id: {process_id}")
        
        # Early validation for common issues
        if not transcript.text or not transcript.text.strip():
            raise ValueError("Empty transcript text provided")
        
        if transcript.model in ["claude", "groq", "openai", "openrouter"]:
            # Check if API key is available for cloud providers
            api_key = await processor.db.get_api_key(transcript.model)
            if not api_key:
                provider_names = {"claude": "Anthropic", "groq": "Groq", "openai": "OpenAI", "openrouter": "OpenRouter"}
                raise ValueError(f"{provider_names.get(transcript.model, transcript.model)} API key not configured. Please set your API key in the model settings.")

        _, all_json_data = await processor.process_transcript(
            text=transcript.text,
            model=transcript.model,
            model_name=transcript.model_name,
            chunk_size=transcript.chunk_size,
            overlap=transcript.overlap,
            custom_prompt=custom_prompt
        )

        # Create final summary structure by aggregating chunk results
        final_summary = {
            "MeetingName": "",
            "People": {"title": "People", "blocks": []},
            "SessionSummary": {"title": "Session Summary", "blocks": []},
            "CriticalDeadlines": {"title": "Critical Deadlines", "blocks": []},
            "KeyItemsDecisions": {"title": "Key Items & Decisions", "blocks": []},
            "ImmediateActionItems": {"title": "Immediate Action Items", "blocks": []},
            "NextSteps": {"title": "Next Steps", "blocks": []},
            # "OtherImportantPoints": {"title": "Other Important Points", "blocks": []},
            # "ClosingRemarks": {"title": "Closing Remarks", "blocks": []},
            "MeetingNotes": {
                "meeting_name": "",
                "sections": []
            }
        }

        # Process each chunk's data
        for json_str in all_json_data:
            try:
                json_dict = json.loads(json_str)
                if "MeetingName" in json_dict and json_dict["MeetingName"]:
                    final_summary["MeetingName"] = json_dict["MeetingName"]
                for key in final_summary:
                    if key == "MeetingNotes" and key in json_dict:
                        # Handle MeetingNotes sections
                        if isinstance(json_dict[key].get("sections"), list):
                            # Ensure each section has blocks array
                            for section in json_dict[key]["sections"]:
                                if not section.get("blocks"):
                                    section["blocks"] = []
                            final_summary[key]["sections"].extend(json_dict[key]["sections"])
                        if json_dict[key].get("meeting_name"):
                            final_summary[key]["meeting_name"] = json_dict[key]["meeting_name"]
                    elif key != "MeetingName" and key in json_dict and isinstance(json_dict[key], dict) and "blocks" in json_dict[key]:
                        if isinstance(json_dict[key]["blocks"], list):
                            final_summary[key]["blocks"].extend(json_dict[key]["blocks"])
                            # Also add as a new section in MeetingNotes if not already present
                            section_exists = False
                            for section in final_summary["MeetingNotes"]["sections"]:
                                if section["title"] == json_dict[key]["title"]:
                                    section["blocks"].extend(json_dict[key]["blocks"])
                                    section_exists = True
                                    break
                            
                            if not section_exists:
                                final_summary["MeetingNotes"]["sections"].append({
                                    "title": json_dict[key]["title"],
                                    "blocks": json_dict[key]["blocks"].copy() if json_dict[key]["blocks"] else []
                                })
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON chunk for {process_id}: {e}. Chunk: {json_str[:100]}...")
            except Exception as e:
                logger.error(f"Error processing chunk data for {process_id}: {e}. Chunk: {json_str[:100]}...")

        # Update database with meeting name using meeting_id
        if final_summary["MeetingName"]:
            await processor.db.update_meeting_name(transcript.meeting_id, final_summary["MeetingName"])

        # Save final result
        if all_json_data:
            await processor.db.update_process(process_id, status="completed", result=json.dumps(final_summary))
            logger.info(f"Background processing completed for process_id: {process_id}")
        else:
            error_msg = "Summary generation failed: No chunks were processed successfully. Check logs for specific errors."
            await processor.db.update_process(process_id, status="failed", error=error_msg)
            logger.error(f"Background processing failed for process_id: {process_id} - {error_msg}")

    except ValueError as e:
        # Handle specific value errors (like API key issues)
        error_msg = str(e)
        logger.error(f"Configuration error in background processing for {process_id}: {error_msg}", exc_info=True)
        try:
            await processor.db.update_process(process_id, status="failed", error=error_msg)
        except Exception as db_e:
            logger.error(f"Failed to update DB status to failed for {process_id}: {db_e}", exc_info=True)
    except Exception as e:
        # Handle all other exceptions
        error_msg = f"Processing error: {str(e)}"
        logger.error(f"Error in background processing for {process_id}: {error_msg}", exc_info=True)
        try:
            await processor.db.update_process(process_id, status="failed", error=error_msg)
        except Exception as db_e:
            logger.error(f"Failed to update DB status to failed for {process_id}: {db_e}", exc_info=True)

@app.post("/process-transcript")
async def process_transcript_api(
    transcript: TranscriptRequest,
    background_tasks: BackgroundTasks
):
    """Process a transcript text with background processing"""
    try:
        # Create new process linked to meeting_id
        process_id = await processor.db.create_process(transcript.meeting_id)

        # Save transcript data associated with meeting_id
        await processor.db.save_transcript(
            transcript.meeting_id,
            transcript.text,
            transcript.model,
            transcript.model_name,
            transcript.chunk_size,
            transcript.overlap
        )

        custom_prompt = transcript.custom_prompt

        # Start background processing
        background_tasks.add_task(
            process_transcript_background,
            process_id,
            transcript,
            custom_prompt
        )

        return JSONResponse({
            "message": "Processing started",
            "process_id": process_id
        })

    except Exception as e:
        logger.error(f"Error in process_transcript_api: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-summary/{meeting_id}")
async def get_summary(meeting_id: str):
    """Get the summary for a given meeting ID"""
    try:
        result = await processor.db.get_transcript_data(meeting_id)
        if not result:
            return JSONResponse(
                status_code=404,
                content={
                    "status": "error",
                    "meetingName": None,
                    "meeting_id": meeting_id,
                    "data": None,
                    "start": None,
                    "end": None,
                    "error": "Meeting ID not found"
                }
            )

        status = result.get("status", "unknown").lower()
        logger.debug(f"Summary status for meeting {meeting_id}: {status}, error: {result.get('error')}")

        # Parse result data if available
        summary_data = None
        if result.get("result"):
            try:
                parsed_result = json.loads(result["result"])
                if isinstance(parsed_result, str):
                    summary_data = json.loads(parsed_result)
                else:
                    summary_data = parsed_result
                if not isinstance(summary_data, dict):
                    logger.error(f"Parsed summary data is not a dictionary for meeting {meeting_id}")
                    summary_data = None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON data for meeting {meeting_id}: {str(e)}")
                status = "failed"
                result["error"] = f"Invalid summary data format: {str(e)}"
            except Exception as e:
                logger.error(f"Unexpected error parsing summary data for {meeting_id}: {str(e)}")
                status = "failed"
                result["error"] = f"Error processing summary data: {str(e)}"

        # Transform summary data into frontend format if available - PRESERVE ORDER
        transformed_data = {}
        if isinstance(summary_data, dict) and status == "completed":
            # Add MeetingName to transformed data
            transformed_data["MeetingName"] = summary_data.get("MeetingName", "")

            # Map backend sections to frontend sections
            section_mapping = {
                # "SessionSummary": "key_points",
                # "ImmediateActionItems": "action_items",
                # "KeyItemsDecisions": "decisions",
                # "NextSteps": "next_steps",
                # "CriticalDeadlines": "critical_deadlines",
                # "People": "people"
            }

            # Add each section to transformed data
            for backend_key, frontend_key in section_mapping.items():
                if backend_key in summary_data and isinstance(summary_data[backend_key], dict):
                    transformed_data[frontend_key] = summary_data[backend_key]
            
            # Add meeting notes sections if available - PRESERVE ORDER AND HANDLE DUPLICATES
            if "MeetingNotes" in summary_data and isinstance(summary_data["MeetingNotes"], dict):
                meeting_notes = summary_data["MeetingNotes"]
                if isinstance(meeting_notes.get("sections"), list):
                    # Add section order array to maintain order
                    transformed_data["_section_order"] = []
                    used_keys = set()
                    
                    for index, section in enumerate(meeting_notes["sections"]):
                        if isinstance(section, dict) and "title" in section and "blocks" in section:
                            # Ensure blocks is a list to prevent frontend errors
                            if not isinstance(section.get("blocks"), list):
                                section["blocks"] = []
                                
                            # Convert title to snake_case key
                            base_key = section["title"].lower().replace(" & ", "_").replace(" ", "_")
                            
                            # Handle duplicate section names by adding index
                            key = base_key
                            if key in used_keys:
                                key = f"{base_key}_{index}"
                            
                            used_keys.add(key)
                            transformed_data[key] = section
                            # Only add to _section_order if the section was successfully added
                            transformed_data["_section_order"].append(key)

        response = {
            "status": "processing" if status in ["processing", "pending", "started"] else status,
            "meetingName": summary_data.get("MeetingName") if isinstance(summary_data, dict) else None,
            "meeting_id": meeting_id,
            "start": result.get("start_time"),
            "end": result.get("end_time"),
            "data": transformed_data if status == "completed" else None
        }

        if status == "failed":
            response["status"] = "error"
            response["error"] = result.get("error", "Unknown processing error")
            response["data"] = None
            response["meetingName"] = None
            logger.info(f"Returning failed status with error: {response['error']}")
            return JSONResponse(status_code=400, content=response)

        elif status in ["processing", "pending", "started"]:
            response["data"] = None
            return JSONResponse(status_code=202, content=response)

        elif status == "completed":
            if not summary_data:
                response["status"] = "error"
                response["error"] = "Completed but summary data is missing or invalid"
                response["data"] = None
                response["meetingName"] = None
                return JSONResponse(status_code=500, content=response)
            return JSONResponse(status_code=200, content=response)

        else:
            response["status"] = "error"
            response["error"] = f"Unknown or unexpected status: {status}"
            response["data"] = None
            response["meetingName"] = None
            return JSONResponse(status_code=500, content=response)

    except Exception as e:
        logger.error(f"Error getting summary for {meeting_id}: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "meetingName": None,
                "meeting_id": meeting_id,
                "data": None,
                "start": None,
                "end": None,
                "error": f"Internal server error: {str(e)}"
            }
        )

@app.post("/save-transcript")
async def save_transcript(request: SaveTranscriptRequest):
    """Save transcript segments for a meeting without processing"""
    try:
        logger.info(f"Received save-transcript request for meeting: {request.meeting_title}")
        logger.info(f"Number of transcripts to save: {len(request.transcripts)}")

        # Log first transcript timestamps for debugging
        if request.transcripts:
            first = request.transcripts[0]
            logger.debug(f"First transcript: audio_start_time={first.audio_start_time}, audio_end_time={first.audio_end_time}, duration={first.duration}")

        # Generate a unique meeting ID
        meeting_id = f"meeting-{int(time.time() * 1000)}"

        # Save the meeting with folder path (if provided)
        await db.save_meeting(meeting_id, request.meeting_title, folder_path=request.folder_path)

        # Save each transcript segment with NEW timestamp fields for playback sync
        for transcript in request.transcripts:
            await db.save_meeting_transcript(
                meeting_id=meeting_id,
                transcript=transcript.text,
                timestamp=transcript.timestamp,
                summary="",
                action_items="",
                key_points="",
                # NEW: Recording-relative timestamps for audio-transcript synchronization
                audio_start_time=transcript.audio_start_time,
                audio_end_time=transcript.audio_end_time,
                duration=transcript.duration
            )

        logger.info("Transcripts saved successfully")
        return {"status": "success", "message": "Transcript saved successfully", "meeting_id": meeting_id}
    except Exception as e:
        logger.error(f"Error saving transcript: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-model-config")
async def get_model_config():
    """Get the current model configuration"""
    model_config = await db.get_model_config()
    if model_config:
        api_key = await db.get_api_key(model_config["provider"])
        if api_key != None:
            model_config["apiKey"] = api_key
    return model_config

@app.post("/save-model-config")
async def save_model_config(request: SaveModelConfigRequest):
    """Save the model configuration"""
    await db.save_model_config(request.provider, request.model, request.whisperModel)
    if request.apiKey != None:
        await db.save_api_key(request.apiKey, request.provider)
    return {"status": "success", "message": "Model configuration saved successfully"}  

@app.get("/get-transcript-config")
async def get_transcript_config():
    """Get the current transcript configuration"""
    transcript_config = await db.get_transcript_config()
    if transcript_config:
        transcript_api_key = await db.get_transcript_api_key(transcript_config["provider"])
        if transcript_api_key != None:
            transcript_config["apiKey"] = transcript_api_key
    return transcript_config

@app.post("/save-transcript-config")
async def save_transcript_config(request: SaveTranscriptConfigRequest):
    """Save the transcript configuration"""
    await db.save_transcript_config(request.provider, request.model)
    if request.apiKey != None:
        await db.save_transcript_api_key(request.apiKey, request.provider)
    return {"status": "success", "message": "Transcript configuration saved successfully"}

class GetApiKeyRequest(BaseModel):
    provider: str

@app.post("/get-api-key")
async def get_api_key(request: GetApiKeyRequest):
    try:
        return await db.get_api_key(request.provider)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get-transcript-api-key")
async def get_transcript_api_key(request: GetApiKeyRequest):
    try:
        return await db.get_transcript_api_key(request.provider)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class MeetingSummaryUpdate(BaseModel):
    meeting_id: str
    summary: dict

@app.post("/save-meeting-summary")
async def save_meeting_summary(data: MeetingSummaryUpdate):
    """Save a meeting summary"""
    try:
        await db.update_meeting_summary(data.meeting_id, data.summary)
        return {"message": "Meeting summary saved successfully"}
    except ValueError as ve:
        logger.error(f"Value error saving meeting summary: {str(ve)}")
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error saving meeting summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

class SearchRequest(BaseModel):
    query: str

@app.post("/search-transcripts")
async def search_transcripts(request: SearchRequest):
    """Search through meeting transcripts for the given query"""
    try:
        results = await db.search_transcripts(request.query)
        return JSONResponse(content=results)
    except Exception as e:
        logger.error(f"Error searching transcripts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SUMMARY TEMPLATES API ====================

@app.on_event("startup")
async def startup_event():
    """Initialize preset templates on startup"""
    logger.info("Initializing preset templates...")
    try:
        await db.initialize_preset_templates()
        logger.info("Preset templates initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing preset templates: {str(e)}", exc_info=True)

@app.get("/summary-templates")
async def get_templates():
    """Get all summary templates"""
    try:
        templates = await db.get_all_templates()
        # Parse schema_json for each template
        for t in templates:
            if t.get('schema_json'):
                t['schema'] = json.loads(t['schema_json'])
                del t['schema_json']
        return JSONResponse(content=templates)
    except Exception as e:
        logger.error(f"Error getting templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summary-templates/{template_id}")
async def get_template(template_id: str):
    """Get a specific template"""
    try:
        template = await db.get_template_by_id(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if template.get('schema_json'):
            template['schema'] = json.loads(template['schema_json'])
            del template['schema_json']
        return JSONResponse(content=template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    template_schema: dict  # renamed from 'schema' to avoid BaseModel conflict
    prompt_template: str = ""

@app.post("/summary-templates")
async def create_template(template: TemplateCreate):
    """Create a new template"""
    try:
        data = template.model_dump()
        data['schema'] = data.pop('template_schema')  # Map back to 'schema' for DB
        template_id = await db.create_template(data)
        return {"id": template_id, "message": "Template created successfully"}
    except Exception as e:
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class TemplateUpdate(BaseModel):
    name: str
    description: str = ""
    template_schema: dict  # renamed from 'schema' to avoid BaseModel conflict
    prompt_template: str = ""

@app.put("/summary-templates/{template_id}")
async def update_template(template_id: str, template: TemplateUpdate):
    """Update an existing template"""
    try:
        data = template.model_dump()
        data['schema'] = data.pop('template_schema')  # Map back to 'schema' for DB
        await db.update_template(template_id, data)
        return {"message": "Template updated successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/summary-templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a template"""
    try:
        await db.delete_template(template_id)
        return {"message": "Template deleted successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error deleting template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summary-templates/{template_id}/set-default")
async def set_default_template(template_id: str):
    """Set a template as the default"""
    try:
        await db.set_default_template(template_id)
        return {"message": "Default template set successfully"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error setting default template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/summary-templates/default")
async def get_default_template_endpoint():
    """Get the current default template"""
    try:
        template = await db.get_default_template()
        if not template:
            raise HTTPException(status_code=404, detail="No default template set")
        if template.get('schema_json'):
            template['schema'] = json.loads(template['schema_json'])
            del template['schema_json']
        return JSONResponse(content=template)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting default template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== END SUMMARY TEMPLATES API ====================

# ==================== CHAT WITH MEETINGS API ====================

class ChatMessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    model_provider: str = "ollama"
    model_name: str = "llama3.2:latest"

class ChatMessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    response: str

class CreateConversationRequest(BaseModel):
    meeting_id: str
    title: Optional[str] = None

@app.post("/meetings/{meeting_id}/chat")
async def send_chat_message(meeting_id: str, request: ChatMessageRequest):
    """Send a chat message about a meeting and get a response"""
    try:
        logger.info(f"Chat request for meeting {meeting_id}: {request.message[:50]}...")

        # Check if meeting exists
        meeting = await db.get_meeting(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Create or get conversation
        conversation_id = request.conversation_id
        if not conversation_id:
            # Create new conversation
            title = await chat_processor.create_conversation_title(request.message)
            conversation_id = await db.create_chat_conversation(meeting_id, title)

        # Save user message
        user_message_id = await db.add_chat_message(conversation_id, "user", request.message)

        # Get conversation history for context
        messages = await db.get_chat_messages(conversation_id)
        conversation_history = [{"role": m["role"], "content": m["content"]} for m in messages[:-1]]  # Exclude current message

        # Generate response
        response_text = await chat_processor.generate_response(
            meeting_id=meeting_id,
            message=request.message,
            conversation_history=conversation_history,
            model_provider=request.model_provider,
            model_name=request.model_name
        )

        # Save assistant response
        assistant_message_id = await db.add_chat_message(conversation_id, "assistant", response_text)

        return JSONResponse(content={
            "conversation_id": conversation_id,
            "message_id": assistant_message_id,
            "response": response_text
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/meetings/{meeting_id}/chat/conversations")
async def get_meeting_conversations(meeting_id: str):
    """Get all chat conversations for a meeting"""
    try:
        # Check if meeting exists
        meeting = await db.get_meeting(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        conversations = await db.get_chat_conversations(meeting_id)
        return JSONResponse(content=conversations)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    """Get all messages in a conversation"""
    try:
        messages = await db.get_chat_messages(conversation_id)
        if not messages:
            raise HTTPException(status_code=404, detail="Conversation not found or empty")
        return JSONResponse(content=messages)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a chat conversation and all its messages"""
    try:
        await db.delete_chat_conversation(conversation_id)
        return {"message": "Conversation deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting conversation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/conversations")
async def create_conversation(request: CreateConversationRequest):
    """Create a new chat conversation for a meeting"""
    try:
        # Check if meeting exists
        meeting = await db.get_meeting(request.meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        title = request.title or "New Conversation"
        conversation_id = await db.create_chat_conversation(request.meeting_id, title)

        return JSONResponse(content={
            "id": conversation_id,
            "meeting_id": request.meeting_id,
            "title": title
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating conversation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== END CHAT WITH MEETINGS API ====================

# ==================== SPEAKER IDENTIFICATION API ====================

from diarization_processor import DiarizationProcessor, is_pyannote_available

# Initialize diarization processor
diarization_processor = DiarizationProcessor(db)

class SpeakerUpdateRequest(BaseModel):
    label: str

class DiarizeRequest(BaseModel):
    audio_path: str

@app.get("/speakers/status")
async def get_diarization_availability():
    """Check if speaker diarization is available"""
    return {
        "pyannote_available": is_pyannote_available(),
        "message": "Pyannote speaker diarization is available" if is_pyannote_available()
                   else "Pyannote not installed. Install with: pip install pyannote.audio"
    }

@app.post("/meetings/{meeting_id}/diarize")
async def diarize_meeting(meeting_id: str, request: DiarizeRequest, background_tasks: BackgroundTasks):
    """Trigger speaker diarization for a meeting"""
    try:
        # Check if meeting exists
        meeting = await db.get_meeting(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        # Start diarization in background
        background_tasks.add_task(
            diarization_processor.diarize_audio,
            meeting_id,
            request.audio_path
        )

        return {
            "message": "Diarization started",
            "meeting_id": meeting_id,
            "pyannote_available": is_pyannote_available()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting diarization: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/meetings/{meeting_id}/diarization-status")
async def get_meeting_diarization_status(meeting_id: str):
    """Get the diarization status for a meeting"""
    try:
        status = await diarization_processor.get_diarization_status(meeting_id)
        return status or {"status": "not_started"}
    except Exception as e:
        logger.error(f"Error getting diarization status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/meetings/{meeting_id}/speakers")
async def get_meeting_speakers(meeting_id: str):
    """Get all speakers for a meeting"""
    try:
        # Check if meeting exists
        meeting = await db.get_meeting(meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        speakers = await diarization_processor.get_meeting_speakers(meeting_id)
        return JSONResponse(content=speakers)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting speakers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/meetings/{meeting_id}/speakers/{speaker_id}")
async def update_speaker(meeting_id: str, speaker_id: str, request: SpeakerUpdateRequest):
    """Update a speaker's label"""
    try:
        success = await diarization_processor.update_speaker_label(speaker_id, request.label)
        if not success:
            raise HTTPException(status_code=404, detail="Speaker not found")

        # Also update all transcripts with this speaker
        await db.update_speaker_label_on_transcripts(speaker_id, request.label)

        return {"message": "Speaker updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating speaker: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/meetings/{meeting_id}/speakers/{speaker_id}")
async def delete_speaker(meeting_id: str, speaker_id: str):
    """Delete a speaker"""
    try:
        success = await db.delete_speaker(speaker_id)
        if not success:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return {"message": "Speaker deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting speaker: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== END SPEAKER IDENTIFICATION API ====================

# ==================== CALENDAR INTEGRATION API ====================

from calendar_integration.google import GoogleCalendarClient, is_google_calendar_available

# Initialize calendar client
calendar_client = GoogleCalendarClient(db)

@app.get("/calendar/status")
async def get_calendar_status():
    """Check if calendar integration is available and configured"""
    is_configured = await calendar_client.check_is_configured()
    is_available = await calendar_client.check_is_available()
    return {
        "google_api_available": is_google_calendar_available(),
        "configured": is_configured,
        "available": is_available,
        "message": "Google Calendar integration is available" if is_available
                   else "Google Calendar not configured. Add your OAuth credentials in Settings → Calendar."
    }

# OAuth Credentials Management
class GoogleOAuthCredentials(BaseModel):
    client_id: str
    client_secret: str

@app.get("/calendar/oauth-credentials")
async def get_oauth_credentials():
    """Get stored OAuth credentials (masked)"""
    try:
        creds = await db.get_google_oauth_credentials()
        if creds:
            # Mask the secret, only show last 4 chars
            masked_secret = "***" + creds['client_secret'][-4:] if len(creds['client_secret']) > 4 else "****"
            return {
                "configured": True,
                "client_id": creds['client_id'],
                "client_secret_masked": masked_secret,
                "redirect_uri": creds['redirect_uri'],
                "created_at": creds['created_at']
            }
        return {"configured": False}
    except Exception as e:
        logger.error(f"Error getting OAuth credentials: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/calendar/oauth-credentials")
async def save_oauth_credentials(credentials: GoogleOAuthCredentials):
    """Save Google OAuth credentials"""
    try:
        # Reset the credentials loaded flag so the client will reload
        calendar_client._credentials_loaded = False

        await db.save_google_oauth_credentials(
            client_id=credentials.client_id,
            client_secret=credentials.client_secret
        )
        return {"message": "OAuth credentials saved successfully"}
    except Exception as e:
        logger.error(f"Error saving OAuth credentials: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/calendar/oauth-credentials")
async def delete_oauth_credentials():
    """Delete stored OAuth credentials"""
    try:
        # Reset the credentials loaded flag
        calendar_client._credentials_loaded = False
        calendar_client._client_id = None
        calendar_client._client_secret = None

        await db.delete_google_oauth_credentials()
        # Also delete any connected accounts since credentials are now invalid
        accounts = await db.get_calendar_accounts()
        for account in accounts:
            await db.delete_calendar_account(account['id'])
        return {"message": "OAuth credentials and connected accounts deleted"}
    except Exception as e:
        logger.error(f"Error deleting OAuth credentials: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/calendar/auth/google")
async def initiate_google_auth():
    """Get Google OAuth authorization URL"""
    is_available = await calendar_client.check_is_available()
    if not is_available:
        raise HTTPException(
            status_code=503,
            detail="Google Calendar integration not available. Add your OAuth credentials in Settings → Calendar."
        )

    auth_url = await calendar_client.get_auth_url()
    if not auth_url:
        raise HTTPException(status_code=500, detail="Failed to generate authorization URL")

    return {"auth_url": auth_url}

@app.get("/calendar/auth/google/callback")
async def google_auth_callback(code: str):
    """Handle Google OAuth callback"""
    is_available = await calendar_client.check_is_available()
    if not is_available:
        raise HTTPException(status_code=503, detail="Google Calendar integration not available")

    result = await calendar_client.exchange_code(code)
    if not result:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

    return {
        "message": "Google Calendar connected successfully",
        "account_id": result['account_id'],
        "email": result['email']
    }

@app.get("/calendar/accounts")
async def get_calendar_accounts():
    """Get all connected calendar accounts"""
    try:
        accounts = await db.get_calendar_accounts()
        return JSONResponse(content=accounts)
    except Exception as e:
        logger.error(f"Error getting calendar accounts: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/calendar/accounts/{account_id}")
async def delete_calendar_account(account_id: str):
    """Disconnect a calendar account"""
    try:
        success = await db.delete_calendar_account(account_id)
        if not success:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"message": "Calendar account disconnected successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting calendar account: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/calendar/sync")
async def sync_calendar_events(background_tasks: BackgroundTasks):
    """Trigger calendar sync for all connected accounts"""
    try:
        accounts = await db.get_calendar_accounts()
        if not accounts:
            return {"message": "No calendar accounts connected", "synced_events": 0}

        total_events = 0
        for account in accounts:
            events = await calendar_client.sync_events(account['id'])
            total_events += len(events)

        return {
            "message": "Calendar sync completed",
            "accounts_synced": len(accounts),
            "events_synced": total_events
        }
    except Exception as e:
        logger.error(f"Error syncing calendar: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/calendar/events")
async def get_upcoming_events(limit: int = 10):
    """Get upcoming calendar events"""
    try:
        events = await db.get_upcoming_events(limit)
        return JSONResponse(content=events)
    except Exception as e:
        logger.error(f"Error getting calendar events: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

class LinkEventRequest(BaseModel):
    meeting_id: str

@app.post("/calendar/events/{event_id}/link")
async def link_event_to_meeting(event_id: str, request: LinkEventRequest):
    """Link a calendar event to a meeting recording"""
    try:
        await db.link_event_to_meeting(event_id, request.meeting_id)
        return {"message": "Event linked to meeting successfully"}
    except Exception as e:
        logger.error(f"Error linking event to meeting: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== END CALENDAR INTEGRATION API ====================

# ==================== AUTO-JOIN MEETINGS API ====================

class AutoJoinSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    auto_record: Optional[bool] = None
    reminder_minutes: Optional[int] = None
    supported_platforms: Optional[List[str]] = None

@app.get("/auto-join/settings")
async def get_auto_join_settings():
    """Get auto-join settings"""
    try:
        settings = await db.get_auto_join_settings()
        return JSONResponse(content=settings)
    except Exception as e:
        logger.error(f"Error getting auto-join settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/auto-join/settings")
async def update_auto_join_settings(settings: AutoJoinSettingsUpdate):
    """Update auto-join settings"""
    try:
        await db.update_auto_join_settings(
            enabled=settings.enabled,
            auto_record=settings.auto_record,
            reminder_minutes=settings.reminder_minutes,
            supported_platforms=settings.supported_platforms
        )
        updated_settings = await db.get_auto_join_settings()
        return JSONResponse(content=updated_settings)
    except Exception as e:
        logger.error(f"Error updating auto-join settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auto-join/upcoming")
async def get_upcoming_auto_join_meetings(minutes_ahead: int = 30):
    """Get upcoming meetings that qualify for auto-join"""
    try:
        candidates = await db.get_upcoming_auto_join_candidates(minutes_ahead)
        return JSONResponse(content=candidates)
    except Exception as e:
        logger.error(f"Error getting auto-join candidates: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

class MeetingJoinAction(BaseModel):
    action: str  # 'reminded', 'joined', 'skipped'

@app.post("/auto-join/trigger/{event_id}")
async def log_auto_join_action(event_id: str, action: MeetingJoinAction):
    """Log an auto-join action for a meeting event"""
    try:
        valid_actions = ['reminded', 'joined', 'skipped']
        if action.action not in valid_actions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action. Must be one of: {valid_actions}"
            )

        log_id = await db.log_meeting_join(event_id, action.action)
        return {
            "message": "Action logged successfully",
            "log_id": log_id,
            "event_id": event_id,
            "action": action.action
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging auto-join action: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ==================== END AUTO-JOIN MEETINGS API ====================

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on API shutdown"""
    logger.info("API shutting down, cleaning up resources")
    try:
        processor.cleanup()
        logger.info("Successfully cleaned up resources")
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}", exc_info=True)

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    uvicorn.run("main:app", host="0.0.0.0", port=5167, reload=True)
