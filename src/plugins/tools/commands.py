from nonebot import on_command


excel_not_write = on_command("未填写", aliases={"没填表"}, priority=100, block=True)
check_excel = on_command("检查错误", aliases={"表格错误", "检查"}, priority=100, block=True)
add_watermark = on_command("水印", aliases={"添加水印"}, priority=100, block=True)
reset_index = on_command("重置班级序号", aliases={"重置序号"}, priority=100, block=True)
rename = on_command("重命名", priority=100, block=True)
point = on_command("点到", priority=100, block=True)


__helper__ = [{
    "cmd": "重命名",
    "params": ["改成什么样子（默认：姓名 寝室 联系方式）"],
    "tags": ["取名", "学生", "教师"],
    "use": ["重命名 姓名 寝室 联系方式", "OK"]
}]
