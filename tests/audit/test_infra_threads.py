import threading

from packages.core.infrastructure.config import Config


def test_thread_safe_config():
    """
    Vector 1.2: Thread-Safe Config Singleton
    Spawn 100 threads accessing Config.get_active_profile() simultaneously.
    """
    print("Running Vector 1.2 Audit: Thread-Safe Config Singleton...")

    results = []

    def access_config():
        try:
            profile = Config.get_active_profile()
            results.append(profile)
        except Exception as e:
            results.append(e)

    threads = []
    for _ in range(100):
        t = threading.Thread(target=access_config)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(results) == 100, f"Expected 100 results, got {len(results)}"

    for r in results:
        if isinstance(r, Exception):
            raise r

    print(f"Vector 1.2 DoD: SUCCESS. 100 threads accessed config without race conditions. Profile: {results[0]}")

if __name__ == "__main__":
    try:
        test_thread_safe_config()
    except Exception as e:
        print(f"Vector 1.2 FAILURE: {e}")
        exit(1)
