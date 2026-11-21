from scentiq_api.services.ttl_cache import TtlLruCache


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_returns_a_stored_value_until_it_expires() -> None:
    clock = Clock()
    cache: TtlLruCache[int] = TtlLruCache(4, 10, clock=clock)
    cache.put("a", 1)
    clock.now = 9.9
    assert cache.get("a") == 1
    clock.now = 10.0
    assert cache.get("a") is None
    assert len(cache) == 0


def test_evicts_the_least_recently_used_entry() -> None:
    cache: TtlLruCache[int] = TtlLruCache(2, 60)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_a_different_version_in_the_key_is_a_miss() -> None:
    cache: TtlLruCache[str] = TtlLruCache(4, 60)
    cache.put(("user", 1), "old")
    assert cache.get(("user", 2)) is None
    assert cache.get(("user", 1)) == "old"
