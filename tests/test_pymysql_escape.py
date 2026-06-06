"""Quick smoke test for the pymysql % escape helper."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database.adapters.mysql_adapter import _escape_percent_for_pymysql as f

cases = [
    ("LIKE '%sl%'", "LIKE '%%sl%%'"),
    ("WHERE id = %s", "WHERE id = %s"),
    ("-- 100% match", "-- 100%% match"),
    ("WHERE x = 'a%' AND id = %s", "WHERE x = 'a%%' AND id = %s"),
    ("SELECT * FROM t WHERE a LIKE '%' OR b = %s", "SELECT * FROM t WHERE a LIKE '%%' OR b = %s"),
    # SQL 风格的双引号转义
    ("WHERE x = 'it''s 100%'", "WHERE x = 'it''s 100%%'"),
    # 反引号标识符里的 % 也转义（pymysql 不认反引号边界）
    ("SELECT `col%name` FROM `t%`", "SELECT `col%%name` FROM `t%%`"),
    # 多个占位符
    ("INSERT INTO t (a, b) VALUES (%s, %s)", "INSERT INTO t (a, b) VALUES (%s, %s)"),
    # 浮点占位符
    ("SELECT * FROM t WHERE x = %f", "SELECT * FROM t WHERE x = %f"),
    # 字符串里的 %% 也得转义（pymysql 不认 SQL 边界）
    ("SELECT '%%literal%%'", "SELECT '%%%%literal%%%%'"),
    # 块注释里的 %
    ("/* 50% off */ SELECT 1", "/* 50%% off */ SELECT 1"),
    # 多行注释 + 字面量 %
    ("-- header\nSELECT *\nFROM t\nWHERE name LIKE '%abc%'", "-- header\nSELECT *\nFROM t\nWHERE name LIKE '%%abc%%'"),
    # 真实日志里那条
    ("-- Query to find all roles for the user with identifier 'sl'\nSELECT u.USER_ID FROM users u WHERE u.USER_NAME LIKE '%sl%'",
     "-- Query to find all roles for the user with identifier 'sl'\nSELECT u.USER_ID FROM users u WHERE u.USER_NAME LIKE '%%sl%%'"),
]

ok = True
for inp, expected in cases:
    got = f(inp)
    status = "OK" if got == expected else "FAIL"
    if got != expected:
        ok = False
    print(f"{status} | {inp!r}\n        -> {got!r}")
    if got != expected:
        print(f"        EXPECTED: {expected!r}")

print()
print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
