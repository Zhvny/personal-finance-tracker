def month_range(year: int, month: int):
    """Return (start, end) ISO date strings for a calendar month."""
    start = f"{year:04d}-{month:02d}-01"
    end   = (
        f"{year:04d}-{month+1:02d}-01"
        if month < 12 else
        f"{year+1:04d}-01-01"
    )
    return start, end

def prev_month(year: int, month: int):
    return (year - 1, 12) if month == 1 else (year, month - 1)
