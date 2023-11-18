from hashlib import md5


def get_token_md5(value: str) -> str:
    return md5(value.encode()).hexdigest()
