import json
from itertools import chain
from datetime import datetime

from openai import BaseModel
from utils.tools import StringCard
from utils.config import template_dir
from nonebot_plugin_htmlrender import template_to_pic
from utils.models import User, Curriculum, CurriculumConfig, ShareCurriculumConfig

from .typings import CurriculumType


class BaseCurriculum:
    def __init__(self, user: User):
        self.user = user
        # 今天加一天
        self.today = datetime.now()
        self.weekday = self.today.weekday() + 1
        self._config: CurriculumConfig | None = None

    async def get_config(self, is_classes: bool = False) -> CurriculumConfig | None:
        if self._config is None:
            if is_classes and self.user.student:
                self._config = await self.user.student.classes.get_curriculum_config()
            else:
                self._config = await self.user.get_curriculum_config()
        return self._config


class CurriculumRender(BaseModel):
    id: int
    week: list[int]
    weekday: list[int]
    lesson: list[int]
    course: str
    classroom: str | None
    teacher: str | None
    current_week: int
    today: datetime
    type: CurriculumType

    def is_week(self, week: int) -> bool:
        return week in self.week

    def is_day(self, day: int) -> bool:
        """范围是1-7"""
        print(day, self.weekday, self.id)
        return day in self.weekday

    def is_lesson(self, lesson: int) -> bool:
        return lesson in self.lesson

    def is_current_week(self, week: int | None = None) -> bool:
        """是否为本周"""
        if week is None:
            return self.current_week in self.week
        return self.current_week == week

    def is_past_week(self, week: int) -> bool:
        """是否为过去的周"""
        return self.current_week > week

    @property
    def type_str(self):
        if self.type == CurriculumType.private:
            return "个人"
        elif self.type == CurriculumType.share:
            return "共享"
        elif self.type == CurriculumType.classes:
            return "班级"
        return "未知"

    # 是否是今天的课程
    def is_today(self, day: int | None = None) -> bool:
        return self.is_current_week() and self.is_day(
            day if day is not None else self.today.weekday() + 1
        )

    def is_end(self) -> bool:
        """是否已经结束"""
        return self.current_week > max(self.week)


class AddCurriculum(BaseCurriculum):
    async def add(
        self,
        week: list[int],
        weekday: list[int],
        lesson: list[int],
        course: str,
        classroom: str | None = None,
        teacher: str | None = None,
        is_classes: bool = False,
    ) -> Curriculum | None:
        # 获取用户自己的课表配置,如果没有就创建一个
        if not is_classes:
            if (config := await self.get_config()) is None:
                config = await CurriculumConfig(user_id=self.user.id).create()
        elif self.user.student and (config := await self.get_config(True)) is None:
            config = await CurriculumConfig(
                classes_id=self.user.student.classes.id
            ).create()
        elif config is None:
            return None

        curriculum = await Curriculum(
            week=json.dumps(week),
            weekday=json.dumps(weekday),
            lesson=json.dumps(lesson),
            course=course,
            teacher=teacher,
            classroom=classroom,
            config=config,
        ).create()
        return curriculum


class QueryCurriculum(BaseCurriculum):
    _curriculums: dict[CurriculumType, list[Curriculum]] | None = None

    async def get_configs(self):
        """获取到于用户相关的课表配置"""

        # 拿到共享的课表配置
        configs = await CurriculumConfig.filter(user_id=self.user.id).all()
        # 如果用户是学生则获取班级的课表配置
        if self.user.student:
            configs += await CurriculumConfig.filter(
                classes_id=self.user.student.classes.id
            ).all()
        return configs

    async def get_curriculums(self) -> dict[CurriculumType, list[Curriculum]]:
        """获取到用户的课表"""
        if self._curriculums:
            return self._curriculums
        curriculums: dict[CurriculumType, list[Curriculum]] = {}

        for i in await ShareCurriculumConfig.filter(user=self.user).all():
            curriculums.setdefault(CurriculumType.share, []).extend(
                i.config.curriculums
            )

        for config in await self.get_configs():
            if config.classes_id:
                curriculums.setdefault(CurriculumType.classes, []).extend(
                    config.curriculums
                )
            else:
                curriculums.setdefault(CurriculumType.private, []).extend(
                    config.curriculums
                )
        self._curriculums = curriculums
        return curriculums

    async def get_today_curriculums(self) -> list[Curriculum]:
        """获取到今天的课程"""
        curriculums = await self.get_curriculums()
        day_curriculums = []
        for i in chain(*curriculums.values()):
            data = i.loads()
            if i.config.current_week in data["week"] and self.is_weekday(
                data["weekday"]
            ):
                day_curriculums.append(i)
        return day_curriculums

    def is_weekday(self, week: list[int]) -> bool:
        return self.weekday in week

    async def render(self):
        card = StringCard()
        for key, values in (await self.get_curriculums()).items():
            for index, value in enumerate(values):
                if not index:
                    if key == "private":
                        card.hr("个人课表")
                    elif key == "share":
                        card.hr("共享课表")
                    elif key == "classes":
                        card.hr("班级课表")
                else:
                    card.hr()
                data = value.loads()
                card.text(f"课程ID:", str(value.id))
                card.text(f"课程周期:", ",".join(str(i) for i in data["week"]))
                card.text(f"每周星期:", ",".join(str(i) for i in data["weekday"]))
                card.text(f"课程节数:", ",".join(str(i) for i in data["lesson"]))
                card.text(f"课程名称:", value.course)
                if value.classroom:
                    card.text(f"课程教室:", value.classroom)
                if value.teacher:
                    card.text(f"授课老师:", value.teacher)
        # 获取今天的课程
        if today_curriculums := await self.get_today_curriculums():
            for i, v in enumerate(today_curriculums):
                if not i:
                    card.hr("今日课程")
                else:
                    card.hr()
                data = v.loads()
                card.text(f"课程ID:", str(v.id))
                card.text(f"课程周期:", ",".join(str(i) for i in data["week"]))
                card.text(f"每周星期:", ",".join(str(i) for i in data["weekday"]))
                card.text(f"课程节数:", ",".join(str(i) for i in data["lesson"]))
                card.text(f"课程名称:", v.course)
                if v.classroom:
                    card.text(f"课程教室:", v.classroom)
                if v.teacher:
                    card.text(f"授课老师:", v.teacher)
        return card.render()

    @staticmethod
    def curriculum_to_dict(
        curriculum: Curriculum, type: CurriculumType, today: datetime
    ) -> CurriculumRender:
        data = curriculum.loads()
        return CurriculumRender(
            id=curriculum.id,
            week=data["week"],
            weekday=data["weekday"],
            lesson=data["lesson"],
            course=curriculum.course,
            classroom=curriculum.classroom,
            teacher=curriculum.teacher,
            type=type,
            today=today,
            current_week=curriculum.config.current_week,
        )

    async def render_pic(self) -> bytes:
        curriculums = await self.get_curriculums()
        # 从课表中获取最大的节次
        max_lesson = 0
        for values in curriculums.values():
            for value in values:
                data = value.loads()
                max_lesson = max(max(data["lesson"]), max_lesson)

        renders = [
            self.curriculum_to_dict(value, key, self.today)
            for key, values in curriculums.items()
            for value in values
        ]
        html = await template_to_pic(
            str(template_dir),
            "curriculum.html",
            {
                "renders": renders,
                "today": self.today,
                "lesson": list(range(1, max_lesson + 1)),
            },
        )
        return html

    @classmethod
    async def render_pic_by_curriculums(cls, curriculums: list[Curriculum]) -> bytes:
        # 从课表中获取最大的节次
        today = datetime.now()
        max_lesson = 0
        for value in curriculums:
            data = value.loads()
            max_lesson = max(max(data["lesson"]), max_lesson)

        renders = [
            cls.curriculum_to_dict(value, CurriculumType.classes, today)
            for value in curriculums
        ]
        html = await template_to_pic(
            str(template_dir),
            "curriculum.html",
            {
                "renders": renders,
                "today": today,
                "lesson": list(range(1, max_lesson + 1)),
            },
        )
        return html


class DeleteCurriculum(QueryCurriculum):
    async def delete(
        self, curriculum_id: list[int], is_classes: bool = False
    ) -> list[int]:
        if config := await self.get_config(is_classes):
            curriculums = config.curriculums
            ids = [i.id for i in curriculums]
            for i in curriculum_id.copy():
                if i in ids:
                    await Curriculum.filter(id=i).delete()
                    ids.remove(i)
                    curriculum_id.remove(i)
        return curriculum_id


class SetCurriculumWeek(BaseCurriculum):
    async def set_week(self, week: int, classes_id: int | None = None):
        if classes_id is None:
            if config := await self.get_config():
                await config.filter(id=config.id).update(current_week=week)
                return True

        # 获取用户的所有班级,判断是否有权限设置
        all_classes = []
        if self.user.student:
            all_classes.append(self.user.student.classes.id)
        if self.user.teacher:
            all_classes.extend([i.id for i in self.user.teacher.classes])
        if classes_id in all_classes:
            await CurriculumConfig.filter(classes_id=classes_id).update(
                current_week=week
            )
            return True
        return False


class ShareCurriculum(BaseCurriculum):
    async def share(self, config_id: int) -> None | bool:
        # 获取用户的课表配置
        if config := await CurriculumConfig.filter(id=config_id).first():
            # 查看是否已经分享过了
            if await ShareCurriculumConfig.filter(
                user=self.user, config=config
            ).first():
                return False
            elif (
                self_config := await self.get_config()
            ) and self_config.id == config.id:
                return False
            await ShareCurriculumConfig(user=self.user, config=config).create()
            return True
        return None
