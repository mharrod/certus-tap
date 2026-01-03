from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from certus_assurance.jobs import ScanJobManager, ScanStatus
from certus_assurance.models import ArtifactBundle, PipelineResult, ScanRequest


@pytest.fixture()
def job_manager() -> ScanJobManager:
    manager = ScanJobManager(max_workers=1)
    yield manager
    manager.shutdown()


def _fake_pipeline_result(tmp_path: Path, request: ScanRequest) -> PipelineResult:
    root = tmp_path / request.test_id
    (root / "reports" / "sast").mkdir(parents=True, exist_ok=True)
    sarif = root / "reports" / "sast" / "trivy.sarif.json"
    sarif.write_text("{}", encoding="utf-8")
    metadata_file = root / "scan.json"
    metadata_file.write_text(
        json.dumps({
            "test_id": request.test_id,
            "workspace_id": request.workspace_id,
            "component_id": request.component_id,
            "assessment_id": request.assessment_id,
        }),
        encoding="utf-8",
    )
    bundle = ArtifactBundle.discover(root)
    metadata = {
        "test_id": request.test_id,
        "workspace_id": request.workspace_id,
        "component_id": request.component_id,
        "assessment_id": request.assessment_id,
        "status": "SUCCEEDED",
        "artifacts": bundle.artifact_map(),
        "warnings": ["placeholder"],
        "errors": [],
    }
    return PipelineResult(
        test_id=request.test_id,
        workspace_id=request.workspace_id,
        component_id=request.component_id,
        assessment_id=request.assessment_id,
        status="SUCCEEDED",
        artifacts=bundle,
        steps=[],
        metadata=metadata,
        manifest_digest=request.manifest_digest,
    )


def test_job_manager_runs_pipeline(tmp_path: Path, job_manager: ScanJobManager) -> None:
    def runner_fn(request: ScanRequest) -> PipelineResult:
        return _fake_pipeline_result(tmp_path, request)

    job = job_manager.submit(
        "workspace-1",
        "component-1",
        "assessment-1",
        "https://example.com/repo.git",
        None,
        None,
        "tester",
        "light",
        "{}",
        None,
        None,
        None,
        "deadbeef",
        None,
        runner_fn,
        test_id="test-job-1",
    )

    _wait_for_completion(job)

    assert job.status == ScanStatus.SUCCEEDED
    assert job.artifacts["sarif"].endswith("trivy.sarif.json")
    assert job.warnings == ["placeholder"]
    assert job.errors == []
    assert job.metadata["test_id"] == job.test_id


def test_job_manager_records_failures(job_manager: ScanJobManager) -> None:
    def failing_runner(_: ScanRequest) -> PipelineResult:
        raise RuntimeError("boom")

    job = job_manager.submit(
        "workspace-1",
        "component-1",
        "assessment-1",
        "https://example.com/repo.git",
        None,
        None,
        "tester",
        "light",
        "{}",
        None,
        None,
        None,
        "deadbeef",
        None,
        failing_runner,
        test_id="test-job-2",
    )

    _wait_for_completion(job)

    assert job.status == ScanStatus.FAILED
    assert job.completed_at is not None
    assert job.errors and "boom" in job.errors[0]


def _wait_for_completion(job) -> None:
    for _ in range(200):
        if job.completed_at:
            return
        time.sleep(0.01)
    raise AssertionError("job did not complete in time")
