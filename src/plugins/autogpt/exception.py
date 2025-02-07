# 会话锁
class SessionLockError(Exception):
    """一次聊天还未结束就开始了新的聊天。"""
