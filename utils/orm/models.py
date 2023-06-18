# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class ClassFunds(models.Model):
    id: int
    class_table = models.ForeignKey(
        "ClassTable", models.DO_NOTHING, db_column="class_table"
    )
    description = models.TextField()
    money = models.FloatField()
    create_at = models.DateTimeField()
    creator = models.CharField(max_length=100)

    class Meta:
        db_table = "class_funds"


class ClassTable(models.Model):
    id: int
    group_id = models.BigIntegerField(unique=True)
    name = models.CharField(unique=True, max_length=100)
    teacher = models.ForeignKey("Teacher", models.DO_NOTHING, db_column="teacher")
    major = models.ForeignKey("Major", models.DO_NOTHING, db_column="major")

    class Meta:
        db_table = "class_table"


class ClassTasks(models.Model):
    id: int
    title = models.CharField(max_length=255)
    task_type = models.CharField(max_length=255)
    class_table = models.ForeignKey(
        ClassTable, models.DO_NOTHING, db_column="class_table"
    )
    creator = models.CharField(max_length=100)
    completed = models.IntegerField()
    create_time = models.DateTimeField()

    class Meta:
        db_table = "class_tasks"


class College(models.Model):
    id: int
    college = models.CharField(unique=True, max_length=100)
    creator = models.CharField(max_length=100)

    class Meta:
        db_table = "college"


class Feedback(models.Model):
    id: int
    qq = models.BigIntegerField()
    content = models.TextField()
    image_md5 = models.CharField(max_length=255, blank=True, null=True)
    create_at = models.DateTimeField()

    class Meta:
        db_table = "feedback"


class Major(models.Model):
    id: int
    college = models.ForeignKey(College, models.DO_NOTHING, db_column="college")
    major = models.CharField(unique=True, max_length=100)
    creator = models.CharField(max_length=100)

    class Meta:
        db_table = "major"


class MoralEducation(models.Model):
    id: int
    class_table = models.ForeignKey(
        ClassTable, models.DO_NOTHING, db_column="class_table"
    )
    qq = models.ForeignKey("Student", models.DO_NOTHING, db_column="qq")
    activity_type = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField()
    score = models.IntegerField()
    create_at = models.DateTimeField()
    prove = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "moral_education"


class Student(models.Model):
    qq = models.BigIntegerField(
        db_column="QQ", primary_key=True
    )  # Field name made lowercase.
    name = models.CharField(max_length=20)
    class_table = models.ForeignKey(
        ClassTable, models.DO_NOTHING, db_column="class_table"
    )
    student_id = models.BigIntegerField(unique=True, blank=True, null=True)
    phone = models.BigIntegerField(unique=True, blank=True, null=True)
    id_card = models.CharField(unique=True, max_length=20, blank=True, null=True)
    wechat = models.CharField(unique=True, max_length=100, blank=True, null=True)
    email = models.CharField(unique=True, max_length=100, blank=True, null=True)
    position = models.CharField(max_length=50)
    sex = models.CharField(max_length=10, blank=True, null=True)
    class_order = models.IntegerField(blank=True, null=True)
    birthday = models.DateTimeField(blank=True, null=True)
    dorm = models.CharField(max_length=20, blank=True, null=True)
    dorm_head = models.IntegerField()
    ethnic = models.CharField(max_length=200, blank=True, null=True)
    birthplace = models.CharField(max_length=200, blank=True, null=True)
    politics = models.CharField(max_length=50, blank=True, null=True)
    address = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        db_table = "student"


class StudentCouncil(models.Model):
    id: int
    student = models.ForeignKey(Student, models.DO_NOTHING, db_column="student")
    department = models.CharField(max_length=50)
    position = models.CharField(max_length=50)

    class Meta:
        db_table = "student_council"


class TaskFiles(models.Model):
    id: int
    class_tasks = models.ForeignKey(
        ClassTasks, models.DO_NOTHING, db_column="class_tasks"
    )
    student = models.ForeignKey(Student, models.DO_NOTHING, db_column="student")
    file_md5 = models.CharField(max_length=255)
    push_time = models.DateTimeField()

    class Meta:
        db_table = "task_files"


class Teacher(models.Model):
    id: int
    qq = models.BigIntegerField(unique=True)
    name = models.CharField(max_length=20)
    creator = models.CharField(max_length=100)
    phone = models.BigIntegerField(unique=True)
    email = models.CharField(unique=True, max_length=100, blank=True, null=True)

    class Meta:
        db_table = "teacher"
