from datetime import datetime
from itertools import repeat, product

from utils.template import template_to_pic
from pydantic import Extra, Field, BaseModel
from utils.models import Curricula, CurriculaConfig

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
    teacher: str | None
    time: str
    location: str | None
    end: bool = Field(default=False)

    class Config:
        extra = Extra.forbid


class CurrentWeek(BaseModel):
    """当前周信息"""

    year: int
    week_number: int
    month: str
    day: str
    weekday: str

    class Config:
        extra = Extra.forbid


class NextCountdown(BaseModel):
    """下节课或上课倒计时"""

    title: str
    time_remaining: str
    percentage: float

    class Config:
        extra = Extra.forbid


class CurriculaSchema(BaseModel):
    current_week: CurrentWeek
    next_countdown: NextCountdown
    next_course: Course
    today_course: list[Course]
    this_week_course: list[list[Course | None]]

    class Config:
        extra = Extra.forbid

    @classmethod
    async def prase(cls, config: CurriculaConfig, curricula: list[Curricula] | None = None):
        if curricula is None:
            curricula = await config.get_curricula()

        if not curricula:
            return None

        today = datetime.now()
        current_week = config.current_week
        this_week_course: list[list[Course | None]] = list([] for _ in repeat(None, 7))  # 课程表

        for curr in curricula:
            if current_week in curr.weeks:  # 本周课程
                for wd, le in product(curr.weekday, curr.lesson):
                    if len(times) > le >= 0:
                        ctime = f"{times[le - 1][0]}-{times[le - 1][1]}"
                    else:
                        ctime = "00:00-00:00"
                    # Check if the course has already ended
                    course_end_time = datetime.strptime(ctime.split("-")[1], "%H:%M")
                    course_end_time = today.replace(
                        hour=course_end_time.hour, minute=course_end_time.minute, second=0, microsecond=0
                    )
                    is_ended = today > course_end_time

                    cls.insert_list(
                        this_week_course,
                        wd - 1,
                        le - 1,
                        Course(
                            name=curr.course,
                            teacher=curr.teacher,
                            time=ctime,
                            location=curr.classroom,
                            end=is_ended,
                        ),
                    )
        today_course: list[Course] = [i for i in this_week_course[today.weekday()] if i is not None]

        next_course = None
        next_countdown = None
        for course in today_course:
            # 根据time字段的区间判断当前是否是下课或上课时间，还有多久上下课
            if course.time == "00:00-00:00":
                continue
            start_time = datetime.strptime(course.time.split("-")[0], "%H:%M")
            end_time = datetime.strptime(course.time.split("-")[1], "%H:%M")
            start_time = today.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)
            end_time = today.replace(hour=end_time.hour, minute=end_time.minute, second=0, microsecond=0)
            if start_time < today < end_time:
                next_course = course
                time_remaining = end_time - today
                percentage = ((today - start_time) / (end_time - start_time) * 100) if end_time != start_time else 100
                # Determine if we're in class or the class has ended

                next_countdown = NextCountdown(
                    title="距离下节课",
                    time_remaining=f"{time_remaining.seconds//3600:02d}:{(time_remaining.seconds//60)%60:02d}:{time_remaining.seconds%60:02d}",
                    percentage=percentage,
                )
                break

        return cls(
            current_week=CurrentWeek(
                year=today.year,
                week_number=current_week,
                month="%02d" % today.month,
                day="%02d" % today.day,
                weekday=weekday_chinese[today.weekday()],
            ),
            next_course=next_course
            or Course(
                name="没有课程",
                time="00:00-00:00",
                location=None,
                teacher=None,
            ),
            next_countdown=next_countdown
            or NextCountdown(
                title="没有课程",
                time_remaining="0",
                percentage=0.0,
            ),
            today_course=today_course,
            this_week_course=this_week_course,
        )

    @staticmethod
    def insert_list(data: list[list], row: int, col: int, course: Course):
        """列表动态增长"""
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
        # open("data.json", "w", encoding="utf-8").write(self.json(ensure_ascii=False, indent=4))
        return await template_to_pic("curricula.html", {"data": self})
