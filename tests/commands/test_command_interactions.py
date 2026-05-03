from __future__ import annotations

import pandas as pd
import pytest


pytestmark = pytest.mark.asyncio


async def test_login_edu_system_returns_fallback_message(app, onebot, send_recorder, monkeypatch):
    import src.managers.auth as auth_module
    from src.managers.auth.commands import login_edu_cmd

    monkeypatch.setattr(auth_module, "edu_logins", {})

    async with app.test_matcher(login_edu_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("登录教务系统 20250001 123456", user_id=10001, nickname="alice")
        ctx.receive_event(bot, event)

    recorder.assert_any("暂不支持该学校")


async def test_plain_user_can_create_and_query_teacher_profile(app, onebot, send_recorder, models):
    from src.managers.teacher.commands import query_teacher_cmd, set_teacher_cmd
    from utils.models import Teacher

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
    from src.managers.classes.commands import create_classes_cmd, query_classes_cmd
    from utils.models import Classes

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
    from src.managers.classes.commands import exit_classes_cmd, join_classes_cmd
    from utils.models import Student

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
    from src.managers.classes.commands import (
        join_classes_cmd,
        query_join_request_cmd,
        review_join_request_cmd,
        set_join_classes_cmd,
    )
    from utils.models import ClassesJoinRequest, Student

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


async def test_student_can_query_and_update_profile(app, onebot, send_recorder, models):
    from src.managers.student.commands import query_cmd, set_cmd
    from utils.models import Student

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


async def test_teacher_can_delete_empty_class(app, onebot, send_recorder, models):
    from src.managers.classes.commands import delete_classes_cmd
    from utils.models import Classes

    user = await models.create_user(account_id=10010, nickname="老师丙")
    teacher = await models.create_teacher(user, name="老师丙")
    classes = await models.create_classes(name="待删除班级", owner=user, group_id=20005, teacher=teacher)

    async with app.test_matcher(delete_classes_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(f"删除班级 {classes.id}", user_id=10010, nickname="老师丙")
        ctx.receive_event(bot, event)

    recorder.assert_any("删除班级成功")
    assert await Classes.filter(id=classes.id).first() is None


async def test_import_classes_can_create_teacher_class_and_student(app, onebot, send_recorder, monkeypatch, models):
    import src.managers.classes.depends as classes_depends
    from src.managers.classes.commands import import_classes_cmd
    from utils.models import Classes, Student, Teacher

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


async def test_my_info_bind_user_and_logout_flow(app, onebot, send_recorder, models, fake_cache):
    from src.managers.user.commands import bind_user_cmd, logout_cmd, self_info_cmd
    from utils.models import User

    user = await models.create_user(account_id=10012, nickname="信息用户")

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


async def test_help_menu_filters_commands_by_current_role(app, onebot, send_recorder, monkeypatch, models):
    import src.plugins.helper as helper_module
    from nonebot_plugin_alconna import UniMessage
    from src.plugins.helper import help_cmd

    async def fake_render_pic(self):
        lines = []
        for group in self.group_by_scopes():
            lines.append(group.title)
            lines.extend(helper.command for helper in group.helpers)
        return "\n".join(lines).encode("utf-8")

    def fake_image(cls, raw=None, **kwargs):
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        return UniMessage.text(text)

    monkeypatch.setattr(helper_module.Helpers, "render_pic", fake_render_pic)
    monkeypatch.setattr(helper_module.UniMessage, "image", classmethod(fake_image))

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
