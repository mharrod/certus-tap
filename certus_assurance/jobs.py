from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from certus_assurance.logs import LogStream
from certus_assurance.models import PipelineResult, ScanRequest
from certus_assurance.settings import settings


class ScanStatus:
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class ScanJob:
    test_id: str
    workspace_id: str
    component_id: str
    assessment_id: str
    git_url: str
    branch: str | None
    commit: str | None
    requested_by: str | None
    source_type: str = "git"
    directory_path: str | None = None
    archive_path: str | None = None
    profile: str = "light"
    status: str = ScanStatus.QUEUED
    started_at: float | None = None
    completed_at: float | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    upload_status: str = "pending"
    upload_permission_id: str | None = None
    verification_proof: dict[str, Any] | None = None
    manifest_digest: str | None = None


class ScanJobManager:
    def __init__(self, max_workers: int | None = None):
        self._jobs: dict[str, ScanJob] = {}
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers or settings.max_workers,
            thread_name_prefix="certus-assurance",
        )

    def list_jobs(self) -> list[ScanJob]:
        with self._lock:
            return list(self._jobs.values())

    def get_job(self, test_id: str) -> ScanJob | None:
        with self._lock:
            job = self._jobs.get(test_id)
            if not job:
                return None
            return job

    def submit(
        self,
        workspace_id: str,
        component_id: str,
        assessment_id: str,
        git_url: str,
        branch: str | None,
        commit: str | None,
        requested_by: str | None,
        profile: str,
        manifest_text: str | None,
        manifest_path: str | None,
        manifest_uri: str | None,
        manifest_signature_uri: str | None,
        manifest_digest: str | None,
        log_stream: LogStream | None,
        runner_fn: Callable[[ScanRequest], PipelineResult],
        *,
        source_type: str = "git",
        directory_path: str | None = None,
        archive_path: str | None = None,
        test_id: str | None = None,
    ) -> ScanJob:
        test_id = test_id or self._generate_test_id()
        job = ScanJob(
            test_id=test_id,
            workspace_id=workspace_id,
            component_id=component_id,
            assessment_id=assessment_id,
            git_url=git_url,
            branch=branch,
            commit=commit,
            requested_by=requested_by,
            source_type=source_type,
            directory_path=directory_path,
            archive_path=archive_path,
            profile=profile,
        )
        request = ScanRequest(
            test_id=test_id,
            workspace_id=workspace_id,
            component_id=component_id,
            assessment_id=assessment_id,
            source_type=source_type,
            git_url=git_url,
            branch=branch,
            commit=commit,
            directory_path=directory_path,
            archive_path=archive_path,
            requested_by=requested_by,
            profile=profile,
            manifest_text=manifest_text,
            manifest_path=manifest_path,
            manifest_uri=manifest_uri,
            manifest_signature_uri=manifest_signature_uri,
            manifest_digest=manifest_digest,
            log_stream=log_stream,
        )

        with self._lock:
            self._jobs[test_id] = job
            future = self._executor.submit(self._run_job, job, request, runner_fn)
            self._futures[test_id] = future
        return job

    def _run_job(self, job: ScanJob, request: ScanRequest, runner_fn: Callable[[ScanRequest], PipelineResult]) -> None:
        job.status = ScanStatus.RUNNING
        job.started_at = time.time()
        try:
            result = runner_fn(request)
            job.status = result.status or ScanStatus.SUCCEEDED
            job.artifacts = result.metadata.get("artifacts", {})
            job.warnings = result.metadata.get("warnings", [])
            job.errors = result.metadata.get("errors", [])
            job.metadata = result.metadata
            job.manifest_digest = result.manifest_digest or request.manifest_digest
        except Exception as exc:
            job.status = ScanStatus.FAILED
            job.errors.append(str(exc))
        finally:
            job.completed_at = time.time()

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

    def new_test_id(self) -> str:
        return self._generate_test_id()

    def _generate_test_id(self) -> str:
        return "test_" + uuid.uuid4().hex[:12]


job_manager = ScanJobManager()
