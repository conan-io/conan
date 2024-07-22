import pytest

from conans.client.graph.build_mode import BuildMode
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conan.test.utils.mocks import ConanFileMock, RedirectedTestOutput
from conan.test.utils.tools import redirect_output


@pytest.fixture
def conanfile():
    return ConanFileMock(None)


def test_skip_package(conanfile):
    build_mode = BuildMode(["!zlib/*", "other*"])
    assert not build_mode.forced(conanfile, RecipeReference.loads("zlib/1.2.11#23423423"))
    assert build_mode.forced(conanfile, RecipeReference.loads("other/1.2"))

    build_mode = BuildMode(["!zlib/*", "*"])
    assert not build_mode.forced(conanfile, RecipeReference.loads("zlib/1.2.11#23423423"))
    assert build_mode.forced(conanfile, RecipeReference.loads("other/1.2"))

    build_mode = BuildMode(["!zlib/*"])
    assert not build_mode.forced(conanfile, RecipeReference.loads("zlib/1.2.11#23423423"))
    assert not build_mode.forced(conanfile, RecipeReference.loads("other/1.2"))


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
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("hello/0.1@user/testing")
        build_mode = BuildMode(["hello/*"])
        assert build_mode.forced(conanfile, reference) is True


def test_no_user_channel(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("hello/0.1@")
        build_mode = BuildMode(["hello/0.1@"])
        assert build_mode.forced(conanfile, reference) is True


def test_revision_included(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("hello/0.1@user/channel#rrev1")
        build_mode = BuildMode(["hello/0.1@user/channel#rrev1"])
        assert build_mode.forced(conanfile, reference) is True


def test_no_user_channel_revision_included(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("hello/0.1@#rrev1")
        build_mode = BuildMode(["hello/0.1@#rrev1"])
        assert build_mode.forced(conanfile, reference) is True


def test_non_matching_build_force(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("Bar/0.1@user/testing")
        build_mode = BuildMode(["hello"])
        assert build_mode.forced(conanfile, reference) is False


def test_full_reference_build_force(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("bar/0.1@user/testing")
        build_mode = BuildMode(["bar/0.1@user/testing"])
        assert build_mode.forced(conanfile, reference) is True


def test_non_matching_full_reference_build_force(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("bar/0.1@user/stable")
        build_mode = BuildMode(["bar/0.1@user/testing"])
        assert build_mode.forced(conanfile, reference) is False


def test_multiple_builds(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("bar/0.1@user/stable")
        build_mode = BuildMode(["bar/*", "Foo/*"])
        assert build_mode.forced(conanfile, reference) is True


def test_allowed(conanfile):
    build_mode = BuildMode(["missing"])
    assert build_mode.allowed(conanfile) is True

    build_mode = BuildMode(None)
    assert build_mode.allowed(conanfile) is False


def test_casing(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        reference = RecipeReference.loads("boost/1.69.0@user/stable")

        build_mode = BuildMode(["boost*"])
        assert build_mode.forced(conanfile, reference) is True
        build_mode = BuildMode(["bo*"])
        assert build_mode.forced(conanfile, reference) is True

        output.clear()
        build_mode = BuildMode(["Boost*"])
        assert build_mode.forced(conanfile, reference) is False
        build_mode = BuildMode(["Bo*"])
        assert build_mode.forced(conanfile, reference) is False


def test_pattern_matching(conanfile):
    output = RedirectedTestOutput()
    with redirect_output(output):
        build_mode = BuildMode(["boost*"])
        reference = RecipeReference.loads("boost/1.69.0@user/stable")
        assert (build_mode.forced(conanfile, reference)) is True
        reference = RecipeReference.loads("boost_addons/1.0.0@user/stable")
        assert (build_mode.forced(conanfile, reference)) is True
        reference = RecipeReference.loads("myboost/1.0@user/stable")
        assert (build_mode.forced(conanfile, reference)) is False
        reference = RecipeReference.loads("foo/boost@user/stable")
        assert (build_mode.forced(conanfile, reference)) is False
        reference = RecipeReference.loads("foo/1.0@boost/stable")
        assert (build_mode.forced(conanfile, reference)) is False
        reference = RecipeReference.loads("foo/1.0@user/boost")
        assert build_mode.forced(conanfile, reference) is False

        build_mode = BuildMode(["foo/*@user/stable"])
        reference = RecipeReference.loads("foo/1.0.0@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("foo/1.0@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("foo/1.0.0-abcdefg@user/stable")
        assert build_mode.forced(conanfile, reference) is True

        build_mode = BuildMode(["*@user/stable"])
        reference = RecipeReference.loads("foo/1.0.0@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("bar/1.0@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("foo/1.0.0-abcdefg@user/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("foo/1.0.0@NewUser/stable")
        assert build_mode.forced(conanfile, reference) is False

        build_mode = BuildMode(["*tool*"])
        reference = RecipeReference.loads("tool/0.1@lasote/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("pythontool/0.1@lasote/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("sometool/1.2@user/channel")
        assert build_mode.forced(conanfile, reference) is True

        build_mode = BuildMode(["tool/*"])
        reference = RecipeReference.loads("tool/0.1@lasote/stable")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("tool/1.1@user/testing")
        assert build_mode.forced(conanfile, reference) is True
        reference = RecipeReference.loads("pythontool/0.1@lasote/stable")
        assert build_mode.forced(conanfile, reference) is False
