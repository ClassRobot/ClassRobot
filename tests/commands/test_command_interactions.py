from __future__ import annotations

import pytest
import pandas as pd

pytestmark = pytest.mark.asyncio


async def test_plain_user_can_create_and_query_teacher_profile(app, onebot, send_recorder, models):
    from src.models import Teacher
    from src.plugins.application.active.teacher.commands import set_teacher_cmd, query_teacher_cmd

    user = await models.create_user(account_id=10002, nickname="小王")
    school = await models.create_school("测试大学")
    await models.create_college(school, "计算机学院")

    async with app.test_matcher(set_teacher_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            "修改教师信息 姓名=张老师 学校=测试大学 学院=计算机学院",
            user_id=10002,
            nickname="小王",
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("教师信息创建成功", "张老师", "测试大学", "计算机学院")

    teacher = await Teacher.get_teacher(user)
    assert teacher is not None
    assert teacher.name == "张老师"
    assert teacher.school is not None and teacher.school.name == "测试大学"
    assert teacher.college is not None and teacher.college.name == "计算机学院"

    async with app.test_matcher(query_teacher_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("查询教师信息", user_id=10002, nickname="小王", message_id=2)
        ctx.receive_event(bot, event)

    recorder.assert_any("教师信息", "张老师", "测试大学", "计算机学院")


async def test_teacher_can_create_class_and_query_classes(app, onebot, send_recorder, models):
    from src.models import Classes
    from src.plugins.application.active.classes.commands import query_classes_cmd, create_classes_cmd

    user = await models.create_user(account_id=10003, nickname="老师甲")
    school = await models.create_school("测试大学")
    college = await models.create_college(school, "计算机学院")
    major = await models.create_major(school, college, "软件工程")
    await models.create_teacher(user, name="老师甲", school=school, college=college)

    async with app.test_matcher(create_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event(
            "添加班级 软件1班 测试大学 计算机学院 软件工程",
            user_id=10003,
            group_id=20001,
            nickname="老师甲",
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("班级创建成功", "软件1班", "测试大学", "计算机学院", "软件工程")

    classes = await Classes.filter(name="软件1班").first()
    assert classes is not None
    assert classes.school is not None and classes.school.name == "测试大学"
    assert classes.college is not None and classes.college.name == "计算机学院"
    assert any(teacher.user_id == user.id for teacher in classes.teacher)

    async with app.test_matcher(query_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("查询班级", user_id=10003, nickname="老师甲", message_id=2)
        ctx.receive_event(bot, event)

    recorder.assert_any("您所管理的班级如下", "软件1班")


async def test_plain_user_can_join_class_and_exit_after_confirmation(app, onebot, send_recorder, models):
    from src.models import Student
    from src.plugins.application.active.classes.commands import exit_classes_cmd, join_classes_cmd

    teacher_user = await models.create_user(account_id=10004, nickname="班主任")
    teacher = await models.create_teacher(teacher_user, name="班主任")
    classes = await models.create_classes(name="软件2班", owner=teacher_user, group_id=20002, teacher=teacher)
    user = await models.create_user(account_id=10005, nickname="李雷")

    async with app.test_matcher(join_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("加入班级", user_id=10005, group_id=20002, nickname="李雷")
        ctx.receive_event(bot, event)

    recorder.assert_any("成功加入班级", "软件2班")

    student = await Student.filter(user_id=user.id).first()
    assert student is not None
    assert student.classes_id == classes.id

    async with app.test_matcher(exit_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        prompt = onebot.private_event("退出班级", user_id=10005, nickname="李雷", message_id=2)
        confirm = onebot.private_event("yes", user_id=10005, nickname="李雷", message_id=3)
        ctx.receive_event(bot, prompt)
        ctx.receive_event(bot, confirm)

    recorder.assert_any("是否要退出该班级")
    recorder.assert_any("成功退出班级")
    assert await Student.filter(user_id=user.id).first() is None


async def test_teacher_can_change_join_method_and_approve_join_request(app, onebot, send_recorder, models):
    from src.models import Student, ClassesJoinRequest
    from src.plugins.application.active.classes.commands import (
        join_classes_cmd,
        set_join_classes_cmd,
        query_join_request_cmd,
        review_join_request_cmd,
    )

    teacher_user = await models.create_user(account_id=10006, nickname="王老师")
    teacher = await models.create_teacher(teacher_user, name="王老师")
    classes = await models.create_classes(name="软件3班", owner=teacher_user, group_id=20003, teacher=teacher)
    applicant = await models.create_user(account_id=10007, nickname="韩梅梅")

    async with app.test_matcher(set_join_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("修改班级加入方式 申请加入", user_id=10006, group_id=20003, nickname="王老师")
        ctx.receive_event(bot, event)

    recorder.assert_any("加入方式修改为", "申请加入")

    async with app.test_matcher(join_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"加入班级 {classes.id} 我想加入这个班级",
            user_id=10007,
            nickname="韩梅梅",
            message_id=2,
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("申请成功")

    request = await ClassesJoinRequest.filter(user_id=applicant.id, classes_id=classes.id).first()
    assert request is not None
    assert request.describe == "我想加入这个班级"

    async with app.test_matcher(query_join_request_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(f"查询入班申请 {classes.id}", user_id=10006, nickname="王老师", message_id=3)
        ctx.receive_event(bot, event)

    recorder.assert_any("入班申请", "韩梅梅", "软件3班", "我想加入这个班级")

    async with app.test_matcher(review_join_request_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(f"处理入班申请 {request.id} 通过", user_id=10006, nickname="王老师", message_id=4)
        ctx.receive_event(bot, event)

    recorder.assert_any("已通过申请", "韩梅梅", "软件3班")
    assert await ClassesJoinRequest.filter(id=request.id).first() is None

    student = await Student.filter(user_id=applicant.id).first()
    assert student is not None
    assert student.classes_id == classes.id


async def test_student_switch_class_syncs_school_scope(app, onebot, send_recorder, models):
    from src.models import Student
    from src.plugins.application.active.classes.commands import join_classes_cmd

    old_school = await models.create_school("旧学校")
    old_college = await models.create_college(old_school, "旧学院")
    old_owner = await models.create_user(account_id=10131, nickname="旧班主任")
    old_teacher = await models.create_teacher(old_owner, name="旧班主任", school=old_school, college=old_college)
    old_class = await models.create_classes(
        name="旧班级",
        owner=old_owner,
        group_id=20131,
        teacher=old_teacher,
        school=old_school,
        college=old_college,
    )
    new_school = await models.create_school("新学校")
    new_college = await models.create_college(new_school, "新学院")
    new_owner = await models.create_user(account_id=10132, nickname="新班主任")
    new_teacher = await models.create_teacher(new_owner, name="新班主任", school=new_school, college=new_college)
    new_class = await models.create_classes(
        name="新班级",
        owner=new_owner,
        group_id=20132,
        teacher=new_teacher,
        school=new_school,
        college=new_college,
    )
    student_user = await models.create_user(account_id=10133, nickname="转班学生")
    student = await models.create_student(student_user, classes=old_class, name="转班学生")
    assert student.school_id == old_school.id

    async with app.test_matcher(join_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        prompt = onebot.private_event(
            f"加入班级 {new_class.id}",
            user_id=10133,
            nickname="转班学生",
        )
        confirm = onebot.private_event("yes", user_id=10133, nickname="转班学生", message_id=2)
        ctx.receive_event(bot, prompt)
        ctx.receive_event(bot, confirm)

    recorder.assert_any("成功加入班级", "新班级")
    student = await Student.filter(user_id=student_user.id).first()
    assert student is not None
    assert student.classes_id == new_class.id
    assert student.school_id == new_school.id


async def test_student_can_query_and_update_profile(app, onebot, send_recorder, models):
    from src.models import Student
    from src.plugins.application.active.student.commands import set_cmd, query_cmd

    owner = await models.create_user(account_id=10008, nickname="班主任乙")
    teacher = await models.create_teacher(owner, name="班主任乙")
    classes = await models.create_classes(name="软件4班", owner=owner, group_id=20004, teacher=teacher)
    user = await models.create_user(account_id=10009, nickname="初始学生")
    await models.create_student(user, classes=classes, name="初始学生")

    async with app.test_matcher(query_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("查询学生信息", user_id=10009, nickname="初始学生")
        ctx.receive_event(bot, event)

    recorder.assert_any("学生信息", "初始学生", "软件4班")

    async with app.test_matcher(set_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            "修改学生信息 名字=李雷 学号=20250001 宿舍=1-101",
            user_id=10009,
            nickname="初始学生",
            message_id=2,
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("设置成功")

    student = await Student.filter(user_id=user.id).first()
    assert student is not None
    assert student.name == "李雷"
    assert student.extra is not None
    assert student.extra.student_code == "20250001"
    assert student.extra.dormitory == "1-101"


async def test_teacher_can_delete_empty_class(app, onebot, send_recorder, models, monkeypatch, tmp_path):
    from src.models import Classes
    from src.core.storage import StorageManager
    import src.models.models as model_definitions
    from src.plugins.application.active.classes.commands import delete_classes_cmd

    storage = StorageManager(tmp_path / "storage")
    monkeypatch.setattr(model_definitions, "storage_manager", storage)

    user = await models.create_user(account_id=10010, nickname="老师丙")
    teacher = await models.create_teacher(user, name="老师丙")
    classes = await models.create_classes(name="待删除班级", owner=user, group_id=20005, teacher=teacher)
    group_space = storage.group_space(classes.group_id)
    class_space = storage.class_space(classes.id)
    group_space.touch("documents/classes-note.txt")
    group_space.chat_dir.joinpath("messages.db").write_text("classes chat", encoding="utf-8")
    class_space.touch("documents/class-space-note.txt")

    async with app.test_matcher(delete_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(f"删除班级 {classes.id}", user_id=10010, nickname="老师丙")
        ctx.receive_event(bot, event)

    recorder.assert_any("删除班级成功")
    assert await Classes.filter(id=classes.id).first() is None
    assert not group_space.space_root.exists()
    assert not class_space.space_root.exists()


async def test_import_classes_can_create_teacher_class_and_student(app, onebot, send_recorder, monkeypatch, models):
    from src.models import Classes, Student, Teacher
    import src.plugins.application.active.classes.depends as classes_depends
    from src.plugins.application.active.classes.commands import import_classes_cmd

    user = await models.create_user(account_id=10011, nickname="导入老师")
    school = await models.create_school("导入学校")
    await models.create_college(school, "信息学院")

    def fake_read_excel(_):
        return pd.DataFrame(
            [
                {
                    "姓名": "张三",
                    "学号": "20250002",
                    "学校": "导入学校",
                    "学院": "信息学院",
                    "班级": "导入班级",
                    "专业": "大数据",
                }
            ]
        )

    async def fake_download_file(data, to_path=None):
        return b"excel-bytes"

    monkeypatch.setattr(classes_depends, "read_excel", fake_read_excel)
    monkeypatch.setattr(classes_depends, "download_file", fake_download_file)

    async with app.test_matcher(import_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(onebot.file_command("导入班级"), user_id=10011, nickname="导入老师")
        ctx.receive_event(bot, event)

    recorder.assert_any("班级导入完成", "创建班级", "创建学生")

    teacher = await Teacher.get_teacher(user)
    classes = await Classes.filter(name="导入班级").first()
    student = await Student.filter(name="张三").first()
    assert teacher is not None
    assert classes is not None
    assert student is not None
    assert student.classes_id == classes.id


async def test_admin_can_assign_college_manager_and_manager_can_manage_profiles(app, onebot, send_recorder, models):
    from src.models import Student, Teacher, CollegeTeacher
    from src.plugins.application.active.group.commands import set_college_manager
    from src.plugins.application.active.student.commands import add_student_profile_cmd
    from src.plugins.application.active.teacher.commands import add_teacher_profile_cmd

    admin = await models.create_user(account_id=10101, nickname="管理员", is_admin=True)
    school = await models.create_school("组织大学")
    college = await models.create_college(school, "软件学院")
    manager_user = await models.create_user(account_id=10102, nickname="院负责人")
    manager = await models.create_teacher(manager_user, name="院负责人", school=school, college=college)

    async with app.test_matcher(set_college_manager) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"设置学院负责人 组织大学 软件学院 {manager.id}",
            user_id=10101,
            nickname=admin.nickname,
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("学院", "负责人")
    assert await CollegeTeacher.filter(teacher_id=manager.id, college_id=college.id).first() is not None

    new_teacher_user = await models.create_user(account_id=10103, nickname="新教师")
    async with app.test_matcher(add_teacher_profile_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"添加教师 {new_teacher_user.id} 新教师 组织大学 软件学院",
            user_id=10102,
            nickname="院负责人",
            message_id=2,
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("教师档案创建成功", "新教师", "软件学院")
    new_teacher = await Teacher.filter(user_id=new_teacher_user.id).first()
    assert new_teacher is not None
    assert new_teacher.college_id == college.id

    classes = await models.create_classes(
        name="组织1班",
        owner=manager_user,
        group_id=20101,
        teacher=manager,
        school=school,
        college=college,
    )
    new_student_user = await models.create_user(account_id=10104, nickname="新学生")
    async with app.test_matcher(add_student_profile_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"添加学生 {new_student_user.id} {classes.id} 新学生",
            user_id=10102,
            nickname="院负责人",
            message_id=3,
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("学生档案创建成功", "新学生", "组织1班")
    student = await Student.filter(user_id=new_student_user.id).first()
    assert student is not None
    assert student.classes_id == classes.id
    assert student.school_id == school.id


async def test_college_manager_cannot_manage_other_college(app, onebot, send_recorder, models):
    from src.plugins.application.active.group.commands import set_college_manager
    from src.plugins.application.active.teacher.commands import add_teacher_profile_cmd

    admin = await models.create_user(account_id=10111, nickname="管理员", is_admin=True)
    school = await models.create_school("边界大学")
    college_a = await models.create_college(school, "A学院")
    await models.create_college(school, "B学院")
    manager_user = await models.create_user(account_id=10112, nickname="A负责人")
    manager = await models.create_teacher(manager_user, name="A负责人", school=school, college=college_a)
    target_user = await models.create_user(account_id=10113, nickname="B教师")

    async with app.test_matcher(set_college_manager) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"设置学院负责人 边界大学 A学院 {manager.id}",
            user_id=10111,
            nickname=admin.nickname,
        )
        ctx.receive_event(bot, event)
    recorder.assert_any("A学院", "负责人")

    async with app.test_matcher(add_teacher_profile_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"添加教师 {target_user.id} B教师 边界大学 B学院",
            user_id=10112,
            nickname="A负责人",
            message_id=2,
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("只能在自己负责的学院内")


async def test_class_manager_can_set_teacher_and_student_positions(app, onebot, send_recorder, models):
    from src.models import Student, TeacherClasses
    from src.core.auth import UserRole, StudentRole, TeacherClassesRole
    from src.plugins.application.active.student.commands import set_cmd
    from src.plugins.application.active.classes.commands import set_class_teacher_cmd, set_student_position_cmd

    school = await models.create_school("岗位大学")
    college = await models.create_college(school, "信息学院")
    owner = await models.create_user(account_id=10121, nickname="班主任")
    manager = await models.create_teacher(owner, name="班主任", school=school, college=college)
    classes = await models.create_classes(
        name="岗位1班",
        owner=owner,
        group_id=20121,
        teacher=manager,
        school=school,
        college=college,
    )
    teacher_user = await models.create_user(account_id=10122, nickname="任课老师")
    teacher = await models.create_teacher(teacher_user, name="任课老师", school=school, college=college)
    student_user = await models.create_user(account_id=10123, nickname="学生甲")
    student = await models.create_student(student_user, classes=classes, name="学生甲")

    async with app.test_matcher(set_class_teacher_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"设置班级教师 {classes.id} {teacher.id} 班主任",
            user_id=10121,
            nickname="班主任",
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("任课老师", "班主任")
    relation = await TeacherClasses.filter(teacher_id=teacher.id, classes_id=classes.id).first()
    assert relation is not None
    assert relation.role == TeacherClassesRole.homeroom

    async with app.test_matcher(set_student_position_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"设置学生岗位 {student.id} 班助/助教",
            user_id=10121,
            nickname="班主任",
            message_id=2,
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("学生甲", "班助/助教")
    student = await Student.filter(id=student.id).first()
    assert student is not None
    assert student.role == StudentRole.assistant
    assert UserRole.class_cadre in student.user.roles

    async with app.test_matcher(set_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            "修改学生信息 角色=班长",
            user_id=10123,
            nickname="学生甲",
            message_id=3,
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("不能自行修改班级岗位")
    student = await Student.filter(id=student.id).first()
    assert student is not None
    assert student.role == StudentRole.assistant


async def test_my_info_bind_user_and_logout_flow(app, onebot, send_recorder, models, fake_cache, monkeypatch, tmp_path):
    from src.models import User
    from src.core.storage import StorageManager
    import src.models.models as model_definitions
    from src.plugins.application.active.user.commands import logout_cmd, bind_user_cmd, self_info_cmd

    storage = StorageManager(tmp_path / "storage")
    monkeypatch.setattr(model_definitions, "storage_manager", storage)

    user = await models.create_user(account_id=10012, nickname="信息用户")
    user_space = storage.user_space(user.id)
    user_space.touch("documents/profile.txt")
    user_space.chat_dir.joinpath("messages.db").write_text("logout chat", encoding="utf-8")

    async with app.test_matcher(self_info_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("我的信息", user_id=10012, nickname="信息用户")
        ctx.receive_event(bot, event)

    recorder.assert_any("用户信息", "信息用户")

    async with app.test_matcher(bind_user_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("绑定用户", user_id=10012, nickname="信息用户", message_id=2)
        ctx.receive_event(bot, event)

    recorder.assert_any("需要绑定平台", "token=")
    assert len(fake_cache.store) == 1
    assert str(user.id) in fake_cache.store.values()

    async with app.test_matcher(logout_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        prompt = onebot.private_event("注销 用户", user_id=10012, nickname="信息用户", message_id=3)
        confirm = onebot.private_event("yes", user_id=10012, nickname="信息用户", message_id=4)
        ctx.receive_event(bot, prompt)
        ctx.receive_event(bot, confirm)

    recorder.assert_any("您确定要注销", "用户")
    recorder.assert_any("注销成功")
    assert await User.filter(id=user.id).first() is None
    assert not user_space.space_root.exists()


async def test_help_menu_filters_commands_by_current_role(app, onebot, send_recorder, monkeypatch, models):
    from src.platform.helper import Helpers
    from nonebot_plugin_alconna import UniMessage
    from src.plugins.application.active.helper import help_cmd

    async def fake_render_pic(self):
        lines = []
        for group in self.group_by_scopes():
            lines.append(group.title)
            lines.extend(helper.command for helper in group.helpers)
        return "\n".join(lines).encode("utf-8")

    def fake_image(cls, raw=None, **kwargs):
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        return UniMessage.text(text)

    monkeypatch.setattr(Helpers, "render_pic", fake_render_pic)
    monkeypatch.setattr(UniMessage, "image", classmethod(fake_image))

    await models.create_user(account_id=10013, nickname="普通用户")
    async with app.test_matcher(help_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("help", user_id=10013, nickname="普通用户")
        ctx.receive_event(bot, event)

    recorder.assert_any("公共命令", "普通用户命令", "学生身份命令", "教师身份命令")

    teacher_user = await models.create_user(account_id=10014, nickname="教师用户")
    await models.create_teacher(teacher_user, name="教师用户")
    async with app.test_matcher(help_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("help", user_id=10014, nickname="教师用户", message_id=2)
        ctx.receive_event(bot, event)

    recorder.assert_any("公共命令", "普通用户命令", "教师身份命令", absent=("学生身份命令",))

    owner = await models.create_user(account_id=10015, nickname="学生班主任")
    teacher = await models.create_teacher(owner, name="学生班主任")
    classes = await models.create_classes(name="帮助班级", owner=owner, group_id=20006, teacher=teacher)
    student_user = await models.create_user(account_id=10016, nickname="学生用户")
    await models.create_student(student_user, classes=classes, name="学生用户")
    async with app.test_matcher(help_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("help", user_id=10016, nickname="学生用户", message_id=3)
        ctx.receive_event(bot, event)

    recorder.assert_any("公共命令", "普通用户命令", "学生身份命令", absent=("教师身份命令",))
