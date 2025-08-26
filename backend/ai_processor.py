import asyncio
import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class AIResumeProcessor:
    def __init__(self):
        self.api_key = os.getenv('EMERGENT_LLM_KEY', 'sk-emergent-767C06f84EaDfD455E')
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment variables")
        
        self.chat = LlmChat(
            api_key=self.api_key,
            session_id="resume-scanner",
            system_message="You are an expert AI assistant specialized in resume analysis and job matching. You provide accurate, structured analysis of resumes against job descriptions."
        ).with_model("openai", "gpt-4o")
        
        logger.info("AI Resume Processor initialized with GPT-4o")

    async def extract_resume_data(self, resume_text: str) -> Dict[str, List[str]]:
        """Extract skills, education, and experience from resume text using GPT-4o"""
        try:
            extraction_prompt = f"""
            Analyze the following resume text and extract structured information. 
            Return ONLY a valid JSON object with the following format:
            {{
                "skills": ["skill1", "skill2", "skill3"],
                "education": ["degree/institution details"],
                "experience": ["job title - company - duration/description"]
            }}
            
            Guidelines:
            - Extract relevant technical and soft skills
            - Include education degrees, institutions, and years if available
            - Summarize work experience with job titles, companies, and key responsibilities
            - Be concise but comprehensive
            - Return valid JSON only, no additional text
            
            Resume Text:
            {resume_text}
            """
            
            user_message = UserMessage(text=extraction_prompt)
            response = await self.chat.send_message(user_message)
            
            # Parse the JSON response
            import json
            try:
                extracted_data = json.loads(response)
                return extracted_data
            except json.JSONDecodeError:
                # Fallback parsing if GPT doesn't return pure JSON
                logger.warning("Failed to parse JSON response, using fallback extraction")
                return self._fallback_extraction(resume_text)
                
        except Exception as e:
            logger.error(f"Error in AI extraction: {str(e)}")
            return self._fallback_extraction(resume_text)

    def _fallback_extraction(self, resume_text: str) -> Dict[str, List[str]]:
        """Fallback extraction using basic NLP if AI fails"""
        import re
        
        # Basic keyword extraction
        skill_keywords = ['python', 'javascript', 'java', 'react', 'sql', 'aws', 'docker', 
                         'machine learning', 'data analysis', 'project management']
        
        skills = [skill for skill in skill_keywords 
                 if skill.lower() in resume_text.lower()]
        
        # Extract education patterns
        education_patterns = [
            r'(bachelor|master|phd|b\.s\.|m\.s\.|ph\.d\.)[^.]*',
            r'university[^.]*',
            r'college[^.]*'
        ]
        education = []
        for pattern in education_patterns:
            matches = re.findall(pattern, resume_text, re.IGNORECASE)
            education.extend(matches[:2])  # Limit to 2 matches
        
        # Extract experience (basic)
        experience = ["Experience details extracted from resume"]
        if "years" in resume_text.lower():
            exp_match = re.search(r'(\d+)\s+years?', resume_text, re.IGNORECASE)
            if exp_match:
                experience = [f"{exp_match.group(1)} years of experience mentioned"]
        
        return {
            "skills": skills[:10],  # Limit to top 10
            "education": education[:3],  # Limit to 3
            "experience": experience[:5]  # Limit to 5
        }

    async def calculate_match_score(self, resume_text: str, job_description: str, 
                                  extracted_data: Dict[str, List[str]]) -> Tuple[float, str]:
        """Calculate match score between resume and job description using GPT-4o"""
        try:
            matching_prompt = f"""
            As an expert resume analyzer, calculate a match score (0-100) between the resume and job description.
            
            Consider:
            1. Skills alignment (technical and soft skills)
            2. Experience relevance 
            3. Education requirements
            4. Industry experience
            5. Overall qualification fit
            
            Return ONLY a JSON object with this format:
            {{
                "match_score": 85.5,
                "analysis_summary": "Strong match with required Python and ML skills. 5+ years experience aligns well. Missing some cloud technologies mentioned in JD."
            }}
            
            Extracted Resume Data:
            Skills: {extracted_data.get('skills', [])}
            Education: {extracted_data.get('education', [])}
            Experience: {extracted_data.get('experience', [])}
            
            Job Description:
            {job_description}
            
            Full Resume Text:
            {resume_text[:2000]}...
            """
            
            user_message = UserMessage(text=matching_prompt)
            response = await self.chat.send_message(user_message)
            
            # Parse the JSON response
            import json
            try:
                result = json.loads(response)
                match_score = float(result.get('match_score', 75.0))
                analysis_summary = result.get('analysis_summary', 'AI analysis completed')
                
                # Ensure score is within bounds
                match_score = max(0, min(100, match_score))
                
                return match_score, analysis_summary
                
            except (json.JSONDecodeError, ValueError):
                logger.warning("Failed to parse matching response, using fallback")
                return self._fallback_matching(extracted_data, job_description)
                
        except Exception as e:
            logger.error(f"Error in AI matching: {str(e)}")
            return self._fallback_matching(extracted_data, job_description)

    def _fallback_matching(self, extracted_data: Dict[str, List[str]], 
                          job_description: str) -> Tuple[float, str]:
        """Fallback matching using basic keyword comparison"""
        skills = extracted_data.get('skills', [])
        jd_lower = job_description.lower()
        
        # Count skill matches
        skill_matches = sum(1 for skill in skills if skill.lower() in jd_lower)
        total_skills = len(skills) if skills else 1
        
        # Basic score calculation
        skill_score = (skill_matches / total_skills) * 100
        base_score = min(skill_score, 85)  # Cap at 85 for fallback
        
        summary = f"Resume analysis completed. Found {skill_matches} matching skills out of {total_skills} identified skills."
        
        return base_score, summary

    async def test_connection(self) -> bool:
        """Test AI service connection"""
        try:
            user_message = UserMessage(text="Respond with 'AI Service Connected' and nothing else.")
            response = await self.chat.send_message(user_message)
            return "connected" in response.lower()
        except Exception as e:
            logger.error(f"AI connection test failed: {str(e)}")
            return False