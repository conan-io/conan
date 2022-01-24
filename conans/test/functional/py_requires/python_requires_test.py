import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient


class PyRequiresExtendTest(unittest.TestCase):

    @pytest.mark.tool_git
    def test_reuse_scm(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class SomeBase(object):
                scm = {"type" : "git",
                       "url" : "somerepo",
                       "revision" : "auto"}

            class MyConanfileBase(SomeBase, ConanFile):
                pass
            """)
        client.init_git_repo({"conanfile.py": conanfile}, branch="my_release")
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.SomeBase"

                def source(self):
                    self.output.info("URL: {}!!!!".format(self.scm["url"]))
                    self.output.info("Type: {}!!!!".format(self.scm["type"]))
                    self.output.info("Commit: {}!!!!".format(self.scm["revision"] is not None))
            """)
        client.save({"conanfile.py": reuse})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        assert "pkg/0.1@user/testing: URL: somerepo!!!!" in client.out
        assert "pkg/0.1@user/testing: Type: git!!!!" in client.out
        assert "pkg/0.1@user/testing: Commit: True!!!!" in client.out

    @pytest.mark.tool_git
    def test_reuse_customize_scm(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class SomeBase(object):
                base_repo = "somerepo"
                scm = {"type" : "git",
                       "url" : base_repo,
                       "revision" : "auto"}

            class MyConanfileBase(SomeBase, ConanFile):
                pass
            """)
        client.init_git_repo({"conanfile.py": conanfile}, branch="my_release")
        client.run("export . --name=base --version=1.1 --user=user --channel=testing")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                base_repo = "other_repo"
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.SomeBase"
                def init(self):
                    self.scm["url"] = self.base_repo

                def source(self):
                    self.output.info("URL: {}!!!!".format(self.scm["url"]))
                    self.output.info("Type: {}!!!!".format(self.scm["type"]))
                    self.output.info("Commit: {}!!!!".format(self.scm["revision"] is not None))
            """)
        client.save({"conanfile.py": reuse})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")

        assert "pkg/0.1@user/testing: URL: other_repo!!!!" in client.out
        assert "pkg/0.1@user/testing: Type: git!!!!" in client.out
        assert "pkg/0.1@user/testing: Commit: True!!!!" in client.out

    @pytest.mark.tool_git
    def test_reuse_scm_multiple_conandata(self):
        # https://github.com/conan-io/conan/issues/7236
        # This only works when using conandata.yml, conanfile.py replace is broken
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class SomeBase(object):
                scm = {"type" : "git",
                       "url" : "remote1",
                       "revision" : "auto"}

            class MyConanfileBase(SomeBase, ConanFile):
                pass
            """)
        base_rev = client.init_git_repo({"conanfile.py": conanfile}, branch="my_release",
                                        folder="base")
        client.run("export base --name=base --version=1.1 --user=user --channel=testing")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                name = "%s"
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.SomeBase"

                def source(self):
                    self.output.info("Commit: {}!!!!".format(self.scm["revision"]))
            """)
        reuse1_rev = client.init_git_repo({"conanfile.py": reuse % "reuse1"}, branch="release",
                                          folder="reuse1")
        reuse2_rev = client.init_git_repo({"conanfile.py": reuse % "reuse2"}, branch="release",
                                          folder="reuse2")
        client.run("create reuse1 --name=reuse1 --version=1.1 --user=user --channel=testing")
        assert f"reuse1/1.1@user/testing: Commit: {reuse1_rev}!!!!" in client.out
        client.run("create reuse2 --name=reuse2 --version=1.1 --user=user --channel=testing")
        assert f"reuse2/1.1@user/testing: Commit: {reuse2_rev}!!!!" in client.out
