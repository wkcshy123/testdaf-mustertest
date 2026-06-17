"""本地后台生成任务管理。"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from uuid import uuid4


@dataclass
class GenerationJob:
    id: str
    name: str
    status: str = "queued"
    step: str = "等待开始"
    progress: int = 0
    result_url: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class JobManager:
    """以内存方式管理本地生成任务，允许多个单题并行生成。"""

    def __init__(self, max_workers: int = 3):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, GenerationJob] = {}
        self._lock = Lock()

    def create(self, name: str) -> str:
        job_id = f"job_{uuid4().hex[:12]}"
        with self._lock:
            self._jobs[job_id] = GenerationJob(id=job_id, name=name)
        return job_id

    def start(self, job_id: str, func) -> None:
        self._executor.submit(self._run, job_id, func)

    def update(self, job_id: str, *, status: str | None = None, step: str | None = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if status:
                job.status = status
            if step:
                job.step = step
            job.updated_at = datetime.now().isoformat(timespec="seconds")

    def set_progress(self, job_id: str, progress: int, step: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.progress = max(0, min(100, progress))
            job.step = step
            job.updated_at = datetime.now().isoformat(timespec="seconds")

    def complete(self, job_id: str, result_url: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "success"
            job.step = "生成完成"
            job.progress = 100
            job.result_url = result_url
            job.updated_at = datetime.now().isoformat(timespec="seconds")

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "failed"
            job.step = "生成失败"
            job.error = error
            job.updated_at = datetime.now().isoformat(timespec="seconds")

    def get(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs[job_id]
            return {
                "id": job.id,
                "name": job.name,
                "status": job.status,
                "step": job.step,
                "progress": job.progress,
                "result_url": job.result_url,
                "error": job.error,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }

    def _run(self, job_id: str, func) -> None:
        try:
            self.update(job_id, status="running", step="开始生成")
            result_url = func()
            self.complete(job_id, result_url)
        except Exception as exc:
            self.fail(job_id, str(exc))
