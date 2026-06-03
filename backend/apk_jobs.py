import uuid
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ApkJob:
    job_id: str
    user_id: str
    apk_path: str
    status: str = "queued"      # queued | ready | navigating | processing | done | failed
    progress: int = 0
    message: str = ""
    screenshots: list = field(default_factory=list)  # image_ids after DB insert
    static_info: dict = field(default_factory=dict)
    error: Optional[str] = None

_jobs: dict[str, ApkJob] = {}

def create_job(user_id: str, apk_path: str) -> ApkJob:
    job = ApkJob(job_id=str(uuid.uuid4()), user_id=user_id, apk_path=apk_path)
    _jobs[job.job_id] = job
    return job

def get_job(job_id: str) -> Optional[ApkJob]:
    return _jobs.get(job_id)

def update_job(job_id: str, **kwargs) -> None:
    if job := _jobs.get(job_id):
        for k, v in kwargs.items():
            setattr(job, k, v)
