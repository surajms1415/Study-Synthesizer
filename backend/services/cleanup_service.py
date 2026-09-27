import os
import glob
import shutil
import asyncio
from datetime import datetime
from services.db_service import get_expired_documents, delete_document_record
from rag.retrieval import delete_document

ACTIVE_TASKS = set()

def mark_task_active(task_id: str):
    ACTIVE_TASKS.add(task_id)

def mark_task_inactive(task_id: str):
    if task_id in ACTIVE_TASKS:
        ACTIVE_TASKS.remove(task_id)

def safe_delete_file(path: str):
    try:
        # Ensure path is within managed temp/output directories to prevent traversal
        abs_path = os.path.abspath(path)
        base_temp = os.path.abspath("temp")
        base_output = os.path.abspath("output")
        
        if not (abs_path.startswith(base_temp) or abs_path.startswith(base_output)):
            print(f"Skipping unsafe deletion: {path}")
            return
            
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
    except Exception as e:
        print(f"Failed to delete {path}: {e}")

async def cleanup_task(task_id: str):
    """Deletes all temporary files and outputs associated with a task_id."""
    print(f"[Cleanup] Deleting temporary files for expired task {task_id}")
    
    # temp files
    patterns = [
        f"temp/{task_id}_*",
        f"output/{task_id}_*"
    ]
    
    for pattern in patterns:
        for file_path in glob.glob(pattern):
            safe_delete_file(file_path)

async def run_cleanup_job():
    print("[Cleanup] Running periodic cleanup job...")
    try:
        expired = get_expired_documents()
        
        # Group by task_id to avoid cleaning the same task multiple times
        expired_tasks = {}
        for d in expired:
            tid = d["task_id"]
            if tid not in expired_tasks:
                expired_tasks[tid] = []
            expired_tasks[tid].append(d["document_id"])
            
        for task_id, doc_ids in expired_tasks.items():
            if task_id in ACTIVE_TASKS:
                print(f"[Cleanup] Skipping active task {task_id}")
                continue
                
            # 1. Delete ChromaDB records
            for doc_id in doc_ids:
                try:
                    delete_document(doc_id)
                    delete_document_record(doc_id)
                except Exception as e:
                    print(f"Failed to delete document {doc_id} from ChromaDB/metadata: {e}")
            
            # 2. Delete Temporary Files
            await cleanup_task(task_id)
            
    except Exception as e:
        print(f"[Cleanup Error] {e}")

async def cleanup_loop():
    # Run initially
    await run_cleanup_job()
    
    # Run every 1 hour
    while True:
        await asyncio.sleep(3600)
        await run_cleanup_job()

def start_cleanup_service():
    asyncio.create_task(cleanup_loop())
