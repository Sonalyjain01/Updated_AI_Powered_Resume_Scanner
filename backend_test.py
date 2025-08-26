#!/usr/bin/env python3
"""
Comprehensive Backend Testing for AI-Powered Resume Scanner
Tests all API endpoints, AI integration, file processing, and database operations
"""

import asyncio
import aiohttp
import json
import os
import io
from pathlib import Path
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ResumeScannerTester:
    def __init__(self):
        # Get backend URL from frontend .env file
        self.base_url = self._get_backend_url()
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_results = {
            "health_check": {"status": "pending", "details": ""},
            "file_validation": {"status": "pending", "details": ""},
            "resume_scanning": {"status": "pending", "details": ""},
            "scan_history": {"status": "pending", "details": ""},
            "scan_retrieval": {"status": "pending", "details": ""},
            "scan_deletion": {"status": "pending", "details": ""},
            "error_handling": {"status": "pending", "details": ""},
            "ai_integration": {"status": "pending", "details": ""}
        }
        
    def _get_backend_url(self) -> str:
        """Get backend URL from frontend .env file"""
        try:
            frontend_env_path = Path("/app/frontend/.env")
            if frontend_env_path.exists():
                with open(frontend_env_path, 'r') as f:
                    for line in f:
                        if line.startswith('REACT_APP_BACKEND_URL='):
                            backend_url = line.split('=', 1)[1].strip()
                            return f"{backend_url}/api"
            
            # Fallback
            return "https://resume-scanner-3.preview.emergentagent.com/api"
        except Exception as e:
            logger.warning(f"Could not read frontend .env: {e}")
            return "https://resume-scanner-3.preview.emergentagent.com/api"
    
    async def setup_session(self):
        """Setup aiohttp session"""
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        logger.info(f"Testing backend at: {self.base_url}")
    
    async def cleanup_session(self):
        """Cleanup aiohttp session"""
        if self.session:
            await self.session.close()
    
    def _create_test_pdf_content(self) -> bytes:
        """Create a simple test PDF content"""
        # This creates a minimal PDF structure for testing
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(John Doe Resume) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF"""
        return pdf_content
    
    def _create_realistic_resume_text(self) -> str:
        """Create realistic resume text for testing"""
        return """
        SARAH JOHNSON
        Senior Software Engineer
        Email: sarah.johnson@email.com | Phone: (555) 123-4567
        LinkedIn: linkedin.com/in/sarahjohnson
        
        PROFESSIONAL SUMMARY
        Experienced software engineer with 7+ years in full-stack development, 
        specializing in Python, JavaScript, and cloud technologies. Proven track 
        record in building scalable web applications and leading development teams.
        
        TECHNICAL SKILLS
        • Programming Languages: Python, JavaScript, TypeScript, Java, SQL
        • Frameworks: React, FastAPI, Django, Node.js, Express
        • Cloud Technologies: AWS, Docker, Kubernetes, MongoDB, PostgreSQL
        • Tools: Git, Jenkins, JIRA, Agile methodologies
        • Machine Learning: TensorFlow, scikit-learn, pandas, numpy
        
        PROFESSIONAL EXPERIENCE
        
        Senior Software Engineer | TechCorp Inc. | 2020 - Present
        • Led development of microservices architecture serving 1M+ users
        • Implemented CI/CD pipelines reducing deployment time by 60%
        • Mentored junior developers and conducted code reviews
        • Built RESTful APIs using Python FastAPI and PostgreSQL
        
        Software Engineer | StartupXYZ | 2018 - 2020
        • Developed React-based frontend applications
        • Integrated third-party APIs and payment systems
        • Optimized database queries improving performance by 40%
        • Collaborated with cross-functional teams using Agile methodology
        
        Junior Developer | WebSolutions | 2017 - 2018
        • Built responsive web applications using HTML, CSS, JavaScript
        • Maintained legacy PHP applications
        • Participated in daily standups and sprint planning
        
        EDUCATION
        Bachelor of Science in Computer Science
        University of Technology | 2013 - 2017
        GPA: 3.8/4.0
        
        CERTIFICATIONS
        • AWS Certified Solutions Architect
        • Certified Scrum Master (CSM)
        
        PROJECTS
        • E-commerce Platform: Built full-stack application with React and Python
        • Data Analytics Dashboard: Created ML-powered insights platform
        • Mobile App: Developed cross-platform app with React Native
        """
    
    async def test_health_check(self) -> bool:
        """Test health check endpoint"""
        try:
            logger.info("Testing health check endpoint...")
            
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Validate response structure
                    required_fields = ["status", "message", "ai_service"]
                    if all(field in data for field in required_fields):
                        ai_status = data.get("ai_service", "")
                        self.test_results["health_check"] = {
                            "status": "passed",
                            "details": f"Health check successful. AI Service: {ai_status}"
                        }
                        logger.info(f"✅ Health check passed - AI Service: {ai_status}")
                        return True
                    else:
                        self.test_results["health_check"] = {
                            "status": "failed",
                            "details": f"Missing required fields in response: {data}"
                        }
                        return False
                else:
                    self.test_results["health_check"] = {
                        "status": "failed",
                        "details": f"HTTP {response.status}: {await response.text()}"
                    }
                    return False
                    
        except Exception as e:
            self.test_results["health_check"] = {
                "status": "failed",
                "details": f"Exception: {str(e)}"
            }
            logger.error(f"❌ Health check failed: {e}")
            return False
    
    async def test_file_validation(self) -> bool:
        """Test file upload validation"""
        try:
            logger.info("Testing file validation...")
            
            # Test 1: Invalid file type
            invalid_data = aiohttp.FormData()
            invalid_data.add_field('resume_file', 
                                 io.BytesIO(b"test content"), 
                                 filename='test.txt',
                                 content_type='text/plain')
            invalid_data.add_field('job_description', 'Test job description with enough characters to meet minimum requirements for testing purposes.')
            
            async with self.session.post(f"{self.base_url}/scan_resume", data=invalid_data) as response:
                if response.status == 400:
                    logger.info("✅ Invalid file type correctly rejected")
                else:
                    self.test_results["file_validation"] = {
                        "status": "failed",
                        "details": f"Invalid file type not rejected properly. Status: {response.status}"
                    }
                    return False
            
            # Test 2: Empty job description
            valid_file_data = aiohttp.FormData()
            valid_file_data.add_field('resume_file', 
                                    io.BytesIO(self._create_test_pdf_content()), 
                                    filename='test_resume.pdf',
                                    content_type='application/pdf')
            valid_file_data.add_field('job_description', '')
            
            async with self.session.post(f"{self.base_url}/scan_resume", data=valid_file_data) as response:
                if response.status == 400:
                    logger.info("✅ Empty job description correctly rejected")
                else:
                    self.test_results["file_validation"] = {
                        "status": "failed",
                        "details": f"Empty job description not rejected properly. Status: {response.status}"
                    }
                    return False
            
            # Test 3: Short job description
            short_jd_data = aiohttp.FormData()
            short_jd_data.add_field('resume_file', 
                                  io.BytesIO(self._create_test_pdf_content()), 
                                  filename='test_resume.pdf',
                                  content_type='application/pdf')
            short_jd_data.add_field('job_description', 'Short JD')
            
            async with self.session.post(f"{self.base_url}/scan_resume", data=short_jd_data) as response:
                if response.status == 400:
                    logger.info("✅ Short job description correctly rejected")
                    self.test_results["file_validation"] = {
                        "status": "passed",
                        "details": "File validation tests passed - invalid files and short job descriptions properly rejected"
                    }
                    return True
                else:
                    self.test_results["file_validation"] = {
                        "status": "failed",
                        "details": f"Short job description not rejected properly. Status: {response.status}"
                    }
                    return False
                    
        except Exception as e:
            self.test_results["file_validation"] = {
                "status": "failed",
                "details": f"Exception during file validation: {str(e)}"
            }
            logger.error(f"❌ File validation test failed: {e}")
            return False
    
    async def test_resume_scanning(self) -> Optional[str]:
        """Test resume scanning functionality"""
        try:
            logger.info("Testing resume scanning...")
            
            # Create realistic test data
            job_description = """
            We are seeking a Senior Software Engineer to join our dynamic team. 
            The ideal candidate will have 5+ years of experience in full-stack development 
            with expertise in Python, JavaScript, and cloud technologies.
            
            Key Requirements:
            - Strong proficiency in Python and FastAPI
            - Experience with React and modern JavaScript frameworks
            - Knowledge of AWS, Docker, and containerization
            - Database experience with PostgreSQL or MongoDB
            - Experience with CI/CD pipelines and DevOps practices
            - Strong problem-solving skills and ability to work in Agile environment
            - Bachelor's degree in Computer Science or related field
            
            Preferred Qualifications:
            - Machine Learning experience
            - Leadership and mentoring experience
            - AWS certifications
            - Experience with microservices architecture
            """
            
            # Create form data with realistic resume
            form_data = aiohttp.FormData()
            
            # Create a more realistic PDF-like content
            resume_content = f"""
            %PDF-1.4
            Resume Content:
            {self._create_realistic_resume_text()}
            """.encode('utf-8')
            
            form_data.add_field('resume_file', 
                              io.BytesIO(resume_content), 
                              filename='sarah_johnson_resume.pdf',
                              content_type='application/pdf')
            form_data.add_field('job_description', job_description)
            
            async with self.session.post(f"{self.base_url}/scan_resume", data=form_data) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Validate response structure
                    required_fields = ["id", "filename", "extracted_data", "match_score", "job_description", "analysis_summary"]
                    if all(field in data for field in required_fields):
                        
                        # Validate extracted_data structure
                        extracted_data = data.get("extracted_data", {})
                        if all(key in extracted_data for key in ["skills", "education", "experience"]):
                            
                            match_score = data.get("match_score", 0)
                            if 0 <= match_score <= 100:
                                self.test_results["resume_scanning"] = {
                                    "status": "passed",
                                    "details": f"Resume scanning successful. Match Score: {match_score}%, Skills: {len(extracted_data.get('skills', []))}, ID: {data.get('id')}"
                                }
                                logger.info(f"✅ Resume scanning passed - Match Score: {match_score}%")
                                return data.get("id")  # Return scan ID for further tests
                            else:
                                self.test_results["resume_scanning"] = {
                                    "status": "failed",
                                    "details": f"Invalid match score: {match_score}"
                                }
                        else:
                            self.test_results["resume_scanning"] = {
                                "status": "failed",
                                "details": f"Invalid extracted_data structure: {extracted_data}"
                            }
                    else:
                        self.test_results["resume_scanning"] = {
                            "status": "failed",
                            "details": f"Missing required fields in response: {list(data.keys())}"
                        }
                else:
                    error_text = await response.text()
                    self.test_results["resume_scanning"] = {
                        "status": "failed",
                        "details": f"HTTP {response.status}: {error_text}"
                    }
                    logger.error(f"❌ Resume scanning failed: {response.status} - {error_text}")
                    
        except Exception as e:
            self.test_results["resume_scanning"] = {
                "status": "failed",
                "details": f"Exception during resume scanning: {str(e)}"
            }
            logger.error(f"❌ Resume scanning test failed: {e}")
            
        return None
    
    async def test_scan_history(self) -> bool:
        """Test scan history endpoint"""
        try:
            logger.info("Testing scan history...")
            
            # Test with default parameters
            async with self.session.get(f"{self.base_url}/scan_history") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Validate response structure
                    if "scans" in data and "total_count" in data:
                        scans = data.get("scans", [])
                        total_count = data.get("total_count", 0)
                        
                        self.test_results["scan_history"] = {
                            "status": "passed",
                            "details": f"Scan history retrieved successfully. Total scans: {total_count}, Retrieved: {len(scans)}"
                        }
                        logger.info(f"✅ Scan history passed - Total: {total_count}, Retrieved: {len(scans)}")
                        return True
                    else:
                        self.test_results["scan_history"] = {
                            "status": "failed",
                            "details": f"Invalid response structure: {list(data.keys())}"
                        }
                else:
                    error_text = await response.text()
                    self.test_results["scan_history"] = {
                        "status": "failed",
                        "details": f"HTTP {response.status}: {error_text}"
                    }
                    
        except Exception as e:
            self.test_results["scan_history"] = {
                "status": "failed",
                "details": f"Exception during scan history test: {str(e)}"
            }
            logger.error(f"❌ Scan history test failed: {e}")
            
        return False
    
    async def test_scan_retrieval(self, scan_id: str) -> bool:
        """Test individual scan retrieval"""
        try:
            logger.info(f"Testing scan retrieval for ID: {scan_id}")
            
            async with self.session.get(f"{self.base_url}/scan/{scan_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Validate that we get the same scan back
                    if data.get("id") == scan_id:
                        self.test_results["scan_retrieval"] = {
                            "status": "passed",
                            "details": f"Scan retrieval successful for ID: {scan_id}"
                        }
                        logger.info(f"✅ Scan retrieval passed for ID: {scan_id}")
                        return True
                    else:
                        self.test_results["scan_retrieval"] = {
                            "status": "failed",
                            "details": f"Retrieved scan ID mismatch. Expected: {scan_id}, Got: {data.get('id')}"
                        }
                elif response.status == 404:
                    self.test_results["scan_retrieval"] = {
                        "status": "failed",
                        "details": f"Scan not found (404) for ID: {scan_id}"
                    }
                else:
                    error_text = await response.text()
                    self.test_results["scan_retrieval"] = {
                        "status": "failed",
                        "details": f"HTTP {response.status}: {error_text}"
                    }
                    
        except Exception as e:
            self.test_results["scan_retrieval"] = {
                "status": "failed",
                "details": f"Exception during scan retrieval: {str(e)}"
            }
            logger.error(f"❌ Scan retrieval test failed: {e}")
            
        return False
    
    async def test_scan_deletion(self, scan_id: str) -> bool:
        """Test scan deletion"""
        try:
            logger.info(f"Testing scan deletion for ID: {scan_id}")
            
            async with self.session.delete(f"{self.base_url}/scan/{scan_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    if "message" in data:
                        self.test_results["scan_deletion"] = {
                            "status": "passed",
                            "details": f"Scan deletion successful for ID: {scan_id}"
                        }
                        logger.info(f"✅ Scan deletion passed for ID: {scan_id}")
                        return True
                    else:
                        self.test_results["scan_deletion"] = {
                            "status": "failed",
                            "details": f"Invalid deletion response: {data}"
                        }
                elif response.status == 404:
                    self.test_results["scan_deletion"] = {
                        "status": "failed",
                        "details": f"Scan not found for deletion (404) for ID: {scan_id}"
                    }
                else:
                    error_text = await response.text()
                    self.test_results["scan_deletion"] = {
                        "status": "failed",
                        "details": f"HTTP {response.status}: {error_text}"
                    }
                    
        except Exception as e:
            self.test_results["scan_deletion"] = {
                "status": "failed",
                "details": f"Exception during scan deletion: {str(e)}"
            }
            logger.error(f"❌ Scan deletion test failed: {e}")
            
        return False
    
    async def test_error_handling(self) -> bool:
        """Test various error scenarios"""
        try:
            logger.info("Testing error handling...")
            
            # Test 1: Non-existent scan retrieval
            async with self.session.get(f"{self.base_url}/scan/non-existent-id") as response:
                if response.status != 404:
                    self.test_results["error_handling"] = {
                        "status": "failed",
                        "details": f"Non-existent scan should return 404, got {response.status}"
                    }
                    return False
            
            # Test 2: Non-existent scan deletion
            async with self.session.delete(f"{self.base_url}/scan/non-existent-id") as response:
                if response.status != 404:
                    self.test_results["error_handling"] = {
                        "status": "failed",
                        "details": f"Non-existent scan deletion should return 404, got {response.status}"
                    }
                    return False
            
            self.test_results["error_handling"] = {
                "status": "passed",
                "details": "Error handling tests passed - proper 404 responses for non-existent resources"
            }
            logger.info("✅ Error handling tests passed")
            return True
            
        except Exception as e:
            self.test_results["error_handling"] = {
                "status": "failed",
                "details": f"Exception during error handling tests: {str(e)}"
            }
            logger.error(f"❌ Error handling test failed: {e}")
            return False
    
    async def test_ai_integration(self) -> bool:
        """Test AI integration specifically"""
        try:
            logger.info("Testing AI integration...")
            
            # Check if health endpoint shows AI as connected
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    ai_service = data.get("ai_service", "")
                    
                    if "connected" in ai_service.lower():
                        self.test_results["ai_integration"] = {
                            "status": "passed",
                            "details": f"AI service is connected: {ai_service}"
                        }
                        logger.info(f"✅ AI integration test passed - {ai_service}")
                        return True
                    else:
                        self.test_results["ai_integration"] = {
                            "status": "failed",
                            "details": f"AI service not connected: {ai_service}"
                        }
                        logger.warning(f"⚠️ AI service status: {ai_service}")
                        return False
                else:
                    self.test_results["ai_integration"] = {
                        "status": "failed",
                        "details": f"Could not check AI status. HTTP {response.status}"
                    }
                    return False
                    
        except Exception as e:
            self.test_results["ai_integration"] = {
                "status": "failed",
                "details": f"Exception during AI integration test: {str(e)}"
            }
            logger.error(f"❌ AI integration test failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all backend tests"""
        logger.info("🚀 Starting comprehensive backend testing...")
        
        await self.setup_session()
        
        try:
            # Test sequence
            health_ok = await self.test_health_check()
            
            if health_ok:
                file_validation_ok = await self.test_file_validation()
                scan_id = await self.test_resume_scanning()
                history_ok = await self.test_scan_history()
                ai_ok = await self.test_ai_integration()
                error_ok = await self.test_error_handling()
                
                # Test scan retrieval and deletion if we have a scan ID
                retrieval_ok = deletion_ok = False
                if scan_id:
                    retrieval_ok = await self.test_scan_retrieval(scan_id)
                    deletion_ok = await self.test_scan_deletion(scan_id)
                else:
                    self.test_results["scan_retrieval"]["status"] = "skipped"
                    self.test_results["scan_retrieval"]["details"] = "No scan ID available from resume scanning test"
                    self.test_results["scan_deletion"]["status"] = "skipped"
                    self.test_results["scan_deletion"]["details"] = "No scan ID available from resume scanning test"
            
        finally:
            await self.cleanup_session()
        
        # Print comprehensive results
        self.print_test_results()
    
    def print_test_results(self):
        """Print comprehensive test results"""
        logger.info("\n" + "="*80)
        logger.info("🧪 BACKEND TEST RESULTS SUMMARY")
        logger.info("="*80)
        
        passed_count = 0
        failed_count = 0
        skipped_count = 0
        
        for test_name, result in self.test_results.items():
            status = result["status"]
            details = result["details"]
            
            if status == "passed":
                logger.info(f"✅ {test_name.upper()}: PASSED")
                logger.info(f"   Details: {details}")
                passed_count += 1
            elif status == "failed":
                logger.error(f"❌ {test_name.upper()}: FAILED")
                logger.error(f"   Details: {details}")
                failed_count += 1
            elif status == "skipped":
                logger.warning(f"⏭️  {test_name.upper()}: SKIPPED")
                logger.warning(f"   Details: {details}")
                skipped_count += 1
            else:
                logger.warning(f"⏸️  {test_name.upper()}: PENDING")
                failed_count += 1
        
        logger.info("\n" + "="*80)
        logger.info(f"📊 FINAL RESULTS: {passed_count} PASSED | {failed_count} FAILED | {skipped_count} SKIPPED")
        logger.info("="*80)
        
        # Overall assessment
        if failed_count == 0:
            logger.info("🎉 ALL CRITICAL TESTS PASSED! Backend is working properly.")
        elif failed_count <= 2:
            logger.warning("⚠️  Some tests failed but core functionality appears to work.")
        else:
            logger.error("🚨 MULTIPLE CRITICAL FAILURES detected. Backend needs attention.")

async def main():
    """Main test execution"""
    tester = ResumeScannerTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())