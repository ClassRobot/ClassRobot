from typing import Generator

line = "—" * 10


def select_formant(id: str | int, name: str) -> str:
    return f"{line}\n[ {id} ] {name}"


def select_list(prompt: str, info_list: Generator[str, None, None]):
    return f"{prompt}\n" + "\n".join(info_list) + f"\n{line}\n★ 格式为 [ id ] 名称"
