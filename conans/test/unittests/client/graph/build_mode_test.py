from unittest import mock

import pytest

from conans.client.graph.build_mode import BuildMode
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.utils.mocks import MockConanfile, SysStdStream


@pytest.fixture
def conanfile():
    return MockConanfile(None)


def test_valid_params():
    build_mode = BuildMode(["missing"])
    assert build_mode.missing is True
    assert build_mode.never is False
    assert build_mode.cascade is False

    build_mode = BuildMode(["never"])
    assert build_mode.missing is False
    assert build_mode.never is True
    assert build_mode.cascade is False

    build_mode = BuildMode(["cascade"])
    assert build_mode.missing is False
    assert build_mode.never is False
    assert build_mode.cascade is True


def test_invalid_configuration():
    for mode in ["missing", "cascade"]:
        with pytest.raises(ConanException, match=r"--build=never not compatible "
                                                 r"with other options"):
            BuildMode([mode, "never"])


def test_common_build_force(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Hello/0.1@user/testing")
        build_mode = BuildMode(["Hello"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode.report_matches()
        assert output.contents == ""


def test_no_user_channel(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Hello/0.1@")
        build_mode = BuildMode(["Hello/0.1@"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode.report_matches()
        assert output.contents == ""


def test_revision_included(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Hello/0.1@user/channel#rrev1")
        build_mode = BuildMode(["Hello/0.1@user/channel#rrev1"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode.report_matches()
        assert output.contents == ""


def test_no_user_channel_revision_included(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Hello/0.1@#rrev1")
        build_mode = BuildMode(["Hello/0.1@#rrev1"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode.report_matches()
        assert output.contents == ""


def test_non_matching_build_force(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Bar/0.1@user/testing")
        build_mode = BuildMode(["Hello"])
        assert build_mode.forced(conanfile, reference) is False
        build_mode.report_matches()
        assert "ERROR: No package matching 'Hello' pattern" in output.contents


def test_full_reference_build_force(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Bar/0.1@user/testing")
        build_mode = BuildMode(["Bar/0.1@user/testing"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode.report_matches()
        assert output.contents == ""


def test_non_matching_full_reference_build_force(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Bar/0.1@user/stable")
        build_mode = BuildMode(["Bar/0.1@user/testing"])
        assert build_mode.forced(conanfile, reference) is False
        build_mode.report_matches()
        assert "No package matching 'Bar/0.1@user/testing' pattern" in output.contents


def test_multiple_builds(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Bar/0.1@user/stable")
        build_mode = BuildMode(["Bar", "Foo"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode.report_matches()
        assert "ERROR: No package matching" in output.contents


def test_allowed(conanfile):
    build_mode = BuildMode(["missing"])
    assert build_mode.allowed(conanfile) is True

    build_mode = BuildMode([])
    assert build_mode.allowed(conanfile) is False


def test_casing(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        reference = ConanFileReference.loads("Boost/1.69.0@user/stable")

        build_mode = BuildMode(["Boost"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode = BuildMode(["Bo*"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode.report_matches()
        assert "" == output.contents

        build_mode = BuildMode(["boost"])
        assert build_mode.forced(conanfile, reference) is False
        build_mode = BuildMode(["bo*"])
        assert build_mode.forced(conanfile, reference) is False
        build_mode.report_matches()
        assert "ERROR: No package matching" in output.contents


def test_pattern_matching(conanfile):
    output = SysStdStream()
    with mock.patch("sys.stderr", output):
        build_mode = BuildMode(["Boost*"])
        reference = ConanFileReference.loads("Boost/1.69.0@user/stable")
        assert (build_mode.forced(conanfile, reference)) is True
        reference = ConanFileReference.loads("Boost_Addons/1.0.0@user/stable")
        assert (build_mode.forced(conanfile, reference)) is True
        reference = ConanFileReference.loads("MyBoost/1.0@user/stable")
        assert (build_mode.forced(conanfile, reference)) is False
        reference = ConanFileReference.loads("foo/Boost@user/stable")
        assert (build_mode.forced(conanfile, reference)) is False
        reference = ConanFileReference.loads("foo/1.0@Boost/stable")
        assert (build_mode.forced(conanfile, reference)) is False
        reference = ConanFileReference.loads("foo/1.0@user/Boost")
        assert build_mode.forced(conanfile, reference) is False

        build_mode = BuildMode(["foo/*@user/stable"])
        reference = ConanFileReference.loads("foo/1.0.0@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("foo/1.0@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("foo/1.0.0-abcdefg@user/stable")
        assert build_mode.forced(conanfile, reference) is True

        build_mode = BuildMode(["*@user/stable"])
        reference = ConanFileReference.loads("foo/1.0.0@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("bar/1.0@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("foo/1.0.0-abcdefg@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("foo/1.0.0@NewUser/stable")
        assert build_mode.forced(conanfile, reference) is False

        build_mode = BuildMode(["*Tool"])
        reference = ConanFileReference.loads("Tool/0.1@lasote/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("PythonTool/0.1@lasote/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("SomeTool/1.2@user/channel")
        assert build_mode.forced(conanfile, reference) is True

        build_mode = BuildMode(["Tool/*"])
        reference = ConanFileReference.loads("Tool/0.1@lasote/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("Tool/1.1@user/testing")
        assert build_mode.forced(conanfile, reference) is True
        reference = ConanFileReference.loads("PythonTool/0.1@lasote/stable")
        assert build_mode.forced(conanfile, reference) is False

        build_mode.report_matches()
        assert output.contents == ""
