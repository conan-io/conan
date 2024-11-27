from conans.model.conf import Conf


def test_copy_conaninfo_conf():
    conf = Conf()

    conf.define("core:non_interactive", True)
    conf.define("tools.cmake.cmaketoolchain:generator", True)
    conf.define("tools.deployer:symlinks", True)
    conf.define("user.myconf:cmake-test", True)

    pattern = [".*"]
    conf.define("tools.info.package_id:confs", pattern)
    result = conf.copy_conaninfo_conf().dumps()
    assert "tools.info.package_id:confs=%s" % pattern in result
    assert "core:non_interactive" in result
    assert "tools.cmake.cmaketoolchain:generator=True" in result
    assert "tools.deployer:symlinks" in result
    assert "user.myconf:cmake-test" in result

    pattern = ["tools\..*"]
    conf.define("tools.info.package_id:confs", pattern)
    result = conf.copy_conaninfo_conf().dumps()
    assert "tools.info.package_id:confs=%s" % pattern in result
    assert "core:non_interactive" not in result
    assert "tools.cmake.cmaketoolchain:generator=True" in result
    assert "tools.deployer:symlinks" in result
    assert "user.myconf:cmake-test" not in result

    pattern = [".*cmake"]
    conf.define("tools.info.package_id:confs", pattern)
    result = conf.copy_conaninfo_conf().dumps()
    assert "tools.info.package_id:confs=%s" % pattern not in result
    assert "core:non_interactive" not in result
    assert "tools.cmake.cmaketoolchain:generator=True" in result
    assert "tools.deployer:symlinks" not in result
    assert "user.myconf:cmake-test" in result

    pattern = ["(tools.deploy|core)"]
    conf.define("tools.info.package_id:confs", pattern)
    result = conf.copy_conaninfo_conf().dumps()
    assert "tools.info.package_id:confs=%s" % pattern not in result
    assert "core:non_interactive" in result
    assert "tools.cmake.cmaketoolchain:generator=True" not in result
    assert "tools.deployer:symlinks" in result
    assert "user.myconf:cmake-test" not in result

