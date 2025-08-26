# AI-Powered Resume Scanner - API Contracts & Integration Guide

## Project Overview
Full-stack AI-powered resume screening system using GPT-4o for intelligent analysis and matching.

## Backend API Endpoints

### Base URL
- **Development**: `http://localhost:8001/api`
- **Production**: `{REACT_APP_BACKEND_URL}/api`

### Authentication
- Currently no authentication required
- Uses Emergent LLM universal key for AI services

---

## API Endpoints

### 1. Health Check
```http
GET /api/health
```
**Response:**
```json
{
  "status": "healthy",
  "message": "All services operational", 
  "ai_service": "Connected"
}
```

### 2. Resume Scanning (Main Feature)
```http
POST /api/scan_resume
Content-Type: multipart/form-data
```

**Request Body:**
- `resume_file`: File (PDF/DOCX, max 10MB)
- `job_description`: String (minimum 50 characters)

**Response:**
```json
{
  "id": "uuid4-string",
  "filename": "resume.pdf",
  "extracted_data": {
    "skills": ["Python", "React", "Machine Learning"],
    "education": ["B.S. Computer Science - MIT 2020"],
    "experience": ["Software Engineer - Google - 3 years"]
  },
  "match_score": 87.5,
  "job_description": "Looking for Python developer...",
  "analysis_summary": "Strong match with required skills...",
  "created_at": "2024-01-01T12:00:00Z"
}
```

**Error Responses:**
- `400`: Invalid file format, file too large, job description too short
- `500`: AI processing error, database error

### 3. Get Scan History
```http
GET /api/scan_history?limit=20&skip=0
```

**Response:**
```json
{
  "scans": [/* Array of scan results */],
  "total_count": 45
}
```

### 4. Get Specific Scan
```http
GET /api/scan/{scan_id}
```

### 5. Delete Scan
```http
DELETE /api/scan/{scan_id}
```

---

## Frontend Components

### Main Components
1. **ResumeScanner** - Main container component
2. **Header** - Navigation and branding
3. **Hero** - Dynamic hero section based on current view
4. **UploadSection** - File upload and job description input
5. **ResultsSection** - Display scan results and analysis
6. **HistorySection** - View past scans with search/filter

### Key Features
- **Drag & Drop Upload**: Supports PDF and DOCX files
- **Real-time Validation**: File type, size, and job description length
- **Animated UI**: Smooth transitions and loading states  
- **Responsive Design**: Mobile-first responsive layout
- **State Management**: React hooks for component state

---

## Database Schema (MongoDB)

### Collection: `resume_scans`
```javascript
{
  _id: ObjectId,
  id: "uuid4-string",           // Frontend-facing ID
  filename: "resume.pdf",
  extracted_data: {
    skills: ["skill1", "skill2"],
    education: ["education1"],
    experience: ["experience1"]
  },
  match_score: 87.5,            // 0-100 percentage
  job_description: "text...",
  analysis_summary: "text...",
  created_at: Date
}
```

---

## AI Processing Pipeline

### 1. File Processing
- **PDF**: PyMuPDF for text extraction
- **DOCX**: python-docx for text extraction
- **Validation**: File size (10MB max), format validation

### 2. AI Analysis (GPT-4o)
```python
# Resume data extraction
extraction_prompt = """
Analyze resume and extract:
{
  "skills": ["skill1", "skill2"],
  "education": ["degree - institution"],
  "experience": ["role - company - description"]
}
"""

# Job matching & scoring
matching_prompt = """
Calculate match score (0-100) and provide analysis summary
considering skills, experience, education alignment
"""
```

### 3. Fallback Processing
- Basic NLP extraction if AI fails
- Keyword matching for skills
- Regex patterns for education/experience

---

## Environment Variables

### Backend (.env)
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
CORS_ORIGINS=*
EMERGENT_LLM_KEY=sk-emergent-...
```

### Frontend (.env)
```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

---

## Error Handling

### Frontend
- File validation before upload
- Loading states during processing
- Error messages for user feedback
- Retry mechanisms for failed requests

### Backend
- Input validation and sanitization
- AI service fallback mechanisms
- Detailed error logging
- Graceful degradation for AI failures

---

## Performance Considerations

### Frontend
- Lazy loading for components
- Optimized images and assets
- Debounced search in history
- Pagination for large datasets

### Backend
- Async processing for AI calls
- Connection pooling for database
- File size limits and validation
- Request timeout handling

---

## Testing Strategy

### Manual Testing
1. Upload various resume formats (PDF, DOCX)
2. Test with different job descriptions
3. Verify accuracy of extracted data
4. Test error scenarios (invalid files, network errors)

### API Testing
```bash
# Health check
curl -X GET "http://localhost:8001/api/health"

# Upload test (requires multipart form data)
curl -X POST "http://localhost:8001/api/scan_resume" \
  -F "resume_file=@sample_resume.pdf" \
  -F "job_description=Software Engineer position..."
```

---

## Deployment Configuration

### Backend (Render/Heroku)
- Environment variables configured
- Requirements.txt with all dependencies
- Gunicorn/Uvicorn for production server
- Health check endpoint for monitoring

### Frontend (Vercel/Netlify)
- Build command: `npm run build`
- Publish directory: `build`
- Environment variables for API URL
- Redirects for SPA routing

---

## Security Considerations

### Current Implementation
- CORS enabled for development
- File type and size validation
- Input sanitization for job descriptions

### Production Recommendations
- Rate limiting for API endpoints
- File upload virus scanning
- Authentication and authorization
- HTTPS enforcement
- Environment variable security

---

## Future Enhancements

### Planned Features
1. **User Authentication**: Login/signup functionality
2. **Advanced Analytics**: Match score trends, skills analysis
3. **Bulk Processing**: Upload multiple resumes at once
4. **Custom Scoring**: Adjustable match criteria
5. **Resume Templates**: Generate improved resumes
6. **Integration APIs**: Connect with ATS systems

### Technical Improvements
1. **Caching**: Redis for frequent queries
2. **Monitoring**: Application performance monitoring
3. **Testing**: Automated test suites
4. **Documentation**: Interactive API docs with Swagger
5. **Optimization**: Database indexing, query optimization

---

This contract serves as the complete technical specification for frontend-backend integration and system architecture.