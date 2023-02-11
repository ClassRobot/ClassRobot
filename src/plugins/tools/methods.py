from typing import List

from utils.orm import ClassTable, StudentInfo
from utils.typing import BaseAuth
from utils.tools.docs_sheet import docs_url, GetDocsSheet, DataFrame
from utils.tools import html_to_image, check_data


class NotWriteExcel(BaseAuth):
    async def not_write_excel(self, excel_url: str, class_table: ClassTable):
        async with GetDocsSheet(excel_url) as sheet:
            if not sheet.data.empty:
                names = DataFrame(
                    [i async for i in StudentInfo.objects.filter(class_field=class_table).values("name")]
                )
                print(sheet.data["姓名"].isin(names))
                # names = [i["name"] for i in StudentInfo.objects.filter(
                #     class_field=class_table
                # ).values("name")]
            return "看不到表格里面的数据！"



class Watermark(BaseAuth):
    user: StudentInfo
    html = """
    <style>
        body { position: relative; }
        img { width: 100%; }
        .text { 
            top: 0;
            color: red;
            text-align: center;
            position: absolute; 
            font-size: 6em; 
            opacity: 0.6;
            left: 0;
            background-color: #ffffff50;
            font-weight: bold;
            width: 100%;
        }
    </style>
    """
    async def watermark(self, urls: List[str]):
        for url in urls:
            yield await html_to_image(
                self.html + 
                f"<img src='{url}'><hr>" + 
                f'<div class="text">{self.user.class_field.class_name}<br>{self.user.name}<br>{self.user.student_id}</div>',
                options={"width": 720}
            )