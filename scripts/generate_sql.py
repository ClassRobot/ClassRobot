# filepath: classrobot/scripts/generate_sql.py

import sys

import nonebot
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable

# 初始化 NoneBot
nonebot.init()

# 注册适配器
driver = nonebot.get_driver()


@driver.on_startup
async def on_startup():
    """处理启动事件。"""
    from nonebot_plugin_orm import Model as Base  # Assuming Base is the declarative base for your models

    def generate_sql_statements(database_url: str):
        """生成 SQL 语句。"""
        engine = create_engine(database_url)
        Base.metadata.reflect(bind=engine)

        sql_statements = []
        for table in Base.metadata.sorted_tables:
            sql_statements.append(str(CreateTable(table)))

        return sql_statements

    def main():
        """运行主入口。"""
        if len(sys.argv) != 2:
            print("Usage: python generate_sql.py <database_url>")
            sys.exit(1)

        database_url = sys.argv[1]
        sql_statements = generate_sql_statements(database_url)

        output_file = "generated_sql_statements.sql"
        with open(output_file, "w") as f:
            for statement in sql_statements:
                f.write(statement + ";\n\n")

        print(f"SQL statements generated and saved to {output_file}")

    main()


if __name__ == "__main__":
    nonebot.run()
