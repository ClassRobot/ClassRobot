from itertools import repeat, product
from datetime import datetime, timedelta

from pydantic import Field, BaseModel, ConfigDict
from src.models import Curricula, CurriculaConfig
from src.platform.rendering import template_to_pic

from .util import times

weekday_chinese = [
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
]


class Course(BaseModel):
    """ "课程信息"""

    name: str
    teacher: str | None = None
    time: str
    location: str | None = None
    end: bool = Field(default=False)

    def md5(self) -> str:
        """返回当前课表内容的 MD5 摘要。"""
        return f"{self.name}{self.teacher}{self.location}"

    model_config = ConfigDict(extra="forbid")


class CurrentWeek(BaseModel):
    """当前周信息"""

    year: int
    week_number: int
    month: str
    day: str
    weekday: str
    model_config = ConfigDict(extra="forbid")


class NextCountdown(BaseModel):
    """下节课或上课倒计时"""

    title: str
    time_remaining: str
    percentage: float
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def calc(cls, title: str, first_date: str, today: datetime, last_date: str):
        """计算下节课或上课倒计时

        参数:
            title (str): 标题
            first_date (str): 上次时间(可能是上课可能是下课但一定是比today早的时间)
            today (datetime): 当前时间
            last_date (str): 下次时间(可能是上课可能是下课但一定是比today晚的时间)
        """
        first_hour, first_minute = first_date.split(":")
        first_datetime = today.replace(hour=int(first_hour), minute=int(first_minute), second=0, microsecond=0)
        last_hour, last_minute = last_date.split(":")
        last_datetime = today.replace(hour=int(last_hour), minute=int(last_minute), second=0, microsecond=0)
        remaining = last_datetime - today  # 得到剩余时间
        percentage = (today - first_datetime) / (last_datetime - first_datetime) * 100
        return cls(
            title=title,
            time_remaining=f"{remaining.seconds//3600:02d}:{(remaining.seconds//60)%60:02d}:{remaining.seconds%60:02d}",
            percentage=percentage,
        )


class CurriculaSchema(BaseModel):
    """描述课表条目的结构化数据。"""

    current_week: CurrentWeek
    next_countdown: NextCountdown
    next_course: Course
    today_course: list[Course]
    this_week_course: list[list[Course | None]]
    model_config = ConfigDict(extra="forbid")

    @classmethod
    async def prase(cls, config: CurriculaConfig, curricula: list[Curricula] | None = None, day: int = 0):
        """处理prase相关逻辑。

        参数:
            config (CurriculaConfig): 配置。
            curricula (list[Curricula] | None): 课表。
            day (int): 天数偏移。
        """
        if curricula is None:
            curricula = await config.get_curricula()

        if not curricula:
            return None
        this_week_course: list[list[Course | None]] = list([] for _ in repeat(None, 7))  # 课程表
        today = datetime.now()  # 今天的日期
        if day >= 0:
            add_week = (today.weekday() + day) // 7  # 今天是星期几+天数
            today += timedelta(days=day)  # 今天的日期加上天数
            config.current_week += add_week
        else:
            add_week = (6 - today.weekday() + -day) // 7
            today += timedelta(days=day)  # 今天的日期加上天数
            config.current_week -= add_week
        config.current_week = max(1, config.current_week)  # 当前周数不能小于1
        for curr in curricula:
            if config.current_week not in curr.weeks:  # 本周课程
                continue
            for wd, le in product(curr.weekday, curr.lesson):
                ctime = f"{times[le - 1][0]}-{times[le - 1][1]}" if len(times) > le >= 0 else "00:00-00:00"
                hour, minute = ctime.split("-")[1].split(":")
                cls.insert_list(
                    this_week_course,
                    wd - 1,
                    le - 1,
                    Course(
                        name=curr.course,
                        teacher=curr.teacher,
                        time=ctime,
                        location=curr.classroom,
                        end=today > today.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0),
                    ),
                )
        today_course: list[Course] = [i for i in this_week_course[today.weekday()] if i is not None]

        next_course = None
        next_countdown = None
        for course in today_course:
            # 根据time字段的区间判断当前是否是下课或上课时间，还有多久上下课
            first_date = "00:00"  # 比today早的时间
            if course.time == "00:00-00:00" or course.end:
                first_date = course.time.split("-")[1]
                continue
            next_course = course
            start_date = course.time.split("-")[0]
            hour, minute = start_date.split(":")  # 上课时间
            if today < today.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0):  # 说明还没上课
                next_countdown = NextCountdown.calc(
                    title="距离上课时间",
                    first_date=first_date,
                    today=today,
                    last_date=start_date,
                )
            else:
                next_countdown = NextCountdown.calc(
                    title="距离下课时间",
                    first_date=start_date,
                    today=today,
                    last_date=course.time.split("-")[1],
                )
            break
        return cls(
            current_week=CurrentWeek(
                year=today.year,
                week_number=config.current_week,
                month="%02d" % today.month,
                day="%02d" % today.day,
                weekday=weekday_chinese[today.weekday()],
            ),
            next_course=next_course
            or Course(
                name="没有课程",
                time="00:00-00:00",
                location="无",
                teacher="无",
            ),
            next_countdown=next_countdown
            or NextCountdown(
                title="今日课程结束",
                time_remaining="00:00:00",
                percentage=100.0,
            ),
            today_course=today_course,
            this_week_course=this_week_course,
        )

    @staticmethod
    def insert_list(data: list[list], row: int, col: int, course: Course):
        """列表动态增长

        参数:
            data (list[list]): data。
            row (int): row。
            col (int): col。
            course (Course): course。
        """
        data_row = len(data)  # 星期
        data_col = len(data[0]) if data_row else 0

        if row >= data_row:
            for _ in repeat(None, row - data_row + 1):
                data.append([None] * (data_col + 1))
        for value in data:
            value_len = len(value)
            if value_len <= col:
                value.extend([None] * (col - value_len + 1))
        data[row][col] = course

    async def render(self) -> bytes:
        # open("data.json", "w", encoding="utf-8").write(self.model_dump_json(indent=4))
        """将当前课表渲染为图片。"""
        return await template_to_pic("curricula.html", {"data": self})
