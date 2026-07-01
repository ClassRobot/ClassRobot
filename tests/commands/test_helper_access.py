def test_roles_are_matched_by_any_role_instead_of_subset(loaded_plugins):
    from src.platform.helper import Helper, Helpers, UserRole

    helpers = Helpers()
    helpers.append(
        Helper(
            command="查询请假",
            description="查询请假信息",
            roles={UserRole.student, UserRole.teacher, UserRole.class_cadre},
        )
    )

    student_visible = helpers.get_roles_helpers(UserRole.user, UserRole.student)
    teacher_visible = helpers.get_roles_helpers(UserRole.user, UserRole.teacher)

    assert student_visible.get_helper("查询请假") is not None
    assert teacher_visible.get_helper("查询请假") is not None


def test_excluded_roles_can_block_teacher_or_student_paths(loaded_plugins):
    from src.platform.helper import Helper, UserRole, HelperScope

    helper = Helper(
        command="添加班级",
        description="创建班级",
        roles={UserRole.user, UserRole.teacher},
        exclude_roles={UserRole.student},
        scopes={HelperScope.teacher},
    )

    assert helper.is_available_for(UserRole.user)
    assert helper.is_available_for(UserRole.user, UserRole.teacher)
    assert not helper.is_available_for(UserRole.user, UserRole.student)


def test_help_groups_keep_current_role_visible_scopes_only(loaded_plugins):
    from src.platform.helper import Helper, Helpers, UserRole, HelperScope

    helpers = Helpers()
    helpers.extend(
        [
            Helper(command="help", description="帮助", scopes={HelperScope.public}),
            Helper(command="我的信息", description="查看信息", roles={UserRole.user}, scopes={HelperScope.user}),
            Helper(
                command="加入班级",
                description="加入班级",
                roles={UserRole.user},
                exclude_roles={UserRole.teacher, UserRole.student},
                scopes={HelperScope.student},
            ),
            Helper(
                command="查询学生信息", description="查看学生", roles={UserRole.student}, scopes={HelperScope.student}
            ),
            Helper(
                command="查询教师信息", description="查看教师", roles={UserRole.teacher}, scopes={HelperScope.teacher}
            ),
            Helper(
                command="查询请假",
                description="学生和教师都能查看请假记录",
                roles={UserRole.student, UserRole.teacher, UserRole.class_cadre},
                scopes={HelperScope.student, HelperScope.teacher},
            ),
            Helper(
                command="修改教师信息",
                description="普通用户可创建教师身份，教师本人也可继续修改",
                roles={UserRole.user, UserRole.teacher},
                exclude_roles={UserRole.student},
                scopes={HelperScope.teacher},
            ),
        ]
    )

    student_groups = helpers.get_roles_helpers(UserRole.user, UserRole.student).group_by_scopes()
    assert [group.key for group in student_groups] == [HelperScope.public, HelperScope.user, HelperScope.student]
    assert {helper.command for helper in student_groups[-1].helpers} == {"查询学生信息", "查询请假"}

    plain_user_groups = helpers.get_roles_helpers(UserRole.user).group_by_scopes()
    assert [group.key for group in plain_user_groups] == [
        HelperScope.public,
        HelperScope.user,
        HelperScope.student,
        HelperScope.teacher,
    ]
    plain_user_group_map = {group.key: {helper.command for helper in group.helpers} for group in plain_user_groups}
    assert plain_user_group_map[HelperScope.student] == {"加入班级"}
    assert plain_user_group_map[HelperScope.teacher] == {"修改教师信息"}

    teacher_groups = helpers.get_roles_helpers(UserRole.user, UserRole.teacher).group_by_scopes()
    assert [group.key for group in teacher_groups] == [HelperScope.public, HelperScope.user, HelperScope.teacher]
    assert {helper.command for helper in teacher_groups[-1].helpers} == {
        "查询教师信息",
        "查询请假",
        "修改教师信息",
    }
