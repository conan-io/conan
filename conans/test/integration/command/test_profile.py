import os 

from conans.test.utils.tools import TestClient


def test_profile_path():
    c = TestClient()
    c.run("profile path default")
    assert "default" in c.out


def test_ignore_paths_when_listing_profiles():
    c = TestClient()
    ignore_paths = ['.DS_Store']

    # Create files, dirs if necessary, at the ignore paths
    for path in ignore_paths:
        rel_file_path = os.path.join(c.cache.profiles_path, path)

        base_dir = os.path.join(c.cache.profiles_path, os.path.dirname(path))
        if base_dir:
            os.makedirs(base_dir, exist_ok=True)
            open(os.path.join(base_dir, os.path.basename(path)), 'w').close()
        else:
            open(rel_file_path, 'w').close()

    c.run("profile list")

    for path in ignore_paths:
        rel_file_path = os.path.relpath(os.path.join(c.cache.profiles_path, path))
        assert rel_file_path not in c.out