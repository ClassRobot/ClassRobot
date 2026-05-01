# WeChatFerry Architecture Notes

## Mental Model

WeChatFerry is not a normal SaaS API. It is a local automation bridge around the PC WeChat client:

1. A compatible Windows WeChat client runs and logs in.
2. WeChatFerry injects or loads native components beside that client.
3. The native side exposes WeChat operations through RPC.
4. Client libraries or `go_wcf_http` expose those operations to application code.

For Docker, the practical shape becomes:

```text
Browser -> noVNC:8088 -> Wine desktop -> Windows WeChat
ClassRobot or bridge -> HTTP:8000 -> go_wcf_http -> WeChatFerry RPC -> WeChat
WeChat message event -> CALLBACK_URL -> bridge/ClassRobot
```

## Why This Is Separate From ClassRobot

ClassRobot is a Python/NoneBot application and can run cleanly in a regular Linux Python container.

WeChatFerry has a very different runtime profile because it needs a PC WeChat process. Keeping it in `deploy/wechatferry` makes the boundary explicit:

- ClassRobot owns business logic.
- WeChatFerry owns the WeChat transport.
- A bridge or adapter owns event conversion between the two.

## Ports

| Host port | Container port | Purpose |
| --- | --- | --- |
| `8088` | `8080` | noVNC login and desktop access |
| `8000` | `8000` | WeChatFerry HTTP API |

## Persistent Data

`./data/wechat` is mounted to `/home/app/wechat` in the container. It keeps the Wine/WeChat profile and login state between restarts.

Do not commit this directory. It can contain account data, logs, avatars, downloaded files, and local WeChat databases.
