# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class CampusNotice(models.Model):
    notice_id = models.AutoField(primary_key=True)

    class Meta:
        managed = False
        db_table = 'campus_notice'


class ClassCost(models.Model):
    fee_id = models.AutoField(primary_key=True)
    class_field = models.ForeignKey('ClassTable', models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.
    fee_type = models.CharField(max_length=255)
    fee_time = models.DateTimeField()
    fee_money = models.FloatField()
    invitee = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'class_cost'


class ClassTable(models.Model):
    class_id = models.AutoField(primary_key=True)
    guild_id = models.BigIntegerField(unique=True, blank=True, null=True)
    group_id = models.BigIntegerField(unique=True)
    major = models.ForeignKey('Major', models.DO_NOTHING)
    class_name = models.CharField(unique=True, max_length=100)
    teacher = models.ForeignKey('Teacher', models.DO_NOTHING)
    college = models.ForeignKey('College', models.DO_NOTHING)
    notice_group = models.BigIntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'class_table'


class ClassTaskCollects(models.Model):
    title = models.CharField(max_length=255)
    task = models.ForeignKey('ClassTasks', models.DO_NOTHING)
    qq = models.BigIntegerField()
    user_name = models.CharField(max_length=20)
    class_field = models.ForeignKey(ClassTable, models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.
    file = models.CharField(unique=True, max_length=255)
    push_time = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'class_task_collects'


class ClassTasks(models.Model):
    task_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    class_field = models.ForeignKey(ClassTable, models.DO_NOTHING, db_column='class_id', to_field='class_name')  # Field renamed because it was a Python reserved word.
    initiate = models.BigIntegerField()
    create_time = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'class_tasks'


class College(models.Model):
    college_id = models.AutoField(primary_key=True)
    college = models.CharField(unique=True, max_length=30)
    invitee = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'college'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class Feedback(models.Model):
    qq = models.BigIntegerField()
    files = models.TextField()
    context = models.TextField()
    log_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'feedback'


class Major(models.Model):
    major_id = models.AutoField(primary_key=True)
    major = models.CharField(unique=True, max_length=30)
    college = models.ForeignKey(College, models.DO_NOTHING)
    invitee = models.BigIntegerField()

    class Meta:
        managed = False
        db_table = 'major'


class MoralEducation(models.Model):
    class_field = models.ForeignKey(ClassTable, models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.
    score_type = models.CharField(max_length=50, blank=True, null=True)
    explain_reason = models.TextField(blank=True, null=True)
    student_name = models.CharField(max_length=20)
    student_id = models.BigIntegerField()
    score = models.IntegerField(blank=True, null=True)
    qq = models.BigIntegerField()
    log_time = models.DateTimeField()
    file = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'moral_education'


class PersonalSchedule(models.Model):
    qq = models.BigIntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    create_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'personal_schedule'


class StudentInfo(models.Model):
    qq = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=20)
    sex = models.CharField(max_length=8)
    student_id = models.BigIntegerField(unique=True)
    dorm_master = models.IntegerField()
    phone = models.BigIntegerField(unique=True)
    position = models.CharField(max_length=50)
    password = models.CharField(max_length=255, blank=True, null=True)
    class_index = models.IntegerField(blank=True, null=True)
    dormitory = models.CharField(max_length=10, blank=True, null=True)
    email = models.CharField(max_length=100, blank=True, null=True)
    wechat = models.CharField(max_length=100, blank=True, null=True)
    user_id = models.BigIntegerField(unique=True, blank=True, null=True)
    id_card = models.CharField(unique=True, max_length=20, blank=True, null=True)
    ethnic = models.CharField(max_length=200, blank=True, null=True)
    more_info = models.JSONField(blank=True, null=True)
    class_field = models.ForeignKey(ClassTable, models.DO_NOTHING, db_column='class_id')  # Field renamed because it was a Python reserved word.
    teacher = models.ForeignKey('Teacher', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'student_info'


class StudentUnion(models.Model):
    qq = models.ForeignKey(StudentInfo, models.DO_NOTHING, db_column='qq')
    name = models.CharField(max_length=20)
    position = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    college = models.ForeignKey(College, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'student_union'


class Teacher(models.Model):
    teacher_id = models.AutoField(primary_key=True)
    qq = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=30)
    phone = models.BigIntegerField(unique=True)
    invitee = models.BigIntegerField()
    password = models.CharField(max_length=30, blank=True, null=True)
    user_id = models.BigIntegerField(unique=True, blank=True, null=True)
    position = models.CharField(max_length=255, blank=True, null=True)
    class_list = models.JSONField(blank=True, null=True, default=list)

    class Meta:
        managed = False
        db_table = 'teacher'
