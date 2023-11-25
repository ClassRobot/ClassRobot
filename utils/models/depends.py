from pandas import DataFrame
from utils.typings import UserType
from sqlalchemy.orm import selectinload
from utils.models.models import Student
from nonebot_plugin_orm import get_session
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from utils.models import Bind, User, Major, College, Teacher, BindGroup, ClassTable

# --------------------------------- 用户部分 ---------------------------------


async def update_user_type(
    user: User, user_type: UserType, session: AsyncSession, ignore_admin: bool = True
):
    """设置用户身份"""
    if not (ignore_admin and user.user_type == UserType.ADMIN):
        await session.execute(
            update(User).where(User.id == user.id).values(user_type=user_type)
        )


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


async def create_user(platform_id: int, account_id: str, user_type: UserType) -> User:
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


async def get_teacher(
    platform_id: int, account_id: str | None = None
) -> Teacher | None:
    """获取教师

    当account_id为None时, 会将platform_id作为user_id进行查询;

    Args:
        platform_id (int): 平台id
        account_id (str | None, optional): 平台账号. Defaults to None.

    Returns:
        Teacher | None: 教师模型
    """
    async with get_session() as session:
        if account_id is None:
            return await session.scalar(
                select(Teacher).where(Teacher.user_id == platform_id)
            )
        elif user := await get_user(platform_id, account_id):
            return await get_teacher(user.id)


async def delete_teacher(user: User):
    async with get_session() as session:
        await session.execute(delete(Teacher).where(Teacher.user_id == user.id))
        await update_user_type(user, UserType.USER, session)
        await session.commit()


# --------------------------------- 院系部分 ---------------------------------
async def add_college(college_name: str, user: User):
    async with get_session() as session:
        college = College(college=college_name, creator=user.id)
        session.add(college)
        await session.commit()
        await session.refresh(college)
        return college


async def get_college(college_name: str) -> College | None:
    async with get_session() as session:
        return await session.scalar(
            select(College).where(College.college == college_name)
        )


async def get_college_list() -> list[College]:
    async with get_session() as session:
        colleges = await session.scalars(select(College))
        return list(colleges.all())


async def delete_college(college_name: str | int):
    async with get_session() as session:
        if isinstance(college_name, int):
            result = await session.execute(
                delete(College).where(College.id == college_name)
            )
        else:
            result = await session.execute(
                delete(College).where(College.college == college_name)
            )
        await session.commit()
        return result.rowcount


# --------------------------------- 专业部分 ---------------------------------
async def get_major(major_name: str | int) -> Major | None:
    async with get_session() as session:
        if isinstance(major_name, int):
            return await session.get(Major, major_name)
        return await session.scalar(select(Major).where(Major.major == major_name))


async def add_major(major_name: str, college: College, creator: User):
    async with get_session() as session:
        major = Major(major=major_name, college=college, creator=creator.id)
        session.add(major)
        await session.commit()
        await session.refresh(major)
        return major


async def get_major_list(college: College) -> list[Major]:
    async with get_session() as session:
        majors = await session.scalars(select(Major).where(Major.college == college))
        return list(majors.all())


async def delete_major(major_name: str):
    async with get_session() as session:
        result = await session.execute(delete(Major).where(Major.major == major_name))
        await session.commit()
        return result.rowcount


# --------------------------------- 班级部分 ---------------------------------
async def add_class_table(
    name: str, teacher: Teacher, major: Major, group_id: str, platform_id: int
) -> ClassTable:
    async with get_session() as session:
        class_table = ClassTable(
            name=name,
            teacher=teacher,
            major=major,
        )
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


async def get_class_table(
    group_id: str, *, platform_id: int | None = None, teacher: Teacher | None = None
) -> ClassTable | None:
    """获取班级表

    - 输入group_id和platform_id时会根据群绑定来查找;
    - 输入group_id和teacher时候会根据班级名称与教师进行查找;
    - 只输入group_id时会根据班级id进行查找;

    Args:
        - group_id (str): 群id或者班级名称或者班级id
        - platform_id (int | None, optional): 平台id. Defaults to None.
        - teacher (Teacher | None, optional): 教师. Defaults to None.

    Returns:
        ClassTable | None: 班级表
    """
    async with get_session() as session:
        if platform_id is None and teacher is not None:
            return await session.scalar(
                select(ClassTable)
                .where(ClassTable.name == group_id)
                .where(ClassTable.teacher == teacher)
            )
        elif platform_id is None and teacher is None and group_id.isdigit():
            return await session.get(ClassTable, int(group_id))
        elif bind_group := await session.scalar(
            select(BindGroup)
            .where(BindGroup.group_id == group_id)
            .where(BindGroup.platform_id == platform_id)
            .options(selectinload(BindGroup.class_table))
        ):
            return bind_group.class_table


async def get_class_table_list(teacher: Teacher) -> list[ClassTable]:
    async with get_session() as session:
        return list(
            await session.scalars(
                select(ClassTable).where(ClassTable.teacher == teacher)
            )
        )


async def delete_class_table(name: str, teacher: Teacher) -> int:
    async with get_session() as session:
        result = await session.execute(
            delete(ClassTable)
            .where(ClassTable.name == name)
            .where(ClassTable.teacher == teacher)
        )
        await session.commit()
        return result.rowcount


# --------------------------------- 学生部分 ---------------------------------
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
