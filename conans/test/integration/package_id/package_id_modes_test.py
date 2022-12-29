from conans.client.tools import environment_append
from conans.test.utils.tools import GenConanfile, TestClient
from conans.util.files import save


def test_recipe_modes():
    configs = []
    mode = "semver_mode"
    configs.append((mode, "liba/1.1.1@user/testing", "8ecbf93ba63522ffb32573610c80ab4dcb399b52"))
    configs.append((mode, "liba/1.1.2@user/testing", "8ecbf93ba63522ffb32573610c80ab4dcb399b52"))
    configs.append((mode, "liba/1.2.1@other/stable", "8ecbf93ba63522ffb32573610c80ab4dcb399b52"))
    mode = "patch_mode"
    configs.append((mode, "liba/1.1.1@user/testing", "bd664570d5174c601d5d417bc19257c4dba48f2e"))
    configs.append((mode, "liba/1.1.2@user/testing", "fb1f766173191d44b67156c6b9ac667422e99286"))
    configs.append((mode, "liba/1.1.1@other/stable", "bd664570d5174c601d5d417bc19257c4dba48f2e"))
    mode = "full_recipe_mode"
    configs.append((mode, "liba/1.1.1@user/testing", "9cbe703e1dee73a2a6807f71d8551c5f1e1b08fd"))
    configs.append((mode, "liba/1.1.2@user/testing", "42a9ff9024adabbd54849331cf01be7d95139948"))
    configs.append((mode, "liba/1.1.1@user/stable", "b41d6c026473cffed4abded4b0eaa453497be1d2"))

    client = TestClient()
    # TODO: These 2 little simplifications can reduce test time by 30-40%, to do in test framework
    save(client.cache.settings_path, "")
    save(client.cache.default_profile_path, "")

    def _assert_recipe_mode(liba_ref, package_id_arg):
        client.save({"liba/conanfile.py": GenConanfile("liba"),
                     "libb/conanfile.py": GenConanfile("libb", "0.1").with_require(liba_ref),
                     "app/conanfile.py": GenConanfile("app", "0.1").with_require("libb/0.1")})
        client.run("create liba {}".format(liba_ref))
        client.run("create libb")
        client.run("create app")

        assert "{}:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache".format(liba_ref) in client.out
        assert "libb/0.1:{} - Cache".format(package_id_arg) in client.out

    for package_id_mode, ref, package_id in configs:
        client.run("config set general.default_package_id_mode={}".format(package_id_mode))
        _assert_recipe_mode(ref, package_id)

    for package_id_mode, ref, package_id in configs:
        with environment_append({"CONAN_DEFAULT_PACKAGE_ID_MODE": package_id_mode}):
            _assert_recipe_mode(ref, package_id)


def test_package_revision_mode():
    client = TestClient()
    # TODO: These 2 little simplifications can reduce test time by 30-40%, to do in test framework
    save(client.cache.settings_path, "")
    save(client.cache.default_profile_path, "")

    client.run("config set general.default_package_id_mode=package_revision_mode")

    client.save({"liba/conanfile.py": GenConanfile("liba", "0.1.1"),
                 "libb/conanfile.py": GenConanfile("libb", "0.1").with_require("liba/0.1.1"),
                 "app/conanfile.py": GenConanfile("app", "0.1").with_require("libb/0.1")})

    client.run("create liba")
    client.run("create libb")
    client.run("create app")

    assert "liba/0.1.1:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache" in client.out
    assert "libb/0.1:f2431acdad185a6626b90ee1dffb06445f887cbb - Cache" in client.out
