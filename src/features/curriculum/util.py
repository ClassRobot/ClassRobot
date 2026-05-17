import re

times = [
    ["08:30", "09:15"],
    ["09:20", "10:05"],
    ["10:25", "11:10"],
    ["11:15", "12:00"],
    ["14:30", "15:15"],
    ["15:20", "16:05"],
    ["16:25", "17:10"],
    ["17:15", "18:00"],
    ["19:00", "19:45"],
    ["19:50", "20:35"],
    ["20:40", "21:25"],
]


# 解析1-13+1这种范围
def range_parser(range_str: str) -> list[int]:
    """解析范围参数

    1-13+1表示间隔1周,得到的是1,3,5,7,9,11,13
        +2表示间隔2周,得到的是1,4,7,10,13
    1-3,8,9,10表示1,2,3,8,9,10
    1-3,8-10表示1,2,3,8,9,10
    """
    if range_str.isdigit():
        return [int(range_str)]
    range_list = []

    pattern = re.compile(r"(\d+)-(\d+)(?:\+(\d+))?")
    for string in range_str.split(","):
        if string.isdigit():
            range_list.append(int(string))
            continue
        matches = pattern.findall(string)
        if not matches:
            return []
        matches = list(matches[0])
        if len(matches) == 2 or not matches[2]:
            matches[2] = 0
        range_list.extend(range(int(matches[0]), int(matches[1]) + 1, int(matches[2]) + 1))
    return range_list


# print(range_parser("1-14+1"))
# print(range_parser("1-3,8,9,10"))
# print(range_parser("1-3,8-10"))
# print(range_parser("1-3"))
# print(range_parser("1"))
