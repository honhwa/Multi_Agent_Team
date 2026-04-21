from __future__ import annotations

from app import session_context


def _session_with_checkpoint() -> dict[str, object]:
    return {
        "agent_state": {
            "task_checkpoint": {
                "task_id": "task-1",
                "goal": "Inspect current code",
                "project_root": "/tmp/demo",
                "cwd": "/tmp/demo",
                "active_files": ["/tmp/demo/app.py"],
                "active_attachments": [],
                "last_completed_step": "read: app.py",
                "next_action": "patch app.py",
            }
        },
        "route_state": {},
    }


def test_should_start_new_task_for_explicit_new_request() -> None:
    session = _session_with_checkpoint()

    assert session_context.should_start_new_task(session, message="另外帮我看个新问题", requested_attachment_ids=[]) is True


def test_should_not_start_new_task_for_current_folder_followup() -> None:
    session = _session_with_checkpoint()

    assert session_context.should_start_new_task(session, message="就在当前文件夹", requested_attachment_ids=[]) is False


def test_should_not_start_new_task_for_short_modify_followup_when_active_file_exists() -> None:
    session = _session_with_checkpoint()

    assert session_context.should_start_new_task(session, message="修一下", requested_attachment_ids=[]) is False


def test_should_not_start_new_task_for_short_file_target_followup() -> None:
    session = _session_with_checkpoint()

    assert session_context.should_start_new_task(session, message="修改 app.py", requested_attachment_ids=[]) is False


def test_should_start_new_task_when_new_attachment_arrives_without_followup_language() -> None:
    session = _session_with_checkpoint()

    assert session_context.should_start_new_task(session, message="解释图片内容", requested_attachment_ids=["img-2"]) is True
