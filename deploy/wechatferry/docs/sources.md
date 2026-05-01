# Sources Checked

- Docker Hub: `jackytj/wcf-docker`
  - https://hub.docker.com/r/jackytj/wcf-docker
  - Runs WeChatFerry's Go HTTP service in Wine.
  - Exposes noVNC on container port `8080`.
  - Exposes API on container port `8000`.
  - Uses `CALLBACK_URL` for message callbacks; multiple callbacks can be comma-separated.
  - Notes the image is large.
- WeChatFerry documentation
  - https://wechatferry.readthedocs.io/zh/latest/readme_link.html
  - Current docs mark the older `wcfhttp` client as unmaintained.
  - Current docs recommend WcfRust or GoHttp for HTTP-style access.
- WeChatFerry project references
  - https://deepwiki.com/lich0821/WeChatFerry
  - Project provides client implementations across Python, Go HTTP, Node.js, C#, and Rust.
  - Version compatibility follows the WeChat client version closely, so the Docker image and bundled WeChat version matter.
