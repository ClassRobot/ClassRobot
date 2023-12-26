from typing import overload

from pandas import DataFrame
from sqlalchemy.orm import selectinload
from utils.models.models import Student
from nonebot_plugin_orm import get_session
from sqlalchemy import delete, select, update
from utils.models import Bind, User, Teacher, BindGroup, ClassTable
from sqlalchemy.ext.asyncio import AsyncSession, async_scoped_session
from utils.typings import UserType, ClassCadre, default_student_position

# --------------------------------- 用户部分 ---------------------------------


async def update_user_type(
    user: User,
    user_type: UserType,
    session: AsyncSession | async_scoped_session[AsyncSession],
    ignore_admin: bool = True,
):
    """设置用户身份"""
    if not (ignore_admin and user.user_type == UserType.ADMIN):
        await session.execute(
            update(User).where(User.id == user.id).values(user_type=user_type)
        )


@overload
async def get_user(platform_id: int) -> User | None:
    ...


@overload
async def get_user(platform_id: int, account_id: str) -> User | None:
    ...


async def get_user(platform_id: int, account_id: str | None = None) -> User | None:
    """获取用户

    - 当只传入platform_id时, 会将platform_id作为user_id进行查找;
    - 当同时传入platform_id和account_id时, 会根据绑定平台进行查找;

    Args:
        - platform_id (int): 平台id或者用户id
        - account_id (str | None, optional): 平台账户. Defaults to None.

    Returns:
        User | None: 用户模型
    """
    async with get_session() as session:
        if account_id is None:
            # 当account_id为None时, 将platform_id作为user_id进行查找
            return await session.get(User, platform_id)
        else:
            bind = await session.scalars(
                select(Bind)
                .where(Bind.platform_id == platform_id)
                .where(Bind.account_id == account_id)
                .options(selectinload(Bind.user))
            )
            if bind := bind.one_or_none():
                return bind.user


async def no_bind_user(user_id: int) -> bool:
    """没有绑定平台的用户

    查看用户是否有绑定平台, 用于排除存在但是没有做任何绑定的用户

    Args:
        user_id (int): 用户id

    Returns:
        bool: False表示不是空用户, True表示是空用户
    """
    async with get_session() as session:
        bind = await session.scalars(select(Bind).where(Bind.user_id == user_id))
        return not bind.first()


async def create_user(
    platform_id: int, account_id: str, user_type: UserType = UserType.USER
) -> User:
    """创建用户

    Args:
        platform_id (int): 平台id
        account_id (str): 用户id
        user_type (UserType): 用户类型

    Returns:
        User: 用户模型
    """
    async with get_session() as session:
        user = User(user_type=user_type)
        session.add(user)
        session.add(Bind(platform_id=platform_id, account_id=account_id, user=user))
        await session.commit()
        await session.refresh(user)
        return user


async def add_user_bind(platform_id: int, account_id: str, user: User):
    """平台账户与用户绑定

    Args:
        platform_id (int): 平台id
        account_id (str): 账户id
        user (User): 用户模型
    """
    async with get_session() as session:
        session.add(
            Bind(platform_id=platform_id, account_id=account_id, user_id=user.id)
        )
        await session.commit()


async def delete_user_bind(platform_id: int, account_id: str):
    """删除用户绑定的平台

    Args:
        platform_id (int): 平台id
        account_id (str): 平台账户id
    """
    async with get_session() as session:
        await session.execute(
            delete(Bind)
            .where(Bind.account_id == account_id)
            .where(Bind.platform_id == platform_id)
        )
        await session.commit()


async def rebind_user(
    platform_id: int, account_id: str, old_user: User, new_user: User
):
    """将平台账户绑定到新用户

    Args:
        platform_id (int): 平台id
        account_id (str): 平台账户id
        old_user (User): 旧用户
        new_user (User): 新用户
    """
    async with get_session() as session:
        await session.execute(
            update(Bind)
            .where(Bind.account_id == account_id)
            .where(Bind.user == old_user)
            .where(Bind.platform_id == platform_id)
            .values(user_id=new_user.id)
        )
        await session.commit()


async def get_or_create_user(user_type: UserType, platform_id: int, account_id: str):
    if user := await get_user(platform_id, account_id):
        return user
    return await create_user(platform_id, account_id, user_type)


# --------------------------------- 教师部分 ---------------------------------
async def create_teacher(
    name: str, phone: int, user: User, creator: User, email: str | None = None
):
    """将普通用户添加为教师

    Args:
        name (str): 教师姓名
        phone (int): 教师联系方式
        creator (User): 添加教师的用户
        user (User): 教师用户
        email (str | None, optional): 教师的邮箱. Defaults to None.

    Returns:
        Teacher: 教师模型
    """
    async with get_session() as session:
        teacher = Teacher(
            user_id=user.id, creator=creator.id, phone=phone, name=name, email=email
        )
        session.add(teacher)
        await update_user_type(user, UserType.TEACHER, session)
        await session.commit()
        await session.refresh(teacher)
        return teacher


@overload
async def get_teacher(platform_id: User) -> Teacher | None:
    ...


@overload
async def get_teacher(platform_id: int) -> Teacher | None:
    ...


@overload
async def get_teacher(platform_id: int, account_id: str) -> Teacher | None:
    ...


async def get_teacher(
    platform_id: int | User, account_id: str | None = None
) -> Teacher | None:
    """获取教师

    - 当传入的是User模型时, 会根据user进行查找;
    - 当只传入platform_id时, 会根据teacher.id进行查找;
    - 当同时传入platform_id和account_id时, 会根据platform_id和account_id进行查找;

    Args:
        - platform_id (int): 平台id
        - account_id (str | None, optional): 平台账号. Defaults to None.

    Returns:
        Teacher | None: 教师模型
    """
    async with get_session() as session:
        if isinstance(platform_id, User):
            return await session.scalar(
                select(Teacher).where(Teacher.user_id == platform_id.id)
            )
        elif account_id is None:
            return await session.get(Teacher, platform_id)
        elif user := await get_user(platform_id, account_id):
            return await get_teacher(user)


async def delete_teacher(user: User) -> int:
    async with get_session() as session:
        result = await session.execute(
            delete(Teacher).where(Teacher.user_id == user.id)
        )
        await update_user_type(user, UserType.USER, session)
        await session.commit()
        return result.rowcount


# --------------------------------- 班级部分 ---------------------------------
async def add_class_table(
    name: str, teacher: Teacher, group_id: str, platform_id: int
) -> ClassTable:
    async with get_session() as session:
        class_table = ClassTable(name=name, teacher=teacher)
        session.add(class_table)
        session.add(
            BindGroup(
                group_id=group_id,
                platform_id=platform_id,
                creator=teacher.user_id,
                class_table=class_table,
            )
        )
        await session.commit()
        await session.refresh(class_table)
        return class_table


async def delete_group_bind(platform_id: int, group_id: str) -> int:
    async with get_session() as session:
        result = await session.execute(
            delete(BindGroup)
            .where(BindGroup.platform_id == platform_id)
            .where(BindGroup.group_id == group_id)
        )
        await session.commit()
        return result.rowcount


async def add_bind_class_table(
    group_id: str, platform_id: int, class_table: ClassTable, user: User
) -> BindGroup:
    """将班级表绑定到该群"""
    async with get_session() as session:
        bind = BindGroup(
            group_id=group_id,
            platform_id=platform_id,
            creator=user.id,
            class_table=class_table,
        )
        session.add(bind)
        await session.commit()
        await session.refresh(bind)
        await session.refresh(class_table)
        return bind


@overload
async def get_class_table(
    group_id: str | int, *, teacher: Teacher | None = None
) -> ClassTable | None:
    """如果group_id是str则根据班级名称获取班级表, 如果是int则根据班级id获取班级表"""


@overload
async def get_class_table(
    group_id: str, *, platform_id: int, teacher: Teacher | None = None
) -> ClassTable | None:
    """根据平台群号与平台id获取班级表"""


async def get_class_table(
    group_id: str | int,
    *,
    platform_id: int | None = None,
    teacher: Teacher | None = None,
) -> ClassTable | None:
    """获取班级表

    - 输入group_id和platform_id时会根据群绑定来查找;
    - 只输入group_id会判断group_id类型，str通过班级名称查找，int根据班级id查找;
    - 以上中携带teacher则会判断该班级是否是该教师的班级;

    Args:
        - group_id (str): 群id或者班级名称或者班级id
        - platform_id (int | None, optional): 平台id. Defaults to None.
        - teacher (Teacher | None, optional): 教师. Defaults to None.

    Returns:
        ClassTable | None: 班级表
    """
    async with get_session() as session:
        if platform_id is None:
            sql = (
                select(ClassTable).where(ClassTable.name == group_id)
                if isinstance(group_id, str)
                else select(ClassTable).where(ClassTable.id == group_id)
            )
            if teacher is not None:
                sql = sql.where(ClassTable.teacher == teacher)
            return await session.scalar(sql)
        elif bind_group := await session.scalar(
            select(BindGroup)
            .where(BindGroup.group_id == group_id)
            .where(BindGroup.platform_id == platform_id)
            .options(selectinload(BindGroup.class_table))
        ):
            if teacher is None or bind_group.class_table.teacher_id == teacher.id:
                return bind_group.class_table
            return None


async def get_class_table_list(teacher: Teacher | None) -> list[ClassTable]:
    async with get_session() as session:
        if teacher is None:
            return list(await session.scalars(select(ClassTable)))
        return list(
            await session.scalars(
                select(ClassTable).where(ClassTable.teacher == teacher)
            )
        )


async def delete_class_table(
    name: str | int | ClassTable, teacher: Teacher | None = None
) -> int:
    class_table: ClassTable | None = None
    async with get_session() as session:
        if isinstance(name, ClassTable) and (
            teacher is None or name.teacher_id == teacher.id
        ):
            class_table = name
        elif isinstance(name, (int, str)):
            class_table = await get_class_table(name, teacher=teacher)
        if class_table is not None:
            await session.execute(
                update(User)
                .where(Student.class_table == class_table)
                .where(Student.user_id == User.id)
                .where(User.user_type != UserType.ADMIN)
                .values(user_type=UserType.USER)
            )
            await session.execute(
                delete(ClassTable).where(ClassTable.id == class_table.id)
            )
            await session.commit()
            return 1
        return 0


async def transfer_class_table(class_table: ClassTable, new_teacher: Teacher):
    async with get_session() as session:
        await session.execute(
            update(Student)
            .where(Student.class_table == class_table)
            .values(teacher_id=new_teacher.id)
        )
        await session.execute(
            update(ClassTable)
            .where(ClassTable.id == class_table.id)
            .values(teacher_id=new_teacher.id)
        )

        await session.commit()


# --------------------------------- 学生部分 ---------------------------------
@overload
async def get_student(platform_id: User) -> Student | None:
    "根据用户模型获取学生模型"


@overload
async def get_student(platform_id: int) -> Student | None:
    "根据学生id获取学生模型"


@overload
async def get_student(platform_id: int, account_id: str) -> Student | None:
    "根据平台id和平台账号获取学生模型"


async def get_student(
    platform_id: int | User, account_id: str | None = None
) -> Student | None:
    """获取学生

    - 当platform_id为User模型时, 会根据user进行查找;
    - 当只传入platform_id时, 会根据student.id进行查找;
    - 当同时传入platform_id和account_id时, 会根据platform_id和account_id进行;

    Args:
        - platform_id (int | User): 平台id
        - account_id (str | None, optional): 平台账号. Defaults to None.

    Returns:
        Student | None: 学生模型
    """
    async with get_session() as session:
        if isinstance(platform_id, User):
            return await session.scalar(
                select(Student).where(Student.user == platform_id)
            )
        elif account_id is None:
            return await session.get(Student, platform_id)
        elif user := await get_user(platform_id, account_id):
            return await get_student(user)


async def create_student(
    name: str,
    class_table: ClassTable,
    teacher: Teacher,
    student_user: User,
):
    async with get_session() as session:
        student = Student(
            name=name, class_table=class_table, teacher=teacher, user=student_user
        )
        await update_user_type(student_user, UserType.STUDENT, session)
        session.add(student)
        await session.commit()
        await session.refresh(student)
        await session.refresh(teacher)
        await session.refresh(class_table)
        await session.refresh(student_user)
        return student


async def get_student_list(class_table: ClassTable) -> list[Student]:
    async with get_session() as session:
        return list(
            await session.scalars(
                select(Student).where(Student.class_table == class_table)
            )
        )


async def delete_student(
    student_id: int | User | Student, teacher: Teacher | None = None
) -> int:
    """删除学生

    - `student_id`是学生模型时直接删除;
    - `student_id`是用户模型时, 会根据`user`进行查找，如果携带`teacher`则会判断该学生是否是该教师的学生;
    - `student_id`是数字时, 会根据`student.id`进行查找，如果携带`teacher`则会判断该学生是否是该教师的学生;

    Args:
        - `student_id` (`int` | `User` | `Student`): 学生id或者用户模型或者学生模型
        - `teacher` (`Teacher` | `None`): 教师模型

    Returns:
        int: 删除的学生数量
    """

    async with get_session() as session:
        if isinstance(student_id, Student):  # 如果是学生模型，则直接删除
            if user := await session.get(User, student_id.user_id):
                await update_user_type(user, UserType.USER, session)
            student = student_id
        else:
            sql = (
                select(Student).where(Student.user == student_id)
                if isinstance(student_id, User)  # 如果是用户模型则通过用户模型查找，如果是数字则根据学生id查找
                else select(Student).where(Student.id == student_id)
            )
            if teacher is not None:  # 如果存在教师模型，则判断该学生是否是教师的学生
                sql = sql.where(Student.teacher == teacher)
            if student := await session.scalar(sql.options(selectinload(Student.user))):
                await update_user_type(student.user, UserType.USER, session)
        if student is not None:
            await session.delete(student)
            await session.commit()
            return 1
        return 0


async def query_student(
    class_table: ClassTable,
) -> DataFrame:
    async with get_session() as session:
        result = await session.scalars(
            select(Student).where(Student.class_table == class_table)
        )
        return DataFrame(
            result.fetchall(),
            columns=[column.name for column in Student.__table__.columns],
        )


async def update_student_class_cadre(student: Student, class_cadre: ClassCadre):
    async with get_session() as session:
        await session.execute(
            update(Student)
            .where(Student.position == class_cadre)
            .values(position=default_student_position)
        )
        await session.execute(
            update(Student)
            .where(Student.id == student.id)
            .values(class_cadre=class_cadre)
        )
        await session.commit()
        await session.refresh(student)
