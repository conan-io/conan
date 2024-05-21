import pytest
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def build_all():
    """ Build a simple graph to test --build option
        foobar <- bar <- foo
               <--------|
        All packages are built from sources to keep a cache.
    :return: TestClient instance
    """
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_setting("build_type")})
    client.run("export . --name=foo --version=1.0 --user=user --channel=testing")
    client.save({"conanfile.py": GenConanfile().with_require("foo/1.0@user/testing")
                .with_setting("build_type")})
    client.run("export . --name=bar --version=1.0 --user=user --channel=testing")
    client.save({"conanfile.py": GenConanfile().with_require("foo/1.0@user/testing")
                .with_require("bar/1.0@user/testing")
                .with_setting("build_type")})
    client.run("export . --name=foobar --version=1.0 --user=user --channel=testing")
    client.run("install --requires=foobar/1.0@user/testing --build='*'")
    return client


foo_id = "efa83b160a55b033c4ea706ddb980cd708e3ba1b"
bar_id = "7d0bb2b97d4339b0d3ded1418a2593f35b9cf267"
foobar_id = "af8f885f621ba7baac3f5b1d2c18cfdf5ba2550c"


def check_if_build_from_sources(refs_modes, output):
    for ref, mode in refs_modes.items():
        if mode == "Build":
            assert "{}/1.0@user/testing: Forced build from source".format(ref) in output
        else:
            assert "{}/1.0@user/testing: Forced build from source".format(ref) not in output


def test_install_build_single(build_all):
    """ When only --build=<ref> is passed, only <ref> must be built
    """
    build_all.run("install --requires=foobar/1.0@user/testing --build=foo/*")
    build_all.assert_listed_binary({"bar/1.0@user/testing": (bar_id, "Cache"),
                                    "foo/1.0@user/testing": (foo_id, "Build"),
                                    "foobar/1.0@user/testing": (foobar_id, "Cache"),
                                    })
    assert "foo/1.0@user/testing: Forced build from source" in build_all.out
    assert "bar/1.0@user/testing: Forced build from source" not in build_all.out
    assert "foobar/1.0@user/testing: Forced build from source" not in build_all.out
    assert "No package matching" not in build_all.out


def test_install_build_double(build_all):
    """ When both --build=<ref1> and --build=<ref2> are passed, only both should be built
    """
    build_all.run("install --requires=foobar/1.0@user/testing --build=foo/* --build=bar/*")
    build_all.assert_listed_binary({"bar/1.0@user/testing": (bar_id, "Build"),
                                    "foo/1.0@user/testing": (foo_id, "Build"),
                                    "foobar/1.0@user/testing": (foobar_id, "Cache"),
                                    })
    assert "foo/1.0@user/testing: Forced build from source" in build_all.out
    assert "bar/1.0@user/testing: Forced build from source" in build_all.out
    assert "foobar/1.0@user/testing: Forced build from source" not in build_all.out
    assert "No package matching" not in build_all.out


@pytest.mark.parametrize("build_arg,mode", [
                                            ("--build=", "Cache"),
                                            ("--build=*", "Build")])
def test_install_build_only(build_arg, mode, build_all):
    """ When only --build is passed, all packages must be built from sources
        When only --build= is passed, it's considered an error
        When only --build=* is passed, all packages must be built from sources
    """
    build_all.run("install --requires=foobar/1.0@user/testing {}".format(build_arg))

    build_all.assert_listed_binary({"bar/1.0@user/testing": (bar_id, mode),
                                    "foo/1.0@user/testing": (foo_id, mode),
                                    "foobar/1.0@user/testing": (foobar_id, mode),
                                    })

    if "Build" == mode:
        assert "foo/1.0@user/testing: Forced build from source" in build_all.out
        assert "bar/1.0@user/testing: Forced build from source" in build_all.out
        assert "foobar/1.0@user/testing: Forced build from source" in build_all.out
        # FIXME assert "No package matching" not in build_all.out
    else:
        assert "foo/1.0@user/testing: Forced build from source" not in build_all.out
        assert "bar/1.0@user/testing: Forced build from source" not in build_all.out
        assert "foobar/1.0@user/testing: Forced build from source" not in build_all.out
        # FIXME assert "No package matching" in build_all.out


@pytest.mark.parametrize("build_arg,bar,foo,foobar", [("--build=", "Cache", "Build", "Cache"),
                                                      ("--build=*", "Build", "Build", "Build")])
def test_install_build_all_with_single(build_arg, bar, foo, foobar, build_all):
    """ When --build is passed with another package, only the package must be built from sources.
        When --build= is passed with another package, only the package must be built from sources.
        When --build=* is passed with another package, all packages must be built from sources.
    """
    build_all.run("install --requires=foobar/1.0@user/testing --build=foo/* {}".format(build_arg))
    build_all.assert_listed_binary({"bar/1.0@user/testing": (bar_id, bar),
                                    "foo/1.0@user/testing": (foo_id, foo),
                                    "foobar/1.0@user/testing": (foobar_id, foobar),
                                    })
    check_if_build_from_sources({"foo": foo, "bar": bar, "foobar": foobar}, build_all.out)


@pytest.mark.parametrize("build_arg,bar,foo,foobar", [("--build=", "Cache", "Cache", "Cache"),
                                                      ("--build=*", "Build", "Cache", "Build")])
def test_install_build_all_with_single_skip(build_arg, bar, foo, foobar, build_all):
    """ When --build is passed with a skipped package, not all packages must be built from sources.
        When --build= is passed with another package, only the package must be built from sources.
        When --build=* is passed with another package, not all packages must be built from sources.
        The arguments order matter, that's why we need to run twice.
    """
    for argument in ["--build=!foo/* {}".format(build_arg),
                     "{} --build=!foo/*".format(build_arg)]:
        build_all.run("install --requires=foobar/1.0@user/testing {}".format(argument))
        build_all.assert_listed_binary({"bar/1.0@user/testing": (bar_id, bar),
                                        "foo/1.0@user/testing": (foo_id, foo),
                                        "foobar/1.0@user/testing": (foobar_id, foobar),
                                        })
        check_if_build_from_sources({"foo": foo, "bar": bar, "foobar": foobar}, build_all.out)


@pytest.mark.parametrize("build_arg,bar,foo,foobar", [("--build=", "Cache", "Cache", "Cache"),
                                                      ("--build=*", "Cache", "Cache", "Build")])
def test_install_build_all_with_double_skip(build_arg, bar, foo, foobar, build_all):
    """ When --build is passed with a skipped package, not all packages must be built from sources.
        When --build= is passed with another package, only the package must be built from sources.
        When --build=* is passed with another package, not all packages must be built from sources.
        The arguments order matter, that's why we need to run twice.
    """
    for argument in ["--build=!foo/* --build=~bar/* {}".format(build_arg),
                     "{} --build=!foo/* --build=~bar/*".format(build_arg)]:
        build_all.run("install --requires=foobar/1.0@user/testing {}".format(argument))

        build_all.assert_listed_binary({"bar/1.0@user/testing": (bar_id, bar),
                                        "foo/1.0@user/testing": (foo_id, foo),
                                        "foobar/1.0@user/testing": (foobar_id, foobar),
                                        })
