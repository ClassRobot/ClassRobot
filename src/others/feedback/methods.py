from typing import Optional
from base64 import b64encode

from utils.models import Feedback
from utils.typings import SaveFile
from utils.localstore import LocalStore
from django.db.models.functions import Now
from utils.tools import query_date, html_to_image
from utils.tools.templates import create_template_env

local_store = LocalStore("feedback")
env = create_template_env("feedback")


class PushFeedback:
    def __init__(self) -> None:
        self.save_file = SaveFile()
        self.save_file.local_store = local_store

    async def push_feedback(self, text: str, user_id: int):
        await Feedback.objects.acreate(
            context=text,
            student=user_id,
            image_md5=",".join(self.save_file.files),
            create_at=Now(),
        )
        await self.save_file.save(True)


class ShowFeedback:
    async def show_feedback(self, string: str) -> Optional[bytes]:
        if string.startswith("#"):
            template = env.get_template("feedback.html")
            if feedback := await Feedback.objects.filter(id=string[1:]).afirst():
                return await html_to_image(
                    await template.render_async(
                        feedback=feedback,
                        images=[
                            "data:image/jpeg;base64,"
                            + b64encode(local_store.read_bytes(i)).decode("utf-8")
                            for i in (feedback.image_md5 or "").split(",")
                        ],
                    ),
                    options={"width": 1000},
                )
        else:
            qd: dict = query_date(string, "log_date")  # type: ignore
            feedbacks = [i async for i in Feedback.objects.filter(**qd)]
            feedbacks.reverse()
            template = env.get_template("feedbacklist.html")
            return await html_to_image(
                await template.render_async(
                    date="-".join(str(i) for i in qd.values()),
                    feedbacks=feedbacks,
                    count=len(feedbacks),
                ),
                options={"width": 1000},
            )
