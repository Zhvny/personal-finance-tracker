import threading

from packages.core.infrastructure.config import Config


def test_config_singleton_identity():
    c1 = Config()
    c2 = Config()
    assert c1 is c2

def test_config_thread_safety():
    instances = []
    def get_instance():
        instances.append(Config())

    threads = [threading.Thread(target=get_instance) for _ in range(100)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All instances should be the same
    first_instance = instances[0]
    for instance in instances:
        assert instance is first_instance
