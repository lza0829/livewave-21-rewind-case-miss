"""水位线回退禁改（已实现，架构甲：禁止变小）

全局口径：水位事件时单调不减。把水位改小的请求**整票拒绝**——水位不变、已关闭窗保持关闭、
旁路界不变。只读裁决走 `GET /api/水位变小/审查`，写闸走 `POST /api/水位变小`，
入流装载在事务内统一经 `守卫写水位` 推进水位并同事务关窗。

邻题扩展点已升格为主链护栏；见 app/services/水位闸.py。
"""
状态 = "已实现"
口径 = "禁止变小"
只读接口 = "GET /api/水位变小/审查?房间键=&新值="
写闸接口 = "POST /api/水位变小"


def 审查(房间键: str, 新值: str) -> dict:
    from app.services import 水位闸

    return 水位闸.审查(房间键, 新值)


def 提交(房间键: str, 新值: str, 处理时: str | None = None) -> dict:
    from app.services import 水位闸

    return 水位闸.提交(房间键, 新值, 处理时)
