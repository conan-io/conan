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


def _merge(*requires_lists, kind="requires"):
    result = Lockfile()
    for requires in requires_lists:
        result.merge(Lockfile.deserialize({"version": LOCKFILE_VERSION, kind: requires}))
    return result.serialize()[kind]


@pytest.mark.parametrize("kind", ["requires", "build_requires", "python_requires",
                                  "config_requires"])
@pytest.mark.parametrize("revision_first", [True, False])
def test_merge_revision_and_no_revision(kind, revision_first):
    """ The same name/version, one with revision and the other without it. The revision is more
    specific, so it always prevails (with its timestamp), independently of the order
    https://github.com/conan-io/conan/issues/20551
    """
    with_rev = ["zlib/1.3.1#rev1%123.5"]
    no_rev = ["zlib/1.3.1"]
    lists = [with_rev, no_rev] if revision_first else [no_rev, with_rev]
    assert _merge(*lists, kind=kind) == ["zlib/1.3.1#rev1%123.5"]


@pytest.mark.parametrize("rev1_first", [True, False])
def test_merge_two_revisions(rev1_first):
    """ Different revisions of the same name/version coexist, newest first, in any order """
    rev1 = ["zlib/1.3.1#rev1%1.0"]
    rev2 = ["zlib/1.3.1#rev2%2.0"]
    lists = [rev1, rev2] if rev1_first else [rev2, rev1]
    assert _merge(*lists) == ["zlib/1.3.1#rev2%2.0", "zlib/1.3.1#rev1%1.0"]


@pytest.mark.parametrize("revision_first", [True, False])
def test_merge_revision_and_no_revision_package_ids(revision_first):
    """ Merging a revisionless entry with a revisioned one keeps the revision and the package ids,
    independently of the order
    """
    with_rev = [["zlib/1.3.1#rev1", {"pid1": "prev1"}]]
    no_rev = ["zlib/1.3.1"]
    lists = [with_rev, no_rev] if revision_first else [no_rev, with_rev]
    assert _merge(*lists) == [("zlib/1.3.1#rev1", {"pid1": "prev1"})]
