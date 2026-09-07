from fastapi import Header, HTTPException

from core.config import settings


def _get_valid_api_keys() -> list[str]:
    """获取有效的API Key列表"""
    if not settings.api_keys:
        return []
    return [key.strip() for key in settings.api_keys.split(",") if key.strip()]


async def verify_api_key(authorization: str | None = Header(None)) -> str:
    """验证API Key

    从请求头中获取 Authorization: Bearer {API_KEY} 格式的认证信息，
    并验证API Key是否在配置文件的api_keys列表中。

    Args:
        authorization: 请求头中的Authorization字段值

    Returns:
        验证通过的API Key字符串

    Raises:
        HTTPException: 认证失败时抛出异常
            - status_code=401, error_code=1001: 无效的Authorization请求头格式
            - status_code=403, error_code=1002: API Key不在允许列表中
    """
    # 检查Authorization头是否存在
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail={"error_code": 1001, "error_msg": "缺少Authorization请求头"},
        )

    # 验证Authorization格式 (Bearer {API_KEY})
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail={"error_code": 1001, "error_msg": "无效的Authorization请求头格式"},
        )

    api_key = parts[1]

    # 获取有效的API Key列表并验证
    valid_keys = _get_valid_api_keys()
    if not valid_keys or api_key not in valid_keys:
        raise HTTPException(
            status_code=403,
            detail={"error_code": 1002, "error_msg": "认证失败"},
        )

    return api_key
