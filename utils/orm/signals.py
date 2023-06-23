from typing import Type

from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete

from .models import Teacher, ClassTable


@receiver(post_save, sender=ClassTable)
async def _(sender: Type[ClassTable], instance: ClassTable, **kwargs):
    teacher: Teacher = instance.teacher
    ...


@receiver(post_delete, sender=ClassTable)
async def _(sender: ClassTable, **kwargs):
    ...
