from utils.models.models import User, ScheduledNotice
from utils.tools import StringCard


class QueryNotice:
    def __init__(self, user: User) -> None:
        self.user = user

    async def get_notices(self) -> list[ScheduledNotice]:
        """获取到与用户相关的所有通知"""
        return await ScheduledNotice.filter(creator=self.user).all()
    
    def render_string(self, notices: list[ScheduledNotice]) -> str:
        card = StringCard("通知列表")
        for notice in notices:
            card.hr("NID: " + str(notice.id))
            card.text("通知标题:", notice.title)
            card.text("通知时间:", notice.notice_time.strftime("%Y-%m-%d %H:%M:%S"))
        return card.render()


class DeleteNotice(QueryNotice):
    async def get_notice(self, notice_id: int) -> ScheduledNotice | None:
        """获取到通知"""
        return await ScheduledNotice.filter(creator=self.user, id=notice_id).first()

    async def delete_notice(self, notice_id: int | ScheduledNotice) -> bool:
        """删除通知"""
        notice: ScheduledNotice | None = None
        if isinstance(notice_id, int):
            notice = await self.get_notice(notice_id)
        else:
            notice = notice_id

        if notice:
            await notice.filter(id=notice.id).delete()
            return True  # 删除成功
        return False  # 删除失败
