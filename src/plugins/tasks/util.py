from utils.tools import StringCard
from utils.models import Tasks, Student


class TaskManager:
    def __init__(self, *tasks: Tasks):
        self.tasks: list[Tasks] = list(tasks)

    def add_task(self, *task):
        self.tasks.extend(task)

    def get_task(self, task_id: int | str) -> Tasks | None:
        for task in self.tasks:
            if task.id == task_id or task.name == task_id:
                return task
        return None

    def tasks_string(self):
        card = StringCard()
        for task in self.tasks:
            (
                card.hr()
                .text("任务ID:", str(task.id))
                .text("任务名称:", task.name)
                .text("所属班级:", task.classes.name)
                .text("已提交数:", f"{len(task.commits)}/{len(task.classes.students)}")
                .text("创建日期:", task.created_at.strftime("%Y-%m-%d"))
            )
        return card.render()

    def commits(
        self, task_id: int | str
    ) -> tuple[tuple[Student, ...], tuple[Student, ...]]:
        """已提交和未提交的学生

        Args:
            task_id (int | str): 任务ID或任务名称

        Returns:
            tuple[tuple[Student, ...], tuple[Student, ...]]: 已提交, 未提交
        """
        if task := self.get_task(task_id):
            submitted = tuple(commit.student for commit in task.commits)
            submitted_names = tuple(student.name for student in submitted)
            students = tuple(task.classes.students)
            print(students)
            not_submitted = tuple(
                student for student in students if student.name not in submitted_names
            )
            return submitted, not_submitted
        return tuple(), tuple()

    def __bool__(self) -> bool:
        return bool(self.tasks)
