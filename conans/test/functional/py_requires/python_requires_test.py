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
        client.run("get Pkg/0.1@user/testing")
        self.assertNotIn("scm = base.scm", client.out)
        self.assertIn('scm = {"revision":', client.out)
        self.assertIn('"type": "git",', client.out)
        self.assertIn('"url": "somerepo"', client.out)

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
        client.run("get base/1.1@user/testing")
        self.assertIn('"url": "somerepo"', client.out)

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
        client.run("get Pkg/0.1@user/testing")
        self.assertNotIn("scm = base.scm", client.out)
        self.assertIn('scm = {"revision":', client.out)
        self.assertIn('"type": "git",', client.out)
        self.assertIn('"url": "other_repo"', client.out)

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
        client.run("config set general.scm_to_conandata=1")
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

        client.run("inspect base/1.1@user/testing -a=scm --json=base.json")
        base_json = json.loads(client.load("base.json"))
        client.run("inspect reuse1/1.1@user/testing -a=scm --json=reuse1.json")
        reuse1_json = json.loads(client.load("reuse1.json"))
        client.run("inspect reuse2/1.1@user/testing -a=scm --json=reuse2.json")
        reuse2_json = json.loads(client.load("reuse2.json"))
        self.assertEqual(base_json["scm"]["revision"], base_rev)
        self.assertEqual(reuse1_json["scm"]["revision"], reuse1_rev)
        self.assertEqual(reuse2_json["scm"]["revision"], reuse2_rev)
        self.assertNotEqual(base_rev, reuse1_rev)
        self.assertNotEqual(base_rev, reuse2_rev)
        self.assertNotEqual(reuse2_rev, reuse1_rev)
