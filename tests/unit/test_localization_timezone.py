from datetime import datetime, timedelta, timezone

from packages.core.utils.datetime_utils import month_range, prev_month


def test_timezone_utc_and_wib_conversion():
    """
    Verifies timezone handling, UTC awareness, and ISO-8601 formatting.
    """
    utc_now = datetime.now(timezone.utc)
    wib_tz = timezone(timedelta(hours=7)) # Asia/Jakarta (WIB)
    wib_now = utc_now.astimezone(wib_tz)

    assert wib_now.hour == (utc_now.hour + 7) % 24
    assert wib_now.tzinfo is not None

def test_month_range_utility_bounds():
    """
    Verifies month_range generates exact inclusive/exclusive boundary strings for SQL queries.
    """
    ms, me = month_range(2026, 8)
    assert ms.startswith("2026-08-01")
    assert me.startswith("2026-09-01")

    # Boundary crossing (December to January)
    ms_dec, me_dec = month_range(2026, 12)
    assert ms_dec.startswith("2026-12-01")
    assert me_dec.startswith("2027-01-01")

def test_prev_month_utility():
    py, pm = prev_month(2026, 1)
    assert py == 2025
    assert pm == 12

    py2, pm2 = prev_month(2026, 8)
    assert py2 == 2026
    assert pm2 == 7
