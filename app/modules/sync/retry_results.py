from typing import Any


def retry_summary(
    results: list[dict[str, Any]],
    *,
    remaining: int,
    stopped_on_error: bool | None = None,
) -> dict[str, Any]:
    return {
        "attempted": len(results),
        "synced": sum(1 for result in results if result["success"]),
        "failed": sum(1 for result in results if not result["success"]),
        "remaining": remaining,
        "stopped_on_error": (
            any(not result["success"] for result in results)
            if stopped_on_error is None
            else stopped_on_error
        ),
        "results": results,
    }
