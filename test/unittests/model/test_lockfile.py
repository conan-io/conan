import json

import pytest

from conan.errors import ConanException
from conan.internal.model.lockfile import Lockfile, LOCKFILE_VERSION


def test_load_none_path():
    with pytest.raises(ConanException, match="Missing lockfile in"):
        Lockfile.load(None)


def test_load_empty_path():
    with pytest.raises(ConanException, match="Missing lockfile in"):
        Lockfile.load("")


def test_load_nonexistent_file():
    with pytest.raises(ConanException, match="Missing lockfile in"):
        Lockfile.load("/nonexistent/path/conan.lock")


def test_load_invalid_json(tmp_path):
    lockfile = tmp_path / "conan.lock"
    lockfile.write_text("this is not json")
    with pytest.raises(ConanException, match="Error parsing lockfile"):
        Lockfile.load(str(lockfile))


def test_load_incompatible_version(tmp_path):
    lockfile = tmp_path / "conan.lock"
    lockfile.write_text(json.dumps({"version": "0.1"}))
    with pytest.raises(ConanException, match="Error parsing lockfile"):
        Lockfile.load(str(lockfile))


def test_loads_incompatible_version():
    content = json.dumps({"version": "0.1"})
    with pytest.raises(ConanException, match="incompatible"):
        Lockfile.loads(content)


def test_load_malformed_reference(tmp_path):
    lockfile = tmp_path / "conan.lock"
    lockfile.write_text(json.dumps({"version": LOCKFILE_VERSION,
                                    "requires": ["not_a_valid_ref"]}))
    with pytest.raises(ConanException, match="Error parsing lockfile"):
        Lockfile.load(str(lockfile))


def test_load_valid(tmp_path):
    lockfile = tmp_path / "conan.lock"
    lockfile.write_text(json.dumps({"version": LOCKFILE_VERSION,
                                    "requires": ["pkg/1.0#rev1"]}))
    lf = Lockfile.load(str(lockfile))
    refs = list(lf._requires.refs())
    assert len(refs) == 1
    assert refs[0].name == "pkg"
