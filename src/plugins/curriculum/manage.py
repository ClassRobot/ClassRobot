from datetime import datetime

from utils.models import User, Curricula, CurriculaConfig, ShareCurriculaConfig

from .schema import CurriculaSchema


class BaseCurricula:
    """定义课表管理流程共享的基础能力。"""
    def __init__(self, user: User) -> None:
        """初始化实例。

        参数:
            user (User): 当前用户对象。
        """
        self.user = user
        self.today = datetime.now()
        self.weekday = self.today.weekday() + 1

    async def get_user_config(self) -> CurriculaConfig | None:
        """获取用户配置。"""
        return await CurriculaConfig.filter(user=self.user).first()

    async def get_classes_config(self, name: str | None) -> CurriculaConfig | None:
        """获取班级配置。

        参数:
            name (str | None): 名称。

        返回:
            CurriculaConfig | None: 返回处理结果。
        """
        if name:
            return await CurriculaConfig.filter(name=name).first()
        elif self.user.student:
            return await CurriculaConfig.filter(classes=self.user.student.classes).first()
        return None

    async def get_share_config(self) -> list[CurriculaConfig]:
        """获取shareconfig。"""
        return [share.config for share in await ShareCurriculaConfig.filter(user=self.user).all()]


class AddCurricula(BaseCurricula):
    """负责新增课表记录的业务处理。"""
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
        """处理添加相关逻辑。

        参数:
            weeks (list[int]): 周次。
            weekday (list[int]): weekday。
            lesson (list[int]): lesson。
            course (str): course。
            classroom (str | None): classroom。
            teacher (str | None): 当前教师对象。

        返回:
            Curricula | None: 返回处理结果。
        """
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
    """负责查询课表信息的业务处理。"""
    async def query(self, name: str | None = None, day: int = 0) -> None | CurriculaSchema:
        """调用该方法来查询课表

        参数:
            name (str | None): 名称。
            day (int): 天数偏移。

        返回:
            None | CurriculaSchema: 返回处理结果。
        """
        if name is None:
            if user_config := await self.get_user_config():
                return await CurriculaSchema.prase(user_config, await user_config.get_curricula(), day)
            elif share_config := await self.get_share_config():
                return await CurriculaSchema.prase(share_config[0], await share_config[0].get_curricula(), day)
        if config := await self.get_classes_config(name) if name else await self.get_user_config():
            return await CurriculaSchema.prase(config, await config.get_curricula(), day)


class DeleteCurricula(QueryCurricula):
    """负责删除课表记录的业务处理。"""
    async def delete(self, curricula_id: list[int]) -> list[int]:
        """删除当前数据。

        参数:
            curricula_id (list[int]): 课表标识。

        返回:
            list[int]: 返回处理结果。
        """
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
    """负责设置当前课表周次的业务处理。"""
    async def set_week(self, week: int) -> bool:
        """设置周次。

        参数:
            week (int): 周次。

        返回:
            bool: 表示是否成功。
        """
        if config := await self.get_user_config():
            await config.filter(id=config.id).update(current_week=week)
            return True
        return False


class ShareCurricula(BaseCurricula):
    """负责共享课表配置的业务处理。"""
    async def share(self, config_id: int | CurriculaConfig) -> None | bool:
        # 获取用户的课表配置
        """处理share相关逻辑。

        参数:
            config_id (int | CurriculaConfig): 配置标识。

        返回:
            None | bool: 返回处理结果。
        """
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
