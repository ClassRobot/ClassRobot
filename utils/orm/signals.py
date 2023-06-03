from typing import Type
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import ClassTable, Teacher


@receiver(post_save, sender=ClassTable)
async def _(sender: Type[ClassTable], instance: ClassTable, **kwargs):
    teacher: Teacher = instance.teacher
    ...


@receiver(post_delete, sender=ClassTable)
async def _(sender: ClassTable, **kwargs):
    ...

