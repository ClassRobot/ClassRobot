from typing import List

from sqlalchemy.orm.base import Mapped
from nonebot_plugin_orm import Model as Base
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy import (
    TIMESTAMP,
    Text,
    Index,
    Column,
    Double,
    String,
    Integer,
    BigInteger,
    ForeignKeyConstraint,
    text,
)


class College(Base):
    __tablename__ = "college"
    __table_args__ = (
        Index("college", "college", unique=True),
        Index("id", "id", unique=True),
        {"comment": "学院表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="学院id")
    college = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="院系名称"
    )
    creator = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="添加人"
    )

    major: Mapped[List["Major"]] = relationship(
        "Major", uselist=True, back_populates="college_"
    )


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (Index("id", "id", unique=True), {"comment": "反馈表"})

    id = mapped_column(Integer, primary_key=True, comment="反馈id")
    qq = mapped_column(BigInteger, nullable=False, comment="反馈人qq")
    content = mapped_column(
        Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="反馈内容"
    )
    create_at = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="反馈时间",
    )
    image_md5 = mapped_column(String(255, "utf8mb4_unicode_ci"), comment="反馈图片")


class Teacher(Base):
    __tablename__ = "teacher"
    __table_args__ = (
        Index("email", "email", unique=True),
        Index("id", "id", unique=True),
        Index("phone", "phone", unique=True),
        Index("qq", "qq", unique=True),
        {"comment": "教师表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="教师id")
    qq = mapped_column(BigInteger, nullable=False, comment="教师qq号")
    name = mapped_column(
        String(20, "utf8mb4_unicode_ci"), nullable=False, comment="教师姓名"
    )
    creator = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="谁邀请的"
    )
    phone = mapped_column(BigInteger, nullable=False, comment="教师电话")
    email = mapped_column(String(100, "utf8mb4_unicode_ci"), comment="教师邮箱")

    class_table: Mapped[List["ClassTable"]] = relationship(
        "ClassTable", uselist=True, back_populates="teacher_"
    )


class Major(Base):
    __tablename__ = "major"
    __table_args__ = (
        ForeignKeyConstraint(["college"], ["college.id"], name="major_ibfk_1"),
        Index("college", "college"),
        Index("id", "id", unique=True),
        Index("major", "major", unique=True),
        {"comment": "专业表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="专业id")
    college = mapped_column(Integer, nullable=False, comment="学院id")
    major = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="专业名称"
    )
    creator = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="添加人"
    )

    college_: Mapped["College"] = relationship("College", back_populates="major")
    class_table: Mapped[List["ClassTable"]] = relationship(
        "ClassTable", uselist=True, back_populates="major_"
    )


class ClassTable(Base):
    __tablename__ = "class_table"
    __table_args__ = (
        ForeignKeyConstraint(["major"], ["major.id"], name="class_table_ibfk_2"),
        ForeignKeyConstraint(["teacher"], ["teacher.id"], name="class_table_ibfk_1"),
        Index("group_id", "group_id", unique=True),
        Index("id", "id", unique=True),
        Index("major", "major"),
        Index("name", "name", unique=True),
        Index("teacher", "teacher"),
        {"comment": "班级表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="班级id")
    group_id = mapped_column(BigInteger, nullable=False, comment="班级QQ群")
    name = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="班级群名"
    )
    teacher = mapped_column(Integer, nullable=False, comment="教师id")
    major = mapped_column(Integer, nullable=False, comment="专业id")

    major_: Mapped["Major"] = relationship("Major", back_populates="class_table")
    teacher_: Mapped["Teacher"] = relationship("Teacher", back_populates="class_table")
    class_funds: Mapped[List["ClassFunds"]] = relationship(
        "ClassFunds", uselist=True, back_populates="class_table_"
    )
    class_tasks: Mapped[List["ClassTasks"]] = relationship(
        "ClassTasks", uselist=True, back_populates="class_table_"
    )
    notice: Mapped[List["Notice"]] = relationship(
        "Notice", uselist=True, back_populates="class_table_"
    )
    student: Mapped[List["Student"]] = relationship(
        "Student", uselist=True, back_populates="class_table_"
    )
    moral_education: Mapped[List["MoralEducation"]] = relationship(
        "MoralEducation", uselist=True, back_populates="class_table_"
    )


class ClassFunds(Base):
    __tablename__ = "class_funds"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table"], ["class_table.id"], name="class_funds_ibfk_1"
        ),
        Index("class_table", "class_table"),
        Index("id", "id", unique=True),
        {"comment": "班费表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="班费id")
    class_table = mapped_column(Integer, nullable=False, comment="班级id")
    description = mapped_column(
        Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="费用所花费在某件事情"
    )
    money = mapped_column(Double(asdecimal=True), nullable=False, comment="花费金额")
    create_at = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="添加时间",
    )
    creator = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="费用记录人"
    )

    class_table_: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="class_funds"
    )


class ClassTasks(Base):
    __tablename__ = "class_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table"], ["class_table.id"], name="class_tasks_ibfk_1"
        ),
        Index("class_table", "class_table"),
        Index("id", "id", unique=True),
        {"comment": "班级任务表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="任务id")
    title = mapped_column(
        String(255, "utf8mb4_unicode_ci"), nullable=False, comment="任务标题"
    )
    task_type = mapped_column(
        String(255, "utf8mb4_unicode_ci"), nullable=False, comment="任务类型"
    )
    class_table = mapped_column(Integer, nullable=False, comment="班级id")
    creator = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="创建人"
    )
    completed = mapped_column(
        TINYINT(1), nullable=False, server_default=text("'0'"), comment="是否已经完成"
    )
    create_time = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )

    class_table_: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="class_tasks"
    )
    task_files: Mapped[List["TaskFiles"]] = relationship(
        "TaskFiles", uselist=True, back_populates="class_tasks_"
    )


class Notice(Base):
    __tablename__ = "notice"
    __table_args__ = (
        ForeignKeyConstraint(["class_table"], ["class_table.id"], name="notice_ibfk_1"),
        Index("class_table", "class_table"),
        Index("id", "id", unique=True),
        {"comment": "通知表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="通知id")
    class_table = mapped_column(Integer, nullable=False, comment="班级id")
    title = mapped_column(
        String(255, "utf8mb4_unicode_ci"), nullable=False, comment="通知标题"
    )
    content = mapped_column(
        Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="通知内容"
    )
    create_at = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="通知时间",
    )
    creator = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="通知人"
    )
    notice_type = mapped_column(
        String(50, "utf8mb4_unicode_ci"), nullable=False, comment="通知类型"
    )
    at_user = mapped_column(String(255, "utf8mb4_unicode_ci"), comment="通知@的人")

    class_table_: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="notice"
    )


class Student(Base):
    __tablename__ = "student"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table"], ["class_table.id"], name="student_ibfk_1"
        ),
        Index("QQ", "QQ", unique=True),
        Index("class_table", "class_table"),
        Index("email", "email", unique=True),
        Index("id_card", "id_card", unique=True),
        Index("phone", "phone", unique=True),
        Index("student_id", "student_id", unique=True),
        Index("wechat", "wechat", unique=True),
        {"comment": "学生表"},
    )

    QQ = mapped_column(BigInteger, primary_key=True, comment="QQ")
    name = mapped_column(
        String(20, "utf8mb4_unicode_ci"), nullable=False, comment="学生姓名"
    )
    class_table = mapped_column(Integer, nullable=False, comment="学生班级")
    position = mapped_column(
        String(50, "utf8mb4_unicode_ci"),
        nullable=False,
        server_default=text("'学生'"),
        comment="学生",
    )
    dorm_head = mapped_column(
        TINYINT(1), nullable=False, server_default=text("'0'"), comment="寝室长"
    )
    student_id = mapped_column(BigInteger, comment="学号")
    phone = mapped_column(BigInteger, comment="联系方式")
    id_card = mapped_column(String(20, "utf8mb4_unicode_ci"), comment="身份证号")
    wechat = mapped_column(String(100, "utf8mb4_unicode_ci"), comment="微信号")
    email = mapped_column(String(100, "utf8mb4_unicode_ci"), comment="邮箱")
    sex = mapped_column(String(10, "utf8mb4_unicode_ci"), comment="性别")
    class_order = mapped_column(Integer, comment="个人在班级中的顺序")
    birthday = mapped_column(TIMESTAMP, comment="出生日期")
    dorm = mapped_column(String(20, "utf8mb4_unicode_ci"), comment="寝室")
    ethnic = mapped_column(String(200, "utf8mb4_unicode_ci"), comment="民族")
    birthplace = mapped_column(String(200, "utf8mb4_unicode_ci"), comment="籍贯")
    politics = mapped_column(String(50, "utf8mb4_unicode_ci"), comment="政治面貌")
    address = mapped_column(String(200, "utf8mb4_unicode_ci"), comment="家庭住址")

    class_table_: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="student"
    )
    moral_education: Mapped[List["MoralEducation"]] = relationship(
        "MoralEducation", uselist=True, back_populates="student"
    )
    student_council: Mapped[List["StudentCouncil"]] = relationship(
        "StudentCouncil", uselist=True, back_populates="student_"
    )
    task_files: Mapped[List["TaskFiles"]] = relationship(
        "TaskFiles", uselist=True, back_populates="student_"
    )


class MoralEducation(Base):
    __tablename__ = "moral_education"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table"], ["class_table.id"], name="moral_education_ibfk_1"
        ),
        ForeignKeyConstraint(["qq"], ["student.QQ"], name="moral_education_ibfk_2"),
        Index("class_table", "class_table"),
        Index("id", "id", unique=True),
        Index("qq", "qq"),
        {"comment": "德育日志"},
    )

    id = mapped_column(Integer, primary_key=True, comment="德育日志id")
    class_table = mapped_column(Integer, nullable=False, comment="班级id")
    qq = mapped_column(BigInteger, nullable=False, comment="学生qq")
    description = mapped_column(
        Text(collation="utf8mb4_unicode_ci"), nullable=False, comment="解释原因原因"
    )
    score = mapped_column(
        Integer, nullable=False, server_default=text("'0'"), comment="加减的分数"
    )
    create_at = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="日志时间",
    )
    activity_type = mapped_column(String(50, "utf8mb4_unicode_ci"), comment="分数类型")
    prove = mapped_column(String(255, "utf8mb4_unicode_ci"), comment="证明文件")

    class_table_: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="moral_education"
    )
    student: Mapped["Student"] = relationship(
        "Student", back_populates="moral_education"
    )


class StudentCouncil(Base):
    __tablename__ = "student_council"
    __table_args__ = (
        ForeignKeyConstraint(
            ["student"], ["student.QQ"], name="student_council_ibfk_1"
        ),
        Index("id", "id", unique=True),
        Index("student", "student"),
        {"comment": "学生会表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="学生会id")
    student = mapped_column(BigInteger, nullable=False, comment="学生qq")
    department = mapped_column(
        String(50, "utf8mb4_unicode_ci"), nullable=False, comment="学生会部门"
    )
    position = mapped_column(
        String(50, "utf8mb4_unicode_ci"), nullable=False, comment="学生会职位"
    )

    student_: Mapped["Student"] = relationship(
        "Student", back_populates="student_council"
    )


class TaskFiles(Base):
    __tablename__ = "task_files"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_tasks"], ["class_tasks.id"], name="task_files_ibfk_1"
        ),
        ForeignKeyConstraint(["student"], ["student.QQ"], name="task_files_ibfk_2"),
        Index("class_tasks", "class_tasks"),
        Index("id", "id", unique=True),
        Index("student", "student"),
        {"comment": "任务文件表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="文件id")
    class_tasks = mapped_column(Integer, nullable=False, comment="收取标题")
    student = mapped_column(BigInteger, nullable=False, comment="提交人QQ")
    file_md5 = mapped_column(
        String(255, "utf8mb4_unicode_ci"), nullable=False, comment="文件名称md5"
    )
    push_time = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="上传时间",
    )

    class_tasks_: Mapped["ClassTasks"] = relationship(
        "ClassTasks", back_populates="task_files"
    )
    student_: Mapped["Student"] = relationship("Student", back_populates="task_files")
