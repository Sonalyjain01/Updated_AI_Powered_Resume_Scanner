from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from typing import List, Optional
import os
from models import ResumeAnalysisResponse
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        self.db_name = os.getenv('DB_NAME', 'test_database')
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_url)
            self.db = self.client[self.db_name]
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {self.db_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")
    
    async def save_scan_result(self, scan_result: ResumeAnalysisResponse) -> str:
        """Save scan result to database"""
        try:
            collection = self.db.resume_scans
            
            # Convert Pydantic model to dict
            scan_dict = scan_result.dict()
            
            # Insert into database
            result = await collection.insert_one(scan_dict)
            
            logger.info(f"Saved scan result with ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error saving scan result: {str(e)}")
            raise
    
    async def get_scan_history(self, limit: int = 50, skip: int = 0) -> List[ResumeAnalysisResponse]:
        """Get scan history from database"""
        try:
            collection = self.db.resume_scans
            
            # Get documents with pagination
            cursor = collection.find().sort("created_at", -1).skip(skip).limit(limit)
            
            scan_results = []
            async for doc in cursor:
                # Remove MongoDB _id field
                doc.pop('_id', None)
                
                # Create ResumeAnalysisResponse object
                scan_result = ResumeAnalysisResponse(**doc)
                scan_results.append(scan_result)
            
            logger.info(f"Retrieved {len(scan_results)} scan results")
            return scan_results
            
        except Exception as e:
            logger.error(f"Error retrieving scan history: {str(e)}")
            return []
    
    async def get_total_scans_count(self) -> int:
        """Get total number of scans in database"""
        try:
            collection = self.db.resume_scans
            count = await collection.count_documents({})
            return count
            
        except Exception as e:
            logger.error(f"Error getting scan count: {str(e)}")
            return 0
    
    async def get_scan_by_id(self, scan_id: str) -> Optional[ResumeAnalysisResponse]:
        """Get specific scan by ID"""
        try:
            collection = self.db.resume_scans
            
            doc = await collection.find_one({"id": scan_id})
            
            if doc:
                doc.pop('_id', None)
                return ResumeAnalysisResponse(**doc)
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving scan by ID {scan_id}: {str(e)}")
            return None
    
    async def delete_scan(self, scan_id: str) -> bool:
        """Delete scan by ID"""
        try:
            collection = self.db.resume_scans
            
            result = await collection.delete_one({"id": scan_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted scan with ID: {scan_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting scan {scan_id}: {str(e)}")
            return False

# Global database instance
database = Database()