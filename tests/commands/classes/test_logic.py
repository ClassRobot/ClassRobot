from datetime import datetime


def test_normalize_cell_handles_common_import_values(loaded_plugins):
    from src.features.classes import normalize_cell

    assert normalize_cell(None) is None
    assert normalize_cell("") is None
    assert normalize_cell("  软件1班  ") == "软件1班"
    assert normalize_cell(float("nan")) is None
    assert normalize_cell(202401.0) == "202401"
    assert normalize_cell(202401.5) == "202401.5"


def test_normalize_datetime_accepts_supported_formats(loaded_plugins):
    from src.features.classes import normalize_datetime

    assert normalize_datetime(None) is None
    assert normalize_datetime("2026-05-02") == datetime(2026, 5, 2)
    assert normalize_datetime("2026/05/02") == datetime(2026, 5, 2)
    assert normalize_datetime("2026.05.02") == datetime(2026, 5, 2)
    assert normalize_datetime("2026-05-02 15:30:00") == datetime(2026, 5, 2, 15, 30)
    assert normalize_datetime("not-a-date") is None


def test_join_method_and_request_action_aliases_are_supported(loaded_plugins):
    from src.features.classes import JOIN_METHOD_MAPPING, JOIN_REQUEST_ACTION_MAPPING, get_join_method_label
    from utils.roles import JoinMethod

    assert JOIN_METHOD_MAPPING["直接"] == JoinMethod.direct
    assert JOIN_METHOD_MAPPING["申请加入"] == JoinMethod.apply
    assert JOIN_METHOD_MAPPING["邀请"] == JoinMethod.invite
    assert JOIN_REQUEST_ACTION_MAPPING["通过"] == "approve"
    assert JOIN_REQUEST_ACTION_MAPPING["拒绝"] == "reject"
    assert get_join_method_label("direct") == "直接通过"
    assert get_join_method_label(None) == "未设置"
