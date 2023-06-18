from typing import Dict, List

from django.db.models import Q
from utils.tools.templates import create_template_env

env = create_template_env("tasks")


class TaskFinder:
    def __init__(self, title: str) -> None:
        self.task_id = []
        self.title = []
        for i in title.split():
            if i.isdigit():
                self.task_id.append(i)
            else:
                self.title.append(i)

    def to_Q(self) -> Q:
        return Q(task_id__in=self.task_id) | Q(title__in=self.title)

    def to_dict(self) -> Dict[str, List[str]]:
        return {"task_id": self.task_id.copy(), "title": self.title.copy()}

    def __bool__(self) -> bool:
        return bool(self.task_id or self.title)
