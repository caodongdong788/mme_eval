from datetime import datetime, timezone

from server.datetime_json import serialize_api_datetime


def test_serialize_naive_as_utc_z():
    assert serialize_api_datetime(datetime(2026, 6, 16, 7, 14, 8)) == "2026-06-16T07:14:08Z"


def test_serialize_aware_utc_z():
    aware = datetime(2026, 6, 16, 7, 14, 8, tzinfo=timezone.utc)
    assert serialize_api_datetime(aware) == "2026-06-16T07:14:08Z"
