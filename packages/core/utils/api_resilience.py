import functools
import logging
import time

import requests

logger = logging.getLogger("core.api_resilience")

RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}

def retry_with_backoff(max_retries: int = 3, initial_delay: float = 0.2, backoff_factor: float = 2.0, exceptions=(Exception,)):
    """
    Decorator for retrying a function with exponential backoff on specified exceptions or HTTP rate-limits/server errors.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.warning(f"Function {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    logger.info(f"Attempt {attempt} for {func.__name__} failed ({e}). Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                    delay *= backoff_factor
            if last_exception:
                raise last_exception
        return wrapper
    return decorator

def safe_requests_get(url: str, params: dict = None, headers: dict = None, timeout: float = 5.0, max_retries: int = 2) -> tuple:
    """
    Safely executes a requests.get call with retries for 429 / 5xx responses and status verification.
    Returns (success: bool, data: dict | None).
    """
    delay = 0.2
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                try:
                    return True, resp.json()
                except Exception as je:
                    logger.warning(f"JSON decode error from {url}: {je}")
                    return False, None
            elif resp.status_code in RETRIABLE_STATUS_CODES:
                logger.warning(f"HTTP {resp.status_code} from {url} on attempt {attempt}/{max_retries}")
                if attempt < max_retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
            else:
                logger.warning(f"HTTP {resp.status_code} error from {url}")
                return False, None
        except requests.RequestException as re:
            logger.warning(f"Request exception for {url} on attempt {attempt}/{max_retries}: {re}")
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
    return False, None
