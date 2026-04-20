from fastapi import HTTPException


def assert_transition(current_status: str, allowed_from: set[str], action: str):
    """Enforce state-machine transitions across business actions."""
    if current_status not in allowed_from:
        allowed_text = ", ".join(sorted(allowed_from))
        raise HTTPException(
            status_code=400,
            detail=f"当前状态为 {current_status}，仅允许在 [{allowed_text}] 执行动作：{action}",
        )


def assert_positive(value: float, field_name: str):
    if value is None or value <= 0:
        raise HTTPException(status_code=400, detail=f"{field_name} 必须大于 0")
