from src.shared.tools import StringCard
from src.models import User, ScheduledNotice


class QueryNotice:
    """负责查询通知内容的业务处理。"""

    def __init__(self, user: User) -> None:
        """初始化实例。

        参数:
            user (User): 当前用户对象。
        """
        self.user = user

    async def get_notices(self) -> list[ScheduledNotice]:
        """获取到与用户相关的所有通知"""
        return await ScheduledNotice.filter(creator=self.user).all()

    def render_string(self, notices: list[ScheduledNotice]) -> str:
        """渲染string。

        参数:
            notices (list[ScheduledNotice]): 通知。

        返回:
            str: 返回字符串结果。
        """
        card = StringCard("通知列表")
        for notice in notices:
            card.hr("NID: " + str(notice.id))
            card.text("通知标题:", notice.title)
            card.text("通知时间:", notice.notice_time.strftime("%Y-%m-%d %H:%M:%S"))
        return card.render()


class DeleteNotice(QueryNotice):
    """负责删除通知记录的业务处理。"""

    async def get_notice(self, notice_id: int) -> ScheduledNotice | None:
        """获取到通知

        参数:
            notice_id (int): 通知标识。

        返回:
            ScheduledNotice | None: 返回处理结果。
        """
        return await ScheduledNotice.filter(creator=self.user, id=notice_id).first()

    async def delete_notice(self, notice_id: int | ScheduledNotice) -> bool:
        """删除通知

        参数:
            notice_id (int | ScheduledNotice): 通知标识。

        返回:
            bool: 表示是否成功。
        """
        notice: ScheduledNotice | None = None
        if isinstance(notice_id, int):
            notice = await self.get_notice(notice_id)
        else:
            notice = notice_id

        if notice:
            await notice.filter(id=notice.id).delete()
            return True  # 删除成功
        return False  # 删除失败
