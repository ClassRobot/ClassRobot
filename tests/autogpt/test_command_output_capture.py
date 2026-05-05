import pytest


class FakeMessage:
    """模拟适配器消息对象。"""

    def extract_plain_text(self) -> str:
        return "命令返回的纯文本"


class FakeBot:
    """提供最小化 send 接口，便于测试输出捕获。"""

    def __init__(self) -> None:
        self.sent_messages: list[object] = []

    async def send(self, event, message, **kwargs):
        self.sent_messages.append(message)
        return {"message_id": len(self.sent_messages)}


@pytest.mark.asyncio
async def test_handle_event_with_output_capture_records_command_replies(loaded_plugins, monkeypatch):
    from src.plugins import autogpt as autogpt_module

    async def fake_handle_event(bot, event):
        await bot.send(event=event, message="第一条命令回复")
        await bot.send(event=event, message=FakeMessage())
        unrelated_event = object()
        await bot.send(event=unrelated_event, message="并发无关回复")

    bot = FakeBot()
    original_send = bot.send
    event = object()

    monkeypatch.setattr(autogpt_module, "handle_event", fake_handle_event)

    outputs = await autogpt_module.handle_event_with_output_capture(bot, event)

    assert outputs == ["第一条命令回复", "命令返回的纯文本"]
    assert len(bot.sent_messages) == 3
    assert bot.sent_messages[0] == "第一条命令回复"
    assert isinstance(bot.sent_messages[1], FakeMessage)
    assert bot.sent_messages[2] == "并发无关回复"
    assert bot.send.__self__ is bot
    assert bot.send.__func__ is original_send.__func__


def test_stringify_command_output_falls_back_to_message_string(loaded_plugins):
    from src.plugins import autogpt as autogpt_module

    assert autogpt_module.stringify_command_output(123) == "123"


def test_autogpt_relies_on_global_send_recorder(loaded_plugins):
    from src.plugins import autogpt as autogpt_module

    assert not hasattr(autogpt_module, "record_reply_history")
    assert not hasattr(autogpt_module, "send_reply_and_record")
