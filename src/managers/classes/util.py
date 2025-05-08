column_renames = {
    "name": ["姓名", "名字"],
    "student_id": "学号",
}


def rename(key: str) -> str:
    for k in column_renames:
        if isinstance(column_renames[k], str) and key == column_renames[k]:
            return k
        elif isinstance(column_renames[k], list) and key in column_renames[k]:
            return k
    return key
