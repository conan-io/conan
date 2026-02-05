import json
import os
import textwrap

import pytest
import yaml

from conan.api.model import RecipeReference
from conan.internal.cache.home_paths import HomePaths
from conan.internal.util.files import load
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def servers():
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class Conf(ConanFile):
            package_type = "configuration"
            def package(self):
                copy(self, "*.conf", src=self.build_folder, dst=self.package_folder)
        """)
    c = TestClient(default_server_user=True, light=True)
    c.save({"conanfile.py": conanfile})
    for pkg in ("myconf_a", "myconf_b", "myconf_c"):
        for version in ("0.1", "0.2"):
            c.save({"global.conf": f"user.myteam:myconf=my_{pkg}/{version}_value"})
            c.run(f"export-pkg . --name={pkg} --version={version}")
    c.run("upload * -r=default -c")
    c.run("remove * -c")
    return c.servers


def _check_conf(c, pkg):
    c.run("config show *")
    assert f"user.myteam:myconf: my_{pkg}_value" in c.out


def _check_conf_file(c, refs):
    content = json.loads(c.load_home("config_version.json"))["config_version"]
    for a, b in zip(refs, content):
        assert a in b


class TestConfigInstallPkg:

    def test_install_pkg(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        assert "Installing new or updating configuration packages" in c.out
        _check_conf(c, "myconf_a/0.1")
        _check_conf_file(c, ["myconf_a/0.1"])
        cache_files = os.listdir(c.cache_folder)
        assert "conaninfo.txt" not in cache_files
        assert "conanmanifest.txt" not in cache_files

        # skip reinstall
        c.run("config install-pkg myconf_a/0.1")
        assert ("The requested configurations are identical to the already installed ones, "
                "skipping re-installation") in c.out
        _check_conf(c, "myconf_a/0.1")
        _check_conf_file(c, ["myconf_a/0.1"])

        # forced reinstall
        c.save_home({"global.conf": ""})
        c.run("config install-pkg myconf_a/0.1 --force")
        assert "forcing re-installation because --force" in c.out
        _check_conf(c, "myconf_a/0.1")
        _check_conf_file(c, ["myconf_a/0.1"])

    def test_with_url(self, servers):
        c = TestClient(servers=servers, light=True)
        url = servers["default"].fake_url
        c.run("remote remove default")
        c.run(f"config install-pkg myconf_a/0.1 --url={url}")
        assert "Installing new or updating configuration packages" in c.out
        _check_conf(c, "myconf_a/0.1")
        _check_conf_file(c, ["myconf_a/0.1"])

    def test_update(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        c.run("config install-pkg myconf_a/0.2")
        assert "Installing new or updating configuration packages" in c.out
        _check_conf(c, "myconf_a/0.2")
        _check_conf_file(c, ["myconf_a/0.2"])

    def test_addition(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        c.run("config install-pkg myconf_b/0.1")
        assert "Installing new or updating configuration packages" in c.out
        _check_conf(c, "myconf_b/0.1")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

    def test_update_first(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        c.run("config install-pkg myconf_b/0.1")

        # update of the first fail
        c.run("config install-pkg myconf_a/[*]", assert_error=True)
        assert "ERROR: Installing these configuration packages will break" in c.out
        assert "use 'conan config install-pkg --force' to force" in c.out
        assert "Use 'conan config clean' first to fully reset your configuration" in c.out
        _check_conf(c, "myconf_b/0.1")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

        # Now force the first
        c.run("config install-pkg myconf_a/[*] --force")
        assert "Forcing the installation because --force was defined" in c.out
        _check_conf(c, "myconf_a/0.2")
        _check_conf_file(c, ["myconf_b/0.1", "myconf_a/0.2"])

    def test_update_second(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1")
        c.run("config install-pkg myconf_b/0.1")

        # update of the second works without problem
        c.run("config install-pkg myconf_b/[*]")
        assert "Installing new or updating configuration packages" in c.out
        _check_conf(c, "myconf_b/0.2")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.2"])

    def test_error_cant_use_as_dependency(self):
        c = TestClient(light=True)
        conanfile = GenConanfile("myconf", "0.1").with_package_type("configuration")
        c.save({"myconf/conanfile.py": conanfile,
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("myconf/0.1")})
        c.run("create myconf")
        c.run("install pkg", assert_error=True)
        assert "ERROR: Configuration package myconf/0.1 cannot be used as requirement, " \
               "but pkg/0.1 is requiring it" in c.out

    def test_error_cant_use_without_type(self):
        c = TestClient(light=True)
        c.save({"myconf/conanfile.py": GenConanfile("myconf", "0.1")})
        c.run("create myconf")
        c.run("config install-pkg myconf/[*]", assert_error=True)
        assert 'ERROR: myconf/0.1 is not of package_type="configuration"' in c.out

    def test_create_also(self):
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.files import copy
           class Conf(ConanFile):
               name = "myconf"
               version = "0.1"
               package_type = "configuration"
               exports_sources = "*.conf"
               def package(self):
                   copy(self, "*.conf", src=self.build_folder, dst=self.package_folder)
               """)

        c = TestClient(default_server_user=True, light=True)
        c.save({"conanfile.py": conanfile,
                "global.conf": "user.myteam:myconf=my_myconf/0.1_value"})
        c.run("create .")
        c.run("upload * -r=default -c")
        c.run("remove * -c")

        c.run("config install-pkg myconf/[*]")
        _check_conf(c, "myconf/0.1")
        _check_conf_file(c, ["myconf/0.1"])

    def test_lockfile(self, servers):
        """ it should be able to install the config older version using a lockfile
        """
        c = TestClient(servers=servers, light=True)
        c.run("config install-pkg myconf_a/0.1 --lockfile-out=config.lock")
        c.run("config install-pkg myconf_a/[*] --lockfile=config.lock")
        assert ("The requested configurations are identical to the already installed ones, "
                "skipping re-installation") in c.out
        _check_conf(c, "myconf_a/0.1")
        _check_conf_file(c, ["myconf_a/0.1"])

        # Without the lockfile, it is free to update
        c.run("config install-pkg myconf_a/[*] --lockfile-out=config.lock")
        assert "Installing new or updating configuration packages"
        _check_conf(c, "myconf_a/0.2")
        _check_conf_file(c, ["myconf_a/0.2"])
        result = json.loads(c.load("config.lock"))
        assert "myconf_a/0.2" in result["config_requires"][0]

    def test_package_id_effect(self):
        # full integration, as "test_config_package_id.py" tests from hardcoded cache json files
        c = TestClient(light=True)
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import copy
            class Conf(ConanFile):
                name = "myconf"
                version = "0.1"
                package_type = "configuration"
                def package(self):
                    copy(self, "*.conf", src=self.build_folder, dst=self.package_folder)
            """)
        c.save({"conanfile.py": conanfile,
                "global.conf": f"core.package_id:config_mode=minor_mode"})
        c.run(f"export-pkg .")

        c.run("config install-pkg myconf/0.1")

        c.save({"conanfile.py": GenConanfile("pkg", "0.1")}, clean_first=True)
        c.run("create .")
        assert f"pkg/0.1: config_version: myconf/0.1.Z" in c.out
        c.run("list pkg/0.1:* --format=json")
        info = json.loads(c.stdout)
        rrev = info["Local Cache"]["pkg/0.1"]["revisions"]["485dad6cb11e2fa99d9afbe44a57a164"]
        pkg = rrev["packages"]["b683aa607d81f4a3b6f0c87c8191387133f2ff4a"]
        assert pkg["info"] == {"config_version": ["myconf/0.1.Z"]}


class TestConfigInstallPkgFromFile:
    def test_install_from_file(self, servers):
        c = TestClient(servers=servers, light=True)
        # To make explicit the format of the conanconfig file
        conanconfig = textwrap.dedent("""\
            packages:
                - myconf_a/0.1
                - myconf_b/0.1
            """)
        c.save({"conanconfig.yml": conanconfig})
        # Admits the default location .
        c.run("config install-pkg")
        _check_conf(c, "myconf_b/0.1")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

        # install same file again:
        c.run("config install-pkg .")
        assert ("The requested configurations are identical to the already installed ones, "
                "skipping re-installation") in c.out
        _check_conf(c, "myconf_b/0.1")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

        # Forced re-install
        c.save_home({"global.conf": ""})
        c.run("config install-pkg . --force")
        assert "forcing re-installation because --force" in c.out
        _check_conf(c, "myconf_b/0.1")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

    def test_install_from_file_with_url(self, servers):
        c = TestClient(servers=servers, light=True)
        c.run("remote remove default")
        server_url = servers["default"].fake_url
        conanconfig = yaml.dump({"packages": ["myconf_a/0.1"], "urls": [server_url]})
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")
        _check_conf(c, "myconf_a/0.1")
        _check_conf_file(c, ["myconf_a/0.1"])

    def test_update_with_file(self, servers):
        c = TestClient(servers=servers, light=True)
        conanconfig = yaml.dump({"packages": ["myconf_a/0.1", "myconf_b/0.1"]})
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")

        # Now installing "updates" without disrupting the order
        c.run("config install-pkg myconf_c/0.1")
        assert "Installing new or updating configuration packages"
        _check_conf(c, "myconf_c/0.1")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1", "myconf_c/0.1"])

        # Now installing "updates" without disrupting the order
        conanconfig = textwrap.dedent("""\
            packages:
                - myconf_a/0.1
                - myconf_b/0.1
                - myconf_c/[*]
            """)
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")
        assert "Installing new or updating configuration packages" in c.out
        _check_conf(c, "myconf_c/0.2")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1", "myconf_c/0.2"])

        # This is also an update of the existing ones, keeping the order
        conanconfig = textwrap.dedent("""\
            packages:
                - myconf_a/[*]
                - myconf_b/0.1
                - myconf_c/[*]
            """)
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")
        assert "Installing new or updating configuration packages" in c.out
        _check_conf(c, "myconf_c/0.2")
        _check_conf_file(c, ["myconf_a/0.2", "myconf_b/0.1", "myconf_c/0.2"])

    def test_failed_update_force(self, servers):
        c = TestClient(servers=servers, light=True)
        conanconfig = yaml.dump({"packages": ["myconf_a/0.1", "myconf_b/0.1"]})
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")

        # Now installing "updates" without disrupting the order
        conanconfig = textwrap.dedent("""\
            packages:
                - myconf_a/0.2
            """)
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .", assert_error=True)
        assert "use 'conan config install-pkg --force' to force" in c.out
        assert "Use 'conan config clean' first to fully reset" in c.out
        _check_conf(c, "myconf_b/0.1")
        _check_conf_file(c, ["myconf_a/0.1", "myconf_b/0.1"])

        c.run("config install-pkg . --force")
        assert "Forcing the installation because --force was defined" in c.out
        _check_conf(c, "myconf_a/0.2")
        _check_conf_file(c, ["myconf_b/0.1", "myconf_a/0.2"])

    def test_install_from_file_with_lockfile(self, servers):
        # it should stay in version 0.1
        c = TestClient(servers=servers)
        c.run("config install-pkg myconf_a/0.1 --lockfile-out=conan.lock")
        conanconfig = yaml.dump({"packages": ["myconf_a/[>=0.1 <1.0]"]})
        c.save({"conanconfig.yml": conanconfig})
        c.run("config install-pkg .")
        path = HomePaths(c.cache_folder).config_version_path
        # First are the newest installed
        configs = json.loads(load(path))["config_version"]
        configs = [str(RecipeReference.loads(r)) for r in configs]
        assert configs == ["myconf_a/0.1"]


class TestConfigInstallPkgSettings:
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Conf(ConanFile):
            name = "myconf"
            version = "0.1"
            settings = "os"
            package_type = "configuration"
            def package(self):
                f = "win" if self.settings.os == "Windows" else "nix"
                copy(self, "*.conf", src=os.path.join(self.build_folder, f), dst=self.package_folder)
            """)

    @pytest.fixture()
    def client(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": self.conanfile,
                "win/global.conf": "user.myteam:myconf=mywinvalue",
                "nix/global.conf": "user.myteam:myconf=mynixvalue",
                })
        c.run("export-pkg . -s os=Windows")
        c.run("export-pkg . -s os=Linux")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        return c

    @pytest.mark.parametrize("default_profile", [False, True])
    def test_config_install_from_pkg(self, client, default_profile):
        # Now install it
        c = client
        if not default_profile:
            os.remove(os.path.join(c.cache_folder, "profiles", "default"))
        c.run("config install-pkg myconf/[*] -s os=Windows")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mywinvalue" in c.out

        c.run("config install-pkg myconf/[*] -s os=Linux --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mynixvalue" in c.out

    def test_error_no_settings_defined(self, client):
        c = client
        os.remove(os.path.join(c.cache_folder, "profiles", "default"))
        c.run("config install-pkg myconf/[*]", assert_error=True)
        assert "There are invalid packages:" in c.out
        assert "myconf/0.1: Invalid: 'settings.os' value not defined" in c.out

    def test_config_install_from_pkg_profile(self, client):
        # Now install it
        c = client
        c.save({"win.profile": "[settings]\nos=Windows",
                "nix.profile": "[settings]\nos=Linux"})
        c.run("config install-pkg myconf/[*] -pr=win.profile")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mywinvalue" in c.out

        c.run("config install-pkg myconf/[*] -pr=nix.profile --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mynixvalue" in c.out

    def test_config_install_from_pkg_profile_default(self, client):
        # Now install it
        c = client
        c.save_home({"profiles/default": "[settings]\nos=Windows"})
        c.run("config install-pkg myconf/[*]")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mywinvalue" in c.out

        c.save_home({"profiles/default": "[settings]\nos=Linux"})
        c.run("config install-pkg myconf/[*] --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: mynixvalue" in c.out


class TestConfigInstallPkgOptions:
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy
        class Conf(ConanFile):
            name = "myconf"
            version = "0.1"
            options = {"project": ["project1", "project2"]}
            default_options = {"project": "project1"}
            package_type = "configuration"
            def package(self):
                copy(self, "*.conf", src=os.path.join(self.build_folder, str(self.options.project)),
                     dst=self.package_folder)
            """)

    @pytest.fixture()
    def client(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": self.conanfile,
                "project1/global.conf": "user.myteam:myconf=my1value",
                "project2/global.conf": "user.myteam:myconf=my2value",
                })
        c.run("export-pkg .")
        c.run("export-pkg . -o project=project2")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        return c

    @pytest.mark.parametrize("default_profile", [False, True])
    def test_config_install_from_pkg(self, client, default_profile):
        # Now install it
        c = client
        if not default_profile:
            os.remove(os.path.join(c.cache_folder, "profiles", "default"))
        c.run("config install-pkg myconf/[*] -o &:project=project1")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my1value" in c.out

        c.run("config install-pkg myconf/[*] -o &:project=project2 --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my2value" in c.out

    def test_no_option_defined(self, client):
        c = client
        os.remove(os.path.join(c.cache_folder, "profiles", "default"))
        c.run("config install-pkg myconf/[*]")
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my1value" in c.out

    def test_config_install_from_pkg_profile(self, client):
        # Now install it
        c = client
        c.save({"win.profile": "[options]\n&:project=project1",
                "nix.profile": "[options]\n&:project=project2"})
        c.run("config install-pkg myconf/[*] -pr=win.profile")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my1value" in c.out

        c.run("config install-pkg myconf/[*] -pr=nix.profile --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my2value" in c.out

    def test_config_install_from_pkg_profile_default(self, client):
        # Now install it
        c = client
        c.save_home({"profiles/default": "[options]\n&:project=project1"})
        c.run("config install-pkg myconf/[*]")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my1value" in c.out

        c.save_home({"profiles/default": "[options]\n&:project=project2"})
        c.run("config install-pkg myconf/[*] --force")
        assert "myconf/0.1: Downloaded package revision" in c.out
        assert "Copying file global.conf" in c.out
        c.run("config show *")
        assert "user.myteam:myconf: my2value" in c.out
