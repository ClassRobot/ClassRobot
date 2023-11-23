from utils.typings import UserType
from sqlalchemy.orm import selectinload
from utils.models.models import Student
from nonebot_plugin_orm import get_session
from sqlalchemy import delete, select, update
from utils.models import Bind, User, Major, College, Teacher, BindGroup, ClassTable


async def get_user(platform_id: int, account_id: str | None = None) -> User | None:
    """获取用户

    Args:
        platform_id (int): 平台id, 但如果 account_id 为空时 platform_id 会作为 user_id 进行查找
        account_id (str | None, optional): 平台的账户id. Defaults to None.

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
    """查看用户是否有绑定平台, 用于排除存在但是没有做任何绑定的用户

    Args:
        user_id (int): 用户id

    Returns:
        bool: False表示不是空用户, True表示是空用户
    """
    async with get_session() as session:
        bind = await session.scalars(select(Bind).where(Bind.user_id == user_id))
        return not bind.first()


async def create_user(platform_id: int, account_id: str, user_type: UserType) -> User:
    async with get_session() as session:
        user = User(user_type=user_type)
        session.add(user)
        session.add(Bind(platform_id=platform_id, account_id=account_id, user=user))
        await session.commit()
        await session.refresh(user)
        return user


async def add_user_bind(platform_id: int, account_id: str, user: User):
    async with get_session() as session:
        session.add(
            Bind(platform_id=platform_id, account_id=account_id, user_id=user.id)
        )
        await session.commit()


async def remove_user_bind(platform_id: int, account_id: str):
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
    """重新绑定用户

    Args:
        platform_id (int): 平台id
        account_id (str): 平台账户id
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


async def create_teacher(
    name: str, phone: int, user: User, creator: User, email: str | None = None
):
    async with get_session() as session:
        teacher = Teacher(
            name=name, phone=phone, creator=creator.id, email=email, user=user.id
        )
        session.add(teacher)
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


async def get_student(platform_id: int, account_id: str | None = None):
    """获取学生

    当account_id为None时, 会将platform_id作为user_id进行查询;

    Args:
        platform_id (int): 平台id
        account_id (str | None, optional): 平台账号. Defaults to None.

    Returns:
        Student | None: 学生模型
    """
    async with get_session() as session:
        if account_id is None:
            return await session.scalar(
                select(Student).where(Student.user_id == platform_id)
            )
        elif user := await get_user(platform_id, account_id):
            return await get_student(user.id)


async def set_teacher(
    name: str, phone: int, creator: User, user: User, email: str | None = None
) -> Teacher:
    """将普通用户设置为教师

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
        await session.execute(
            update(User).where(User.id == user.id).values(user_type=UserType.TEACHER)
        )
        await session.commit()
        await session.refresh(teacher)
        return teacher


async def remove_teacher(user: User):
    async with get_session() as session:
        await session.execute(delete(Teacher).where(Teacher.user_id == user.id))
        await session.execute(
            update(User).where(User.id == user.id).values(user_type=UserType.USER)
        )
        await session.commit()


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

    - 当platform_id不为空时, 会根据platform_id和group_id进行查询;
    - 当platform_id为空时, 会根据teacher和group_id视为name进行查询;

    Args:
        - group_id (str): 群id或者班级名称
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
