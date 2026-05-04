from .router import router

# 仅对外暴露管理端路由对象，避免调用方依赖内部实现模块。
__all__ = ["router"]
