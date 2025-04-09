from datetime import datetime

from utils.models import User, Curricula, CurriculaConfig, ShareCurriculaConfig

from .schema import CurriculaSchema


class BaseCurricula:
    def __init__(self, user: User) -> None:
        self.user = user
        self.today = datetime.now()
        self.weekday = self.today.weekday() + 1

    async def get_user_config(self) -> CurriculaConfig | None:
        return await CurriculaConfig.filter(user=self.user).first()

    async def get_classes_config(self, name: str | None) -> CurriculaConfig | None:
        if name:
            return await CurriculaConfig.filter(name=name).first()
        elif self.user.student:
            return await CurriculaConfig.filter(classes=self.user.student.classes).first()
        return None

    async def get_share_config(self) -> list[CurriculaConfig]:
        return [share.config for share in await ShareCurriculaConfig.filter(user=self.user).all()]


class AddCurricula(BaseCurricula):
    async def add(
        self,
        weeks: list[int],
        weekday: list[int],
        lesson: list[int],
        course: str,
        classroom: str | None = None,
        teacher: str | None = None,
    ) -> Curricula | None:
        # 获取用户自己的课表配置,如果没有就创建一个
        if (config := await self.get_user_config()) is None:
            config = await CurriculaConfig(user=self.user).create()

        return await Curricula(
            weeks=weeks,
            weekday=weekday,
            lesson=lesson,
            course=course,
            teacher=teacher,
            classroom=classroom,
            config_id=config.id,
        ).create()


class QueryCurricula(BaseCurricula):
    async def query(self, name: str | None = None) -> None | CurriculaSchema:
        """调用该方法来查询课表"""
        if name is None:
            if user_config := await self.get_user_config():
                return await CurriculaSchema.prase(user_config, await user_config.get_curricula())
            elif share_config := await self.get_share_config():
                return await CurriculaSchema.prase(share_config[0], await share_config[0].get_curricula())
        if config := await self.get_classes_config(name) if name else await self.get_user_config():
            return await CurriculaSchema.prase(config, await config.get_curricula())


class DeleteCurricula(QueryCurricula):
    async def delete(self, curricula_id: list[int]) -> list[int]:
        if config := await self.get_user_config():
            curricula = await config.get_curricula()
            ids = [i.id for i in curricula]
            for i in curricula_id.copy():
                if i in ids:
                    await Curricula.filter(id=i).delete()
                    ids.remove(i)
                    curricula_id.remove(i)
        return curricula_id


class SetCurriculaWeek(BaseCurricula):
    async def set_week(self, week: int) -> bool:
        if config := await self.get_user_config():
            await config.filter(id=config.id).update(current_week=week)
            return True
        return False


class ShareCurricula(BaseCurricula):
    async def share(self, config_id: int | CurriculaConfig) -> None | bool:
        # 获取用户的课表配置
        if isinstance(config_id, CurriculaConfig):
            config = config_id
        if isinstance(config, CurriculaConfig) or (config := await CurriculaConfig.filter(id=config_id).first()):
            # 查看是否已经分享过了
            if await ShareCurriculaConfig.filter(user=self.user, config=config).first():
                return False
            elif (self_config := await self.get_user_config()) and self_config.id == config.id:
                return False
            await ShareCurriculaConfig(user=self.user, config=config).create()
            return True
        return None
