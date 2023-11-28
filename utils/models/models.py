from typing import List

from sqlalchemy.orm.base import Mapped
from nonebot_plugin_orm import Model as Base
from sqlalchemy.orm import Mapped, relationship, mapped_column
from sqlalchemy import (
    TIMESTAMP,
    Text,
    Index,
    Double,
    String,
    Integer,
    BigInteger,
    ForeignKeyConstraint,
    text,
)


class User(Base):
    __tablename__ = "user"
    __table_args__ = (Index("id", "id", unique=True), {"comment": "用户总表"})

    id = mapped_column(Integer, primary_key=True, comment="用户id")
    create_at = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )
    user_type = mapped_column(
        String(50, "utf8mb4_unicode_ci"),
        nullable=False,
        server_default=text("'anonymous'"),
        comment="用户类型[admin|teacher|student|anonymous]",
    )

    bind: Mapped[List["Bind"]] = relationship(
        "Bind", uselist=True, back_populates="user"
    )
    college: Mapped[List["College"]] = relationship(
        "College", uselist=True, back_populates="user"
    )
    feedback: Mapped[List["Feedback"]] = relationship(
        "Feedback", uselist=True, back_populates="user"
    )
    teacher: Mapped[List["Teacher"]] = relationship(
        "Teacher", uselist=True, foreign_keys="[Teacher.creator]", back_populates="user"
    )
    teacher_: Mapped[List["Teacher"]] = relationship(
        "Teacher",
        uselist=True,
        foreign_keys="[Teacher.user_id]",
        back_populates="user_",
    )
    major: Mapped[List["Major"]] = relationship(
        "Major", uselist=True, back_populates="user"
    )
    bind_group: Mapped[List["BindGroup"]] = relationship(
        "BindGroup", uselist=True, back_populates="user"
    )
    class_funds: Mapped[List["ClassFunds"]] = relationship(
        "ClassFunds", uselist=True, back_populates="user"
    )
    class_tasks: Mapped[List["ClassTasks"]] = relationship(
        "ClassTasks", uselist=True, back_populates="user"
    )
    notice: Mapped[List["Notice"]] = relationship(
        "Notice", uselist=True, back_populates="user"
    )
    student: Mapped[List["Student"]] = relationship(
        "Student", uselist=True, back_populates="user"
    )
    task_files: Mapped[List["TaskFiles"]] = relationship(
        "TaskFiles", uselist=True, back_populates="user"
    )


class Bind(Base):
    __tablename__ = "bind"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE", name="bind_ibfk_1"
        ),
        Index("id", "id", unique=True),
        Index("user_id", "user_id"),
        {"comment": "绑定表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="绑定id")
    user_id = mapped_column(Integer, nullable=False, comment="用户id")
    platform_id = mapped_column(Integer, nullable=False, comment="平台id")
    account_id = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="平台账号id"
    )
    create_at = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="绑定时间",
    )

    user: Mapped["User"] = relationship("User", back_populates="bind")


class College(Base):
    __tablename__ = "college"
    __table_args__ = (
        ForeignKeyConstraint(["creator"], ["user.id"], name="college_ibfk_1"),
        Index("college", "college", unique=True),
        Index("creator", "creator"),
        Index("id", "id", unique=True),
        {"comment": "学院表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="学院id")
    college = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="院系名称"
    )
    creator = mapped_column(Integer, nullable=False, comment="添加人")

    user: Mapped["User"] = relationship("User", back_populates="college")
    major: Mapped[List["Major"]] = relationship(
        "Major", uselist=True, back_populates="college"
    )


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (
        ForeignKeyConstraint(["user_id"], ["user.id"], name="feedback_ibfk_1"),
        Index("id", "id", unique=True),
        Index("user_id", "user_id"),
        {"comment": "反馈表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="反馈id")
    user_id = mapped_column(Integer, nullable=False, comment="反馈人qq")
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

    user: Mapped["User"] = relationship("User", back_populates="feedback")


class Teacher(Base):
    __tablename__ = "teacher"
    __table_args__ = (
        ForeignKeyConstraint(["creator"], ["user.id"], name="teacher_ibfk_2"),
        ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE", name="teacher_ibfk_1"
        ),
        Index("creator", "creator"),
        Index("email", "email", unique=True),
        Index("id", "id", unique=True),
        Index("phone", "phone", unique=True),
        Index("user_id", "user_id", unique=True),
        {"comment": "教师表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="教师id")
    name = mapped_column(
        String(20, "utf8mb4_unicode_ci"), nullable=False, comment="教师姓名"
    )
    user_id = mapped_column(Integer, nullable=False, comment="用户id")
    creator = mapped_column(Integer, nullable=False, comment="谁邀请的")
    phone = mapped_column(BigInteger, nullable=False, comment="教师电话")
    email = mapped_column(String(100, "utf8mb4_unicode_ci"), comment="教师邮箱")

    user: Mapped["User"] = relationship(
        "User", foreign_keys=[creator], back_populates="teacher"
    )
    user_: Mapped["User"] = relationship(
        "User", foreign_keys=[user_id], back_populates="teacher_"
    )
    class_table: Mapped[List["ClassTable"]] = relationship(
        "ClassTable", uselist=True, back_populates="teacher"
    )
    student: Mapped[List["Student"]] = relationship(
        "Student", uselist=True, back_populates="teacher"
    )


class Major(Base):
    __tablename__ = "major"
    __table_args__ = (
        ForeignKeyConstraint(["college_id"], ["college.id"], name="major_ibfk_1"),
        ForeignKeyConstraint(["creator"], ["user.id"], name="major_ibfk_2"),
        Index("college_id", "college_id"),
        Index("creator", "creator"),
        Index("id", "id", unique=True),
        Index("major", "major", unique=True),
        {"comment": "专业表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="专业id")
    college_id = mapped_column(Integer, nullable=False, comment="学院id")
    major = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="专业名称"
    )
    creator = mapped_column(Integer, nullable=False, comment="添加人")

    college: Mapped["College"] = relationship("College", back_populates="major")
    user: Mapped["User"] = relationship("User", back_populates="major")
    class_table: Mapped[List["ClassTable"]] = relationship(
        "ClassTable", uselist=True, back_populates="major"
    )


class ClassTable(Base):
    __tablename__ = "class_table"
    __table_args__ = (
        ForeignKeyConstraint(["major_id"], ["major.id"], name="class_table_ibfk_2"),
        ForeignKeyConstraint(["teacher_id"], ["teacher.id"], name="class_table_ibfk_1"),
        Index("id", "id", unique=True),
        Index("major_id", "major_id"),
        Index("name", "name", unique=True),
        Index("teacher_id", "teacher_id"),
        {"comment": "班级表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="班级id")
    name = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="班级群名"
    )
    teacher_id = mapped_column(Integer, nullable=False, comment="教师id")
    major_id = mapped_column(Integer, nullable=False, comment="专业id")

    major: Mapped["Major"] = relationship("Major", back_populates="class_table")
    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="class_table")
    bind_group: Mapped[List["BindGroup"]] = relationship(
        "BindGroup", uselist=True, back_populates="class_table"
    )
    class_funds: Mapped[List["ClassFunds"]] = relationship(
        "ClassFunds", uselist=True, back_populates="class_table"
    )
    class_tasks: Mapped[List["ClassTasks"]] = relationship(
        "ClassTasks", uselist=True, back_populates="class_table"
    )
    notice: Mapped[List["Notice"]] = relationship(
        "Notice", uselist=True, back_populates="class_table"
    )
    student: Mapped[List["Student"]] = relationship(
        "Student", uselist=True, back_populates="class_table"
    )
    moral_education: Mapped[List["MoralEducation"]] = relationship(
        "MoralEducation", uselist=True, back_populates="class_table"
    )


class BindGroup(Base):
    __tablename__ = "bind_group"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table_id"],
            ["class_table.id"],
            ondelete="CASCADE",
            name="bind_group_ibfk_2",
        ),
        ForeignKeyConstraint(["creator"], ["user.id"], name="bind_group_ibfk_1"),
        Index("class_table_id", "class_table_id"),
        Index("creator", "creator"),
        Index("id", "id", unique=True),
        {"comment": "绑定群表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="绑定群id")
    group_id = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="群号"
    )
    platform_id = mapped_column(
        String(100, "utf8mb4_unicode_ci"), nullable=False, comment="平台id"
    )
    creator = mapped_column(Integer, nullable=False, comment="绑定人")
    create_at = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="绑定时间",
    )
    class_table_id = mapped_column(Integer, nullable=False, comment="绑定的班级")

    class_table: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="bind_group"
    )
    user: Mapped["User"] = relationship("User", back_populates="bind_group")


class ClassFunds(Base):
    __tablename__ = "class_funds"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table_id"],
            ["class_table.id"],
            ondelete="CASCADE",
            name="class_funds_ibfk_1",
        ),
        ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE", name="class_funds_ibfk_2"
        ),
        Index("class_table_id", "class_table_id"),
        Index("id", "id", unique=True),
        Index("user_id", "user_id"),
        {"comment": "班费表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="班费id")
    class_table_id = mapped_column(Integer, nullable=False, comment="班级id")
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
    user_id = mapped_column(Integer, nullable=False, comment="记录费用的用户")

    class_table: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="class_funds"
    )
    user: Mapped["User"] = relationship("User", back_populates="class_funds")


class ClassTasks(Base):
    __tablename__ = "class_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table_id"],
            ["class_table.id"],
            ondelete="CASCADE",
            name="class_tasks_ibfk_1",
        ),
        ForeignKeyConstraint(
            ["creator"], ["user.id"], ondelete="CASCADE", name="class_tasks_ibfk_2"
        ),
        Index("class_table_id", "class_table_id"),
        Index("creator", "creator"),
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
    class_table_id = mapped_column(Integer, nullable=False, comment="班级id")
    creator = mapped_column(Integer, nullable=False, comment="创建人")
    completed = mapped_column(
        Integer, nullable=False, server_default=text("'0'"), comment="是否已经完成"
    )
    create_at = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="创建时间",
    )

    class_table: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="class_tasks"
    )
    user: Mapped["User"] = relationship("User", back_populates="class_tasks")
    task_files: Mapped[List["TaskFiles"]] = relationship(
        "TaskFiles", uselist=True, back_populates="class_tasks"
    )


class Notice(Base):
    __tablename__ = "notice"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table_id"],
            ["class_table.id"],
            ondelete="CASCADE",
            name="notice_ibfk_1",
        ),
        ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE", name="notice_ibfk_2"
        ),
        Index("class_table_id", "class_table_id"),
        Index("id", "id", unique=True),
        Index("user_id", "user_id"),
        {"comment": "通知表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="通知id")
    class_table_id = mapped_column(Integer, nullable=False, comment="班级id")
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
    user_id = mapped_column(Integer, nullable=False, comment="创建的用户id")
    notice_type = mapped_column(
        String(50, "utf8mb4_unicode_ci"), nullable=False, comment="通知类型"
    )
    at_user = mapped_column(String(255, "utf8mb4_unicode_ci"), comment="通知@的用户")

    class_table: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="notice"
    )
    user: Mapped["User"] = relationship("User", back_populates="notice")


class Student(Base):
    __tablename__ = "student"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table_id"],
            ["class_table.id"],
            ondelete="CASCADE",
            name="student_ibfk_1",
        ),
        ForeignKeyConstraint(["teacher_id"], ["teacher.id"], name="student_ibfk_2"),
        ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE", name="student_ibfk_3"
        ),
        Index("class_table_id", "class_table_id"),
        Index("email", "email", unique=True),
        Index("id", "id", unique=True),
        Index("id_card", "id_card", unique=True),
        Index("phone", "phone", unique=True),
        Index("student_id", "student_id", unique=True),
        Index("teacher_id", "teacher_id"),
        Index("user_id", "user_id", unique=True),
        {"comment": "学生表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="学生id")
    user_id = mapped_column(Integer, nullable=False, comment="用户id")
    name = mapped_column(
        String(20, "utf8mb4_unicode_ci"), nullable=False, comment="学生姓名"
    )
    class_table_id = mapped_column(Integer, nullable=False, comment="学生班级")
    teacher_id = mapped_column(Integer, nullable=False, comment="教师id")
    dorm_head = mapped_column(
        Integer, nullable=False, server_default=text("'0'"), comment="寝室长"
    )
    position = mapped_column(
        String(50, "utf8mb4_unicode_ci"),
        nullable=False,
        server_default=text("'学生'"),
        comment="学生",
    )
    dorm = mapped_column(String(20, "utf8mb4_unicode_ci"), comment="寝室")
    student_id = mapped_column(BigInteger, comment="学号")
    phone = mapped_column(BigInteger, comment="联系方式")
    id_card = mapped_column(String(20, "utf8mb4_unicode_ci"), comment="身份证号")
    email = mapped_column(String(100, "utf8mb4_unicode_ci"), comment="邮箱")
    sex = mapped_column(String(10, "utf8mb4_unicode_ci"), comment="性别")
    class_order = mapped_column(Integer, comment="个人在班级中的顺序")
    birthday = mapped_column(TIMESTAMP, comment="出生日期")
    ethnic = mapped_column(String(200, "utf8mb4_unicode_ci"), comment="民族")
    birthplace = mapped_column(String(200, "utf8mb4_unicode_ci"), comment="籍贯")
    politics = mapped_column(String(50, "utf8mb4_unicode_ci"), comment="政治面貌")
    address = mapped_column(String(200, "utf8mb4_unicode_ci"), comment="家庭住址")

    class_table: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="student"
    )
    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="student")
    user: Mapped["User"] = relationship("User", back_populates="student")
    moral_education: Mapped[List["MoralEducation"]] = relationship(
        "MoralEducation", uselist=True, back_populates="student"
    )
    student_council: Mapped[List["StudentCouncil"]] = relationship(
        "StudentCouncil", uselist=True, back_populates="student"
    )


class MoralEducation(Base):
    __tablename__ = "moral_education"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_table_id"],
            ["class_table.id"],
            ondelete="CASCADE",
            name="moral_education_ibfk_1",
        ),
        ForeignKeyConstraint(
            ["student_id"],
            ["student.id"],
            ondelete="CASCADE",
            name="moral_education_ibfk_2",
        ),
        Index("class_table_id", "class_table_id"),
        Index("id", "id", unique=True),
        Index("student_id", "student_id"),
        {"comment": "德育日志"},
    )

    id = mapped_column(Integer, primary_key=True, comment="德育日志id")
    class_table_id = mapped_column(Integer, nullable=False, comment="班级id")
    student_id = mapped_column(Integer, nullable=False, comment="学生id")
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

    class_table: Mapped["ClassTable"] = relationship(
        "ClassTable", back_populates="moral_education"
    )
    student: Mapped["Student"] = relationship(
        "Student", back_populates="moral_education"
    )


class StudentCouncil(Base):
    __tablename__ = "student_council"
    __table_args__ = (
        ForeignKeyConstraint(
            ["student_id"],
            ["student.id"],
            ondelete="CASCADE",
            name="student_council_ibfk_1",
        ),
        Index("id", "id", unique=True),
        Index("student_id", "student_id"),
        {"comment": "学生会表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="学生会id")
    student_id = mapped_column(Integer, nullable=False, comment="学生qq")
    department = mapped_column(
        String(50, "utf8mb4_unicode_ci"), nullable=False, comment="学生会部门"
    )
    position = mapped_column(
        String(50, "utf8mb4_unicode_ci"), nullable=False, comment="学生会职位"
    )

    student: Mapped["Student"] = relationship(
        "Student", back_populates="student_council"
    )


class TaskFiles(Base):
    __tablename__ = "task_files"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_tasks_id"],
            ["class_tasks.id"],
            ondelete="CASCADE",
            name="task_files_ibfk_1",
        ),
        ForeignKeyConstraint(
            ["user_id"], ["user.id"], ondelete="CASCADE", name="task_files_ibfk_2"
        ),
        Index("class_tasks_id", "class_tasks_id"),
        Index("id", "id", unique=True),
        Index("user_id", "user_id"),
        {"comment": "任务文件表"},
    )

    id = mapped_column(Integer, primary_key=True, comment="文件id")
    class_tasks_id = mapped_column(Integer, nullable=False, comment="收取标题")
    user_id = mapped_column(Integer, nullable=False, comment="提交人")
    file_md5 = mapped_column(
        String(255, "utf8mb4_unicode_ci"), nullable=False, comment="文件名称md5"
    )
    push_time = mapped_column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="上传时间",
    )

    class_tasks: Mapped["ClassTasks"] = relationship(
        "ClassTasks", back_populates="task_files"
    )
    user: Mapped["User"] = relationship("User", back_populates="task_files")
