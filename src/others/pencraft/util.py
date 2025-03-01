from base64 import b64encode


def footer(image: bytes) -> str:
    return f"""
    <footer style="
        text-align: right; 
        border-top: 1px solid gray; 
        padding-top: 10px;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-left: 2em;
        padding-right: 2em;
    ">
        <p style="margin-right: 10px; display: inline-block;">扫码下载</p>
        <img src="data:image/png;base64,{b64encode(image).decode()}" alt="footer" width="100">
    </footer>
    """
