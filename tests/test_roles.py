from tableprobe.roles import infer_role


def test_identifier_rule_hits_id_names_and_rejects_plain_names():
    assert infer_role("user_id", "BIGINT", distinct_count=30, non_null_count=30).role == "identifier"
    assert infer_role("id", "INTEGER", distinct_count=3, non_null_count=3).role == "identifier"
    assert infer_role("order_uuid", "VARCHAR", distinct_count=5, non_null_count=5).role == "identifier"
    assert infer_role("guid_no", "VARCHAR", distinct_count=5, non_null_count=5).role == "identifier"
    decision = infer_role("identity", "VARCHAR", distinct_count=5, non_null_count=5)
    assert decision.role == "dimension"
    assert "标识" not in decision.reason


def test_primary_key_is_identifier_even_when_the_name_is_ordinary():
    hit = infer_role(
        "sku",
        "BIGINT",
        distinct_count=30,
        non_null_count=30,
        is_primary_key=True,
    )
    missed = infer_role("sku", "BIGINT", distinct_count=30, non_null_count=30)
    assert hit.role == "identifier"
    assert "主键" in hit.reason
    assert missed.role == "measure"


def test_time_rule_hits_temporal_types_and_rejects_text():
    assert infer_role("created", "TIMESTAMP", distinct_count=4, non_null_count=4).role == "time"
    assert infer_role("created", "DATE", distinct_count=4, non_null_count=4).role == "time"
    decision = infer_role("created_at", "VARCHAR", distinct_count=4, non_null_count=4)
    assert decision.role == "dimension"
    assert decision.role != "time"


def test_time_rule_wins_over_a_year_name():
    decision = infer_role("year", "DATE", distinct_count=4, non_null_count=4)
    assert decision.role == "time"


def test_name_rule_marks_codes_as_dimensions_and_leaves_amounts_alone():
    year = infer_role("year", "INTEGER", distinct_count=30, non_null_count=30)
    rating = infer_role("评分", "INTEGER", distinct_count=30, non_null_count=30)
    amount = infer_role("amount", "INTEGER", distinct_count=30, non_null_count=30)
    assert year.role == "dimension"
    assert "年份" in year.reason
    assert rating.role == "dimension"
    assert amount.role == "measure"


def test_low_cardinality_numbers_are_dimensions_and_wide_numbers_are_measures():
    low = infer_role("qty", "INTEGER", distinct_count=20, non_null_count=100)
    wide = infer_role("qty", "INTEGER", distinct_count=21, non_null_count=100)
    ratio = infer_role("qty", "BIGINT", distinct_count=21, non_null_count=1000)
    tiny = infer_role("qty", "INTEGER", distinct_count=21, non_null_count=19)
    assert low.role == "dimension"
    assert "很少" in low.reason
    assert wide.role == "measure"
    assert ratio.role == "dimension"
    assert tiny.role == "measure"


def test_boolean_and_string_are_dimensions():
    assert infer_role("flag", "BOOLEAN", distinct_count=2, non_null_count=10).role == "dimension"
    city = infer_role("city", "VARCHAR", distinct_count=8, non_null_count=8)
    assert city.role == "dimension"
    assert "文本" in city.reason
    amount = infer_role("amount", "DOUBLE", distinct_count=40, non_null_count=40)
    assert amount.role == "measure"
    assert "布尔" not in amount.reason
    assert "文本" not in amount.reason


def test_unknown_type_is_reported_and_text_is_not_unknown():
    blob = infer_role("payload", "BLOB", distinct_count=3, non_null_count=3)
    city = infer_role("city", "VARCHAR", distinct_count=3, non_null_count=3)
    assert blob.role == "unknown"
    assert "BLOB" in blob.reason
    assert city.role != "unknown"
