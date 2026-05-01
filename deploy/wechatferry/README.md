# WeChatFerry Docker Deployment

This directory contains the Docker deployment assets for running WeChatFerry beside ClassRobot.

## What This Runs

The compose file uses `jackytj/wcf-docker`, a community image that runs WeChatFerry's Go HTTP service in Wine. It exposes:

- `8088` on the host for noVNC login, mapped to container `8080`
- `8000` on the host for the WeChatFerry HTTP API, mapped to container `8000`
- `./data/wechat` for persisted WeChat data

WeChatFerry itself works by controlling a Windows WeChat client through hook/RPC capabilities. In this Docker image, that Windows client runs under Wine and is accessed through noVNC.

## Start

```powershell
cd deploy/wechatferry
docker compose up -d
```

Then open:

```text
http://127.0.0.1:8088/vnc.html
```

Scan the QR code in the VNC desktop to log in to the bot WeChat account.

## Configure

Copy `.env.example` to `.env` if you need to change ports, image, container name, or callback URL:

```powershell
cd deploy/wechatferry
Copy-Item .env.example .env
```

Common settings:

```dotenv
WCF_VNC_PORT=8088
WCF_API_PORT=8000
WCF_CALLBACK_URL=http://host.docker.internal:8080/api/bot/ferry
```

Use a LAN IP instead of `host.docker.internal` when deploying to a Linux server or another machine:

```dotenv
WCF_CALLBACK_URL=http://192.168.1.10:8080/api/bot/ferry
```

## Useful Commands

```powershell
cd deploy/wechatferry
docker compose ps
docker compose logs -f
docker compose restart
docker compose down
```

## ClassRobot Integration Notes

ClassRobot currently has OneBot adapters configured. This WeChatFerry deployment provides a WeChatFerry HTTP API, not a OneBot API by itself.

Recommended integration path:

1. Keep WeChatFerry as the WeChat transport service.
2. Add or choose a small adapter layer that converts WeChatFerry callbacks into the event shape ClassRobot expects.
3. Point `WCF_CALLBACK_URL` at that adapter layer.
4. Use `http://127.0.0.1:8000/` as the WeChatFerry API base URL for outbound messages.

If ClassRobot runs in another Docker service on the same compose network, use `http://wechatferry:8000/` for the API base URL and set callback URLs to the service name of the bridge.

## Caveats

- The image is large because it bundles Wine, WeChat, noVNC, and WeChatFerry.
- Login state and message data are stored under `deploy/wechatferry/data/wechat`.
- This is a community Docker image, not an official WeChatFerry release artifact.
- Use a dedicated bot WeChat account and comply with WeChat rules and local law.
