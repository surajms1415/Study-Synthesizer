from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class DocumentContent(BaseModel):
    document_id: str
    document_name: str
    source_type: str # 'youtube', 'pdf', 'docx', 'pptx', 'web'
    text: str
    sections: List[Dict[str, Any]] = [] 
    metadata: Dict[str, Any] = {}
