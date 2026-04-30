import pytest

from core.sql_safe import preview_query, validate_readonly_sql


class TestValidateReadonlySql:
    def test_accepts_simple_select(self):
        assert validate_readonly_sql("SELECT 1") == "SELECT 1"

    def test_strips_trailing_semicolon(self):
        assert validate_readonly_sql("SELECT 1;") == "SELECT 1"

    def test_accepts_cte(self):
        q = "WITH cte AS (SELECT 1 AS x) SELECT * FROM cte"
        assert validate_readonly_sql(q) == q

    def test_case_insensitive_start(self):
        assert validate_readonly_sql("select 1") == "select 1"
        assert validate_readonly_sql("With t AS (SELECT 1) SELECT * FROM t").startswith("With")

    @pytest.mark.parametrize("bad", [
        "DELETE FROM users",
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET x=1",
        "TRUNCATE TABLE t",
        "DROP TABLE users",
        "ALTER TABLE t ADD COLUMN x INT",
        "MERGE INTO t USING s ON ...",
        "GRANT SELECT ON t TO u",
        "CREATE TABLE t (x INT)",
    ])
    def test_rejects_writes(self, bad):
        with pytest.raises(ValueError):
            validate_readonly_sql(bad)

    @pytest.mark.parametrize("bad", [
        "SELECT 1; DROP TABLE x",
        "SELECT * FROM t; SELECT 2",
        "SELECT 1 -- comment",
        "SELECT /* x */ 1",
        "SELECT 1 */",
    ])
    def test_rejects_multistatement_or_comment(self, bad):
        with pytest.raises(ValueError):
            validate_readonly_sql(bad)

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            validate_readonly_sql("")

    def test_rejects_non_string(self):
        with pytest.raises(ValueError):
            validate_readonly_sql(None)


class TestPreviewQuery:
    def test_wraps_with_default_limit(self):
        out = preview_query("SELECT 1")
        assert out == "SELECT * FROM (SELECT 1) AS _preview LIMIT 5"

    def test_wraps_with_custom_limit_and_alias(self):
        out = preview_query("SELECT 1", limit=10, alias="t")
        assert out == "SELECT * FROM (SELECT 1) AS t LIMIT 10"

    def test_rejects_zero_or_negative_limit(self):
        with pytest.raises(ValueError):
            preview_query("SELECT 1", limit=0)
        with pytest.raises(ValueError):
            preview_query("SELECT 1", limit=-1)

    def test_propagates_validation_error(self):
        with pytest.raises(ValueError):
            preview_query("DROP TABLE x")
