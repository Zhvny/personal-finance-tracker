from packages.core.domain.models.profile import Profile


def test_profile_quota_initial_state():
    profile = Profile(name="personal")
    assert profile.requests_today == 0
    assert profile.daily_limit == 50
    assert profile.is_quota_exceeded() is False

def test_profile_quota_increment():
    profile = Profile(name="personal", daily_limit=2)
    profile.increment_request(tokens=100)
    assert profile.requests_today == 1
    assert profile.tokens_today == 100
    assert profile.last_used is not None
    assert profile.is_quota_exceeded() is False

    profile.increment_request(tokens=50)
    assert profile.requests_today == 2
    assert profile.is_quota_exceeded() is True

def test_profile_quota_reset():
    profile = Profile(name="personal", requests_today=10, tokens_today=500)
    profile.reset_quota()
    assert profile.requests_today == 0
    assert profile.tokens_today == 0
    assert profile.quota_reset_at is None

def test_can_handle_pydantic_serialization():
    profile = Profile(name="business", daily_limit=100)
    profile.increment_request(tokens=10)
    data = profile.model_dump()
    assert data["name"] == "business"
    assert data["requests_today"] == 1

    new_profile = Profile(**data)
    assert new_profile.daily_limit == 100
    assert new_profile.requests_today == 1
