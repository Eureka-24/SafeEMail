"""
Action 枚举定义（服务端使用）
"""
from shared.protocol import Action, StatusCode

# 不需要认证的 Action 列表
PUBLIC_ACTIONS = {
    Action.PING,
    Action.REGISTER,
    Action.LOGIN,
}
