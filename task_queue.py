#!/usr/bin/env python3
"""
Background Task Queue for JD Parser & Resume Tailoring Pipeline

Handles long-running operations asynchronously to improve web interface responsiveness:
1. LLM processing tasks
2. PDF compilation
3. Skills extraction
4. Resume updates

Uses threading for background processing with status tracking.
"""

import asyncio
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import queue


class TaskStatus(Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """Task data structure"""
    id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskQueue:
    """Background task queue with status tracking"""

    def __init__(self, max_workers: int = 4, task_timeout: int = 1800):
        self.max_workers = max_workers
        self.task_timeout = task_timeout
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, Task] = {}
        self.task_queue = queue.Queue()
        self.running = True

        # Start background worker
        self.worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _worker_loop(self):
        """Background worker loop"""
        while self.running:
            try:
                # Get task from queue with timeout
                task_data = self.task_queue.get(timeout=1.0)
                if task_data is None:  # Shutdown signal
                    break

                task_id, func, args, kwargs = task_data
                self._execute_task(task_id, func, args, kwargs)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Worker loop error: {e}")

    def _execute_task(self, task_id: str, func: Callable, args: tuple, kwargs: dict):
        """Execute a single task"""
        task = self.tasks.get(task_id)
        if not task:
            return

        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

            # Execute the task
            result = func(*args, **kwargs)

            # Update task with success
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.progress = 100.0
            task.result = result

        except Exception as e:
            # Update task with error
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)

    def submit_task(self, task_type: str, func: Callable, *args,
                    metadata: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """Submit a task for background execution"""
        task_id = str(uuid.uuid4())

        # Create task record
        task = Task(
            id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            metadata=metadata or {}
        )

        # Store task
        self.tasks[task_id] = task

        # Submit to queue
        self.task_queue.put((task_id, func, args, kwargs))

        return task_id

    def get_task_status(self, task_id: str) -> Optional[Task]:
        """Get task status by ID"""
        return self.tasks.get(task_id)

    def get_tasks_by_type(self, task_type: str) -> List[Task]:
        """Get all tasks of a specific type"""
        return [task for task in self.tasks.values() if task.task_type == task_type]

    def get_recent_tasks(self, hours: int = 24) -> List[Task]:
        """Get tasks created within the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [task for task in self.tasks.values() if task.created_at >= cutoff]

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            return True
        return False

    def cleanup_old_tasks(self, hours: int = 24) -> int:
        """Remove old completed/failed tasks"""
        cutoff = datetime.now() - timedelta(hours=hours)
        removed_count = 0

        task_ids_to_remove = []
        for task_id, task in self.tasks.items():
            if (task.created_at < cutoff and
                    task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]):
                task_ids_to_remove.append(task_id)

        for task_id in task_ids_to_remove:
            del self.tasks[task_id]
            removed_count += 1

        return removed_count

    def shutdown(self):
        """Shutdown the task queue"""
        self.running = False
        self.task_queue.put(None)  # Signal worker to stop
        self.executor.shutdown(wait=True)

    def get_stats(self) -> Dict[str, Any]:
        """Get task queue statistics"""
        stats = {
            'total_tasks': len(self.tasks),
            'by_status': {},
            'by_type': {},
            'recent_completion_rate': 0.0
        }

        # Count by status
        for task in self.tasks.values():
            status = task.status.value
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

            task_type = task.task_type
            stats['by_type'][task_type] = stats['by_type'].get(
                task_type, 0) + 1

        # Calculate recent completion rate
        recent_tasks = self.get_recent_tasks(1)  # Last hour
        if recent_tasks:
            completed = sum(
                1 for t in recent_tasks if t.status == TaskStatus.COMPLETED)
            stats['recent_completion_rate'] = completed / len(recent_tasks)

        return stats


# Global task queue instance
_task_queue = None


def get_task_queue() -> TaskQueue:
    """Get the global task queue instance"""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue


def submit_llm_task(prompt: str, model: str, base_url: str, api_key: str) -> str:
    """Submit an LLM processing task"""
    # Import the module with the correct filename
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "jd_parser", "jd-parser.py")
        jd_parser = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(jd_parser)
    except Exception as e:
        print(f"Failed to import jd-parser module: {e}")
        raise ImportError(f"Could not import jd-parser module: {e}")

    import asyncio

    def llm_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                jd_parser.chat_once(base_url, api_key, model, [
                    {"role": "user", "content": prompt}], {})
            )
        finally:
            loop.close()

    queue = get_task_queue()
    return queue.submit_task(
        "llm_processing",
        llm_worker,
        metadata={"prompt_length": len(prompt), "model": model}
    )


def submit_pdf_compilation_task(tex_file_path: str, output_dir: str) -> str:
    """Submit a PDF compilation task"""
    from pdf_utils import compile_latex_to_pdf

    queue = get_task_queue()
    return queue.submit_task(
        "pdf_compilation",
        compile_latex_to_pdf,
        tex_file_path,
        output_dir,
        metadata={"tex_file": tex_file_path}
    )


def submit_skills_extraction_task(jd_content: str) -> str:
    """Submit a skills extraction task (caching disabled for data integrity)"""
    # Caching disabled due to data integrity issues

    def skills_worker():
        print("⚙️ Processing job description (caching disabled)")

        # Import the module with the correct filename
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "jd_parser", "jd-parser.py")
            jd_parser = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(jd_parser)
        except Exception as e:
            print(f"Failed to import jd-parser module: {e}")
            raise ImportError(f"Could not import jd-parser module: {e}")

        import tempfile

        # Create temporary JD file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(jd_content)
            temp_jd_path = f.name

        try:
            # Run JD parser using subprocess (more reliable)
            import subprocess
            import sys
            
            result = subprocess.run([
                sys.executable, 'jd-parser.py', '--jd', temp_jd_path
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            if result.returncode != 0:
                raise Exception(f"JD parser failed: {result.stderr}")

            # Read results
            from pathlib import Path
            import json

            artifacts_path = Path('artifacts/jd_skills.json')
            if artifacts_path.exists():
                with open(artifacts_path, 'r') as f:
                    result = json.load(f)

                return result
            else:
                raise Exception(
                    "Skills extraction failed - no output file generated")

        finally:
            # Clean up temp file
            Path(temp_jd_path).unlink(missing_ok=True)

    queue = get_task_queue()
    return queue.submit_task(
        "skills_extraction",
        skills_worker,
        metadata={"jd_length": len(jd_content)}
    )


def get_task_result(task_id: str, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Get task result, optionally waiting for completion"""
    queue = get_task_queue()
    task = queue.get_task_status(task_id)

    if not task:
        return None

    if timeout:
        # Wait for completion
        start_time = time.time()
        while task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            if time.time() - start_time > timeout:
                break
            time.sleep(0.1)
            task = queue.get_task_status(task_id)

    if task.status == TaskStatus.COMPLETED:
        return task.result
    elif task.status == TaskStatus.FAILED:
        return {"error": task.error}
    else:
        return {"status": task.status.value}


def cleanup_old_tasks() -> int:
    """Clean up old completed tasks"""
    queue = get_task_queue()
    return queue.cleanup_old_tasks()


def get_queue_stats() -> Dict[str, Any]:
    """Get task queue statistics"""
    queue = get_task_queue()
    return queue.get_stats()
