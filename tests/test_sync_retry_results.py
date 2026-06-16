from app.modules.sync.retry_results import retry_summary


def test_retry_summary_uses_explicit_stopped_on_error():
    results = [
        {"success": True},
        {"success": False},
    ]

    assert retry_summary(results, remaining=3, stopped_on_error=False) == {
        "attempted": 2,
        "synced": 1,
        "failed": 1,
        "remaining": 3,
        "stopped_on_error": False,
        "results": results,
    }


def test_retry_summary_defaults_stopped_on_error_from_failed_results():
    assert retry_summary([{"success": True}], remaining=0)["stopped_on_error"] is False
    assert retry_summary([{"success": False}], remaining=1)["stopped_on_error"] is True
