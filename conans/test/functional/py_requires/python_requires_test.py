import json
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
        client.run("export . base/1.1@user/testing")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.SomeBase"
            """)
        client.save({"conanfile.py": reuse})
        client.run("export . Pkg/0.1@user/testing")
        scm_info = client.scm_info("Pkg/0.1@user/testing")
        self.assertIsNotNone(scm_info.revision)
        self.assertEqual(scm_info.type, 'git')
        self.assertEqual(scm_info.url, 'somerepo')

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
        client.run("export . base/1.1@user/testing")
        scm_info = client.scm_info("base/1.1@user/testing")
        self.assertEqual(scm_info.url, "somerepo")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                base_repo = "other_repo"
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.SomeBase"
                def init(self):
                    self.scm["url"] = self.base_repo
            """)
        client.save({"conanfile.py": reuse})
        client.run("export . Pkg/0.1@user/testing")

        scm_info = client.scm_info("Pkg/0.1@user/testing")
        self.assertIsNotNone(scm_info.revision)
        self.assertEqual(scm_info.type, 'git')
        self.assertEqual(scm_info.url, 'other_repo')

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
        client.run("export base base/1.1@user/testing")

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class PkgTest(ConanFile):
                name = "%s"
                python_requires = "base/1.1@user/testing"
                python_requires_extend = "base.SomeBase"
            """)
        reuse1_rev = client.init_git_repo({"conanfile.py": reuse % "reuse1"}, branch="release",
                                          folder="reuse1")
        reuse2_rev = client.init_git_repo({"conanfile.py": reuse % "reuse2"}, branch="release",
                                          folder="reuse2")
        client.run("export reuse1 reuse1/1.1@user/testing")
        client.run("export reuse2 reuse2/1.1@user/testing")

        base = client.scm_info("base/1.1@user/testing")
        reuse1 = client.scm_info("reuse1/1.1@user/testing")
        reuse2 = client.scm_info("reuse2/1.1@user/testing")

        self.assertEqual(base.revision, base_rev)
        self.assertEqual(reuse1.revision, reuse1_rev)
        self.assertEqual(reuse2.revision, reuse2_rev)

        self.assertNotEqual(base_rev, reuse1_rev)
        self.assertNotEqual(base_rev, reuse2_rev)
        self.assertNotEqual(reuse2_rev, reuse1_rev)
