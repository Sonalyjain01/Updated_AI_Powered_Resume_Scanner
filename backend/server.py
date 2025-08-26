from fastapi import FastAPI, File, UploadFile, Form, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging
from pathlib import Path
from typing import List

from models import (
    ResumeAnalysisResponse, 
    ScanHistoryResponse, 
    HealthResponse,
    ExtractedData
)
from file_processor import FileProcessor
from ai_processor import AIResumeProcessor
from database import database

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI-Powered Resume Scanner API",
    description="Intelligent Resume Screening using AI & NLP",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create API router
api_router = APIRouter(prefix="/api")

# Initialize AI processor
ai_processor = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global ai_processor
    
    try:
        # Connect to database
        await database.connect()
        logger.info("Database connected successfully")
        
        # Initialize AI processor
        ai_processor = AIResumeProcessor()
        logger.info("AI processor initialized successfully")
        
        # Test AI connection
        ai_connected = await ai_processor.test_connection()
        if ai_connected:
            logger.info("AI service connection verified")
        else:
            logger.warning("AI service connection test failed")
            
    except Exception as e:
        logger.error(f"Startup error: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await database.close()
    logger.info("Application shutdown complete")

@api_router.get("/", tags=["Health"])
async def root():
    """Root endpoint for health check"""
    return {"message": "AI-Powered Resume Scanner API is running"}

@api_router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Comprehensive health check"""
    try:
        # Test AI connection
        ai_status = "Connected" if ai_processor and await ai_processor.test_connection() else "Disconnected"
        
        return HealthResponse(
            status="healthy",
            message="All services operational",
            ai_service=ai_status
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@api_router.post("/scan_resume", response_model=ResumeAnalysisResponse, tags=["Resume Analysis"])
async def scan_resume(
    resume_file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    job_description: str = Form(..., description="Job description to match against")
):
    """
    Scan and analyze resume against job description
    
    - **resume_file**: PDF or DOCX file containing the resume
    - **job_description**: Job description text to match against
    
    Returns extracted skills, education, experience, and match score
    """
    if not ai_processor:
        raise HTTPException(status_code=500, detail="AI processor not initialized")
    
    try:
        # Validate job description
        if not job_description.strip():
            raise HTTPException(status_code=400, detail="Job description cannot be empty")
        
        if len(job_description.strip()) < 50:
            raise HTTPException(status_code=400, detail="Job description too short (minimum 50 characters)")
        
        # Read file content
        file_content = await resume_file.read()
        
        logger.info(f"Processing resume file: {resume_file.filename}")
        
        # Extract text from file
        try:
            resume_text = await FileProcessor.extract_text_from_file(
                file_content, resume_file.filename
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Validate extracted text
        if len(resume_text.strip()) < 100:
            raise HTTPException(
                status_code=400, 
                detail="Resume appears to be too short or empty. Please ensure the file contains readable text."
            )
        
        logger.info(f"Extracted {len(resume_text)} characters from resume")
        
        # Extract structured data using AI
        extracted_data_dict = await ai_processor.extract_resume_data(resume_text)
        extracted_data = ExtractedData(**extracted_data_dict)
        
        # Calculate match score
        match_score, analysis_summary = await ai_processor.calculate_match_score(
            resume_text, job_description, extracted_data_dict
        )
        
        # Create response
        analysis_response = ResumeAnalysisResponse(
            filename=resume_file.filename,
            extracted_data=extracted_data,
            match_score=match_score,
            job_description=job_description,
            analysis_summary=analysis_summary
        )
        
        # Save to database
        try:
            await database.save_scan_result(analysis_response)
        except Exception as e:
            logger.error(f"Failed to save scan result: {str(e)}")
            # Continue without saving to database
        
        logger.info(f"Resume scan completed - Match Score: {match_score}%")
        return analysis_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resume scan error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Resume processing failed: {str(e)}")

@api_router.get("/scan_history", response_model=ScanHistoryResponse, tags=["History"])
async def get_scan_history(limit: int = 20, skip: int = 0):
    """
    Get scan history with pagination
    
    - **limit**: Number of results to return (max 100)
    - **skip**: Number of results to skip for pagination
    """
    try:
        # Validate parameters
        limit = min(max(1, limit), 100)  # Clamp between 1 and 100
        skip = max(0, skip)
        
        # Get scan history
        scans = await database.get_scan_history(limit=limit, skip=skip)
        total_count = await database.get_total_scans_count()
        
        return ScanHistoryResponse(
            scans=scans,
            total_count=total_count
        )
        
    except Exception as e:
        logger.error(f"Error retrieving scan history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scan history")

@api_router.get("/scan/{scan_id}", response_model=ResumeAnalysisResponse, tags=["History"])
async def get_scan_by_id(scan_id: str):
    """Get specific scan result by ID"""
    try:
        scan_result = await database.get_scan_by_id(scan_id)
        
        if not scan_result:
            raise HTTPException(status_code=404, detail="Scan result not found")
        
        return scan_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving scan {scan_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scan")

@api_router.delete("/scan/{scan_id}", tags=["History"])
async def delete_scan(scan_id: str):
    """Delete scan result by ID"""
    try:
        deleted = await database.delete_scan(scan_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Scan result not found")
        
        return {"message": "Scan deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting scan {scan_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete scan")

# Include the API router
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )