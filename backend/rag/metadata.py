import hashlib
from typing import Dict, Any

def generate_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def sanitize_metadata(metadata: Dict[str, Any], content_hash: str) -> Dict[str, Any]:
    sanitized = {}
    for k, v in metadata.items():
        # ChromaDB only supports str, int, float, bool
        if v is not None and isinstance(v, (str, int, float, bool)):
            sanitized[k] = v
        elif v is not None:
            sanitized[k] = str(v)
    sanitized['content_hash'] = content_hash
    return sanitized
