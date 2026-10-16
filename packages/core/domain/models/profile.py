from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Profile(BaseModel):
    """
    Domain model for a user profile with quota management.
    """
    name: str
    daily_limit: int = Field(default=50, description="Max requests allowed per 24h window")
    requests_today: int = Field(default=0, description="Number of requests made in the current window")
    tokens_today: int = Field(default=0, description="Total tokens consumed today")
    quota_reset_at: Optional[datetime] = Field(default=None, description="When the quota will reset")
    last_used: Optional[datetime] = Field(default=None, description="Timestamp of the last request")

    def increment_request(self, tokens: int = 0):
        """Updates request count and last used timestamp."""
        self.requests_today += 1
        self.tokens_today += tokens
        self.last_used = datetime.now(timezone.utc)

    def is_quota_exceeded(self) -> bool:
        """Checks if the daily limit has been reached."""
        if self.requests_today >= self.daily_limit:
            return True
        return False

    def reset_quota(self):
        """Manually resets the quota counters."""
        self.requests_today = 0
        self.tokens_today = 0
        self.quota_reset_at = None
