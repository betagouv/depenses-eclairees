import logging
from unittest import mock

import pytest

from docia.file_processing.models import ProcessDocumentStep, ProcessingStatus
from docia.file_processing.pipeline.steps.base import AbstractStepRunner
from tests.factories.file_processing import ProcessDocumentStepFactory


class DummyStepRunner(AbstractStepRunner):
    def process(self, step: ProcessDocumentStep) -> ProcessingStatus:
        return ProcessingStatus.SUCCESS


@pytest.mark.django_db
def test_running_step():
    step = ProcessDocumentStepFactory(step_type="dummy_step")
    runner = DummyStepRunner()
    runner.run(step.id)
    step.refresh_from_db()
    assert step.status == ProcessingStatus.SUCCESS


def _test_skip(step, caplog):
    updated_at = step.updated_at
    runner = DummyStepRunner()
    with (
        mock.patch.object(runner, "process", return_value=ProcessingStatus.FAILURE, autospec=True) as m,
        caplog.at_level(logging.INFO, logger="docia"),
    ):
        runner.run(step.id)
        m.assert_not_called()
    step.refresh_from_db()
    assert step.updated_at == updated_at


@pytest.mark.parametrize(
    "status",
    [status for status, _ in ProcessingStatus.choices if status != ProcessingStatus.PENDING],
)
@pytest.mark.django_db
def test_skip_if_not_pending(status, caplog):
    step = ProcessDocumentStepFactory(step_type="dummy_step", status=status)
    _test_skip(step, caplog)
    assert "Step already processed" in caplog.text
    assert step.status == status


@pytest.mark.django_db
def test_skip_if_job_cancelled(caplog):
    step = ProcessDocumentStepFactory(
        step_type="dummy_step",
        status=ProcessingStatus.PENDING,
        job__status=ProcessingStatus.CANCELLED,
    )
    _test_skip(step, caplog)
    assert "Job cancelled" in caplog.text
    assert step.status == ProcessingStatus.PENDING


@pytest.mark.parametrize(
    "status",
    [
        ProcessingStatus.SUCCESS,
        ProcessingStatus.FAILURE,
        ProcessingStatus.SKIPPED,
    ],
)
@pytest.mark.django_db
def test_skip_if_job_already_processed(status, caplog):
    step = ProcessDocumentStepFactory(
        step_type="dummy_step",
        status=ProcessingStatus.PENDING,
        job__status=status,
    )
    _test_skip(step, caplog)
    assert "Job already processed" in caplog.text
    assert step.status == ProcessingStatus.PENDING
