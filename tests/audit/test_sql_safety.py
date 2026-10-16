from packages.core.infrastructure.persistence.database import Database


def run_test(sql, params=()):
    try:
        Database._validate_sql_safety(sql, params)
        print("Allowed: " + sql)
    except Exception as e:
        print("Blocked: " + sql + " -> " + str(e))

run_test("SELECT * FROM expenses WHERE amount > 0")
run_test("SELECT * FROM expenses WHERE status = 1")
run_test("SELECT * FROM expenses WHERE status = ?", (1,))
run_test("SELECT * FROM expenses WHERE description LIKE '%test%'")
run_test("SELECT * FROM expenses WHERE id IN (1, 2, 3)")
run_test("INSERT INTO table (id) VALUES (1)")
run_test("SELECT * FROM table LIMIT 10")
run_test("SELECT * FROM table WHERE 1=1")
