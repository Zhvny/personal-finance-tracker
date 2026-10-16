from packages.core.infrastructure.config import Config


def test_marker_chain_root_detection(tmp_path):
    """
    Vector 1.1: Marker-Chain Root Detection
    Test that Config.get_root points to the absolute canonical root even when called from deep paths.
    """
    print("Running Vector 1.1 Audit: Marker-Chain Root Detection...")

    # 1. Create a deep structure under the temp directory
    deep_dir = tmp_path / "node_modules" / "a" / "b" / "c"
    deep_dir.mkdir(parents=True, exist_ok=True)

    # 2. Place a marker file at tmp_path
    marker_file = tmp_path / "package.json"
    marker_file.write_text("{}")

    # 3. Detect root starting from the deep directory
    detected_root = Config.get_root(deep_dir / "file.py")

    assert detected_root == tmp_path, f"Expected root to be {tmp_path}, got {detected_root}"

    # 4. Try with another marker
    marker_file.unlink()
    setup_marker = tmp_path / ".setup_done"
    setup_marker.write_text("")

    detected_root2 = Config.get_root(deep_dir / "file.py")
    assert detected_root2 == tmp_path, f"Expected root to be {tmp_path} with .setup_done, got {detected_root2}"

    print("Vector 1.1 DoD: SUCCESS. get_root is absolute and canonical.")

if __name__ == "__main__":
    try:
        test_marker_chain_root_detection()
    except Exception as e:
        print(f"Vector 1.1 FAILURE: {e}")
        exit(1)
