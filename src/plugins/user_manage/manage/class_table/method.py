from re import findall


def split_class_name(class_name: str):
    """
    分割班级名称
    :param class_name: 班级名称
    :return: 班级名称
    """
    split = findall(r"\S[^\d]+|\d+", class_name)[:2]
    if len(split) > 1:
        expertise, class_id = split
        if expertise.isdigit():
            return [class_id, expertise]
        return [expertise, class_id]
