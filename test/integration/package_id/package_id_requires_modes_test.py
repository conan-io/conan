import textwrap

import pytest

from conan.test.utils.tools import TestClient, GenConanfile


class TestPackageIDRequirementsModes:

    @pytest.mark.parametrize("mode, accepted_version, rejected_version, pattern",
                             [("unrelated_mode", "2.0", "", ""),
                              ("patch_mode", "1.0.0.1", "1.0.1", "1.0.1"),
                              ("minor_mode", "1.0.1", "1.2", "1.2.Z"),
                              ("major_mode", "1.5", "2.0", "2.Y.Z"),
                              ("semver_mode", "1.5", "2.0", "2.Y.Z"),
                              ("full_mode", "1.0", "1.0.0.1", "1.0.0.1")])
    def test(self, mode, accepted_version, rejected_version, pattern):
        c = TestClient()
        package_id_text = f'self.info.requires["dep"].{mode}()'
        c.save({"dep/conanfile.py": GenConanfile("dep"),
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]")
                                                              .with_package_id(package_id_text)})
        c.run("create dep --version=1.0")
        pkgid = c.created_package_id("dep/1.0")
        c.run("create pkg")
        c.run(f"create dep --version={accepted_version}")
        c.run("install --requires=pkg/0.1")  # binary existing
        c.assert_listed_binary({f"dep/{accepted_version}": (pkgid, "Cache")})
        if rejected_version:
            c.run(f"create dep --version={rejected_version}")
            c.run("install --requires=pkg/0.1", assert_error=True)  # binary missing
            assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out
            assert f"dep/{pattern}" in c.out


@pytest.mark.parametrize("mode, pkg_id",
                             [("unrelated_mode", "da39a3ee5e6b4b0d3255bfef95601890afd80709"),
                              ("semver_mode", "13b9e753af3958dd1b2d4b3f935b04b8fb6b6760"),
                              ("patch_mode", "38d7a3ec6a09165ab3e5306f81c539a2e0a784bd"),
                              ("minor_mode", "a5e7ad26ccf4a5049090976846da1c6ed165cced"),
                              ("major_mode", "6ac597ffb99c3747ed78699f206dc1041537a8df"),
                              # This is equal to semver_mode for 0.X.Y.Z..
                              ("full_version_mode", "13b9e753af3958dd1b2d4b3f935b04b8fb6b6760"),
                              ("revision_mode", "ae5b9eeb74880aeb1cfa3db7f84c007a05ce3a76"),
                              ("full_mode", "d1b2a9538cd69363b4bae7e66c9f900b8f4c58bb")])
def test_modes(mode, pkg_id):
    c = TestClient(light=True)
    package_id_text = f'self.info.requires.{mode}()'
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1.1.1").with_settings("os"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]")
                                                          .with_package_id(package_id_text)})
    c.run("create dep -s os=Linux")
    c.run("create pkg -s os=Linux")
    pkgid = c.created_package_id("pkg/0.1")
    assert pkgid == pkg_id


class TestPackageIDError:

    def test_transitive_multi_mode_package_id(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=dep1 --version=1.0 --user=user --channel=testing")
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")})
        client.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        pkg_revision_mode = "self.info.requires.recipe_revision_mode()"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                                                   .with_package_id(pkg_revision_mode)})
        client.run("export . --name=dep3 --version=1.0 --user=user --channel=testing")

        client.save({"conanfile.py": GenConanfile().with_require("dep2/1.0@user/testing")
                                                   .with_require("dep3/1.0@user/testing")})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build=*')
        assert "consumer/1.0@user/testing: Created" in client.out

    def test_transitive_multi_mode2_package_id(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        # This is mandatory, otherwise it doesn't work
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=dep1 --version=1.0 --user=user --channel=testing")

        pkg_revision_mode = "self.info.requires.full_version_mode()"
        package_id_print = "self.output.info('PkgNames: %s' % sorted(self.info.requires.pkg_names))"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                    .with_package_id(pkg_revision_mode)
                    .with_package_id(package_id_print)})
        client.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        consumer = textwrap.dedent("""
            from conan import ConanFile
            class Consumer(ConanFile):
                requires = "dep2/1.0@user/testing"
                def package_id(self):
                    self.output.info("PKGNAMES: %s" % sorted(self.info.requires.pkg_names))
                """)
        client.save({"conanfile.py": consumer})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build=*')
        assert "dep2/1.0@user/testing: PkgNames: ['dep1']" in client.out
        assert "consumer/1.0@user/testing: PKGNAMES: ['dep1', 'dep2']" in client.out
        assert "consumer/1.0@user/testing: Created" in client.out

    def test_transitive_multi_mode_build_requires(self):
        # https://github.com/conan-io/conan/issues/6942
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=dep1 --version=1.0 --user=user --channel=testing")
        client.run("create . --name=tool --version=1.0 --user=user --channel=testing")

        pkg_revision_mode = "self.info.requires.full_version_mode()"
        package_id_print = "self.output.info('PkgNames: %s' % sorted(self.info.requires.pkg_names))"
        client.save({"conanfile.py": GenConanfile().with_require("dep1/1.0@user/testing")
                    .with_tool_requires("tool/1.0@user/testing")
                    .with_package_id(pkg_revision_mode)
                    .with_package_id(package_id_print)})
        client.run("export . --name=dep2 --version=1.0 --user=user --channel=testing")

        consumer = textwrap.dedent("""
            from conan import ConanFile
            class Consumer(ConanFile):
                requires = "dep2/1.0@user/testing"
                build_requires = "tool/1.0@user/testing"
                def package_id(self):
                    self.output.info("PKGNAMES: %s" % sorted(self.info.requires.pkg_names))
                """)
        client.save({"conanfile.py": consumer})
        client.run('create . --name=consumer --version=1.0 --user=user --channel=testing --build=*')
        assert "dep2/1.0@user/testing: PkgNames: ['dep1']" in client.out
        assert "consumer/1.0@user/testing: PKGNAMES: ['dep1', 'dep2']" in client.out
        assert "consumer/1.0@user/testing: Created" in client.out


class TestRequirementPackageId:
    """ defining requires(..., package_id_mode)
    """

    @pytest.mark.parametrize("mode, pattern",
                             [("patch_mode", "1.2.3"),
                              ("minor_mode", "1.2.Z"),
                              ("major_mode",  "1.Y.Z")])
    def test(self, mode, pattern):
        c = TestClient(light=True)
        pkg = GenConanfile("pkg", "0.1").with_requirement("dep/1.2.3", package_id_mode=mode)
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.2.3"),
                "pkg/conanfile.py": pkg})
        c.run("create dep")
        c.run("create pkg")
        c.run("list pkg:*")
        assert f"dep/{pattern}" in c.out

    def test_wrong_mode(self):
        c = TestClient(light=True)
        pkg = GenConanfile("pkg", "0.1").with_requirement("dep/1.2.3", package_id_mode="nothing")
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.2.3"),
                "pkg/conanfile.py": pkg})
        c.run("create dep")
        c.run("create pkg", assert_error=True)
        assert "ERROR: require dep/1.2.3 package_id_mode='nothing' is not a known package_id_mode" \
               in c.out

    @pytest.mark.parametrize("mode, pattern",
                             [("patch_mode", "1.2.3"),
                              ("minor_mode", "1.2.Z"),
                              ("major_mode", "1.Y.Z")])
    def test_half_diamond(self, mode, pattern):
        # pkg -> libb -> liba
        #  \----(mode)----/
        c = TestClient(light=True)
        pkg = GenConanfile("pkg", "0.1").with_requirement("liba/1.2.3", package_id_mode=mode)\
                                        .with_requirement("libb/1.2.3")
        c.save({"liba/conanfile.py": GenConanfile("liba", "1.2.3"),
                "libb/conanfile.py": GenConanfile("libb", "1.2.3").with_requires("liba/1.2.3"),
                "pkg/conanfile.py": pkg})
        c.run("create liba")
        c.run("create libb")
        c.run("create pkg")
        c.run("list pkg:*")
        assert f"liba/{pattern}" in c.out
        # reverse order also works the same
        pkg = GenConanfile("pkg", "0.1").with_requirement("libb/1.2.3")\
                                        .with_requirement("liba/1.2.3", package_id_mode=mode)
        c.save({"pkg/conanfile.py": pkg})
        c.run("create pkg")
        c.run("list pkg:*")
        assert f"liba/{pattern}" in c.out

    @pytest.mark.parametrize("mode, pattern",
                             [("patch_mode", "1.2.3"),
                              ("minor_mode", "1.2.Z"),
                              ("major_mode", "1.Y.Z")])
    def test_half_diamond_conflict(self, mode, pattern):
        # pkg -> libb --(mode)-> liba
        #  \----(mode)-----------/
        # The libb->liba mode is not propagated down to pkg, so it doesn't really conflict
        c = TestClient(light=True)
        pkg = GenConanfile("pkg", "0.1").with_requirement("liba/1.2.3", package_id_mode=mode) \
            .with_requirement("libb/1.2.3")
        libb = GenConanfile("libb", "1.2.3").with_requirement("liba/1.2.3",
                                                              package_id_mode="patch_mode")
        c.save({"liba/conanfile.py": GenConanfile("liba", "1.2.3"),
                "libb/conanfile.py": libb,
                "pkg/conanfile.py": pkg})
        c.run("create liba")
        c.run("create libb")
        c.run("create pkg")
        c.run("list pkg:*")
        assert f"liba/{pattern}" in c.out
        # reverse order also works the same
        pkg = GenConanfile("pkg", "0.1").with_requirement("libb/1.2.3") \
            .with_requirement("liba/1.2.3", package_id_mode=mode)
        c.save({"pkg/conanfile.py": pkg})
        c.run("create pkg")
        c.run("list pkg:*")
        assert f"liba/{pattern}" in c.out
