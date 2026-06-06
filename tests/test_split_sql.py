"""Smoke test for the SQL editor's statement splitter."""
import sys
sys.path.insert(0, '.')

from src.ui.chat_panel import ChatPanel

cases = [
    ("SELECT 1; SELECT 2;", ["SELECT 1", "SELECT 2"]),
    ("SELECT 1", ["SELECT 1"]),
    ("INSERT INTO t VALUES ('a;b'); SELECT 1;",
     ["INSERT INTO t VALUES ('a;b')", "SELECT 1"]),
    ("-- comment with ; semicolon\nSELECT 1; /* block ; comment */ SELECT 2;",
     ["-- comment with ; semicolon\nSELECT 1", "/* block ; comment */ SELECT 2"]),
    ("", []),
    ("  ;  SELECT 1  ;  ", ["SELECT 1"]),
    # No trailing semicolon
    ("SELECT 1;\nSELECT 2", ["SELECT 1", "SELECT 2"]),
    # Semicolon inside double-quoted identifier
    ('SELECT "weird;name" FROM t;', ['SELECT "weird;name" FROM t']),
]

ok = True
for inp, expected in cases:
    got = [s.strip() for s in ChatPanel._split_sql_statements(inp) if s.strip()]
    if got != expected:
        ok = False
        print(f"FAIL | in:  {inp!r}\n        got:      {got!r}\n        expected: {expected!r}")
    else:
        print(f"OK   | in:  {inp!r}\n        got: {got!r}")

print()
print("ALL OK" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
