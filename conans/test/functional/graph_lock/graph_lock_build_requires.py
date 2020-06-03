import textwrap
import unittest

from conans.test.utils.tools import TestClient, GenConanfile
from conans.model.ref import ConanFileReference


class GraphLockBuildRequireTestCase(unittest.TestCase):


    def test_br_dupe(self):
        br_ref = ConanFileReference.loads("br/version")
        zlib_ref = ConanFileReference.loads("zlib/version")
        bzip2_ref = ConanFileReference.loads("bzip2/version")
        boost_ref = ConanFileReference.loads("boost/version")

        t = TestClient()
        t.save({
            'br/conanfile.py': GenConanfile().with_name(br_ref.name).with_version(br_ref.version),
            'zlib/conanfile.py': GenConanfile().with_name(zlib_ref.name)
                                               .with_version(zlib_ref.version)
                                               .with_build_require(br_ref),
            'bzip2/conanfile.py': GenConanfile().with_name(bzip2_ref.name)
                                                .with_version(zlib_ref.version)
                                                .with_build_require(br_ref),
            'boost/conanfile.py': GenConanfile().with_name(boost_ref.name)
                                                .with_version(boost_ref.version)
                                                .with_require(zlib_ref)
                                                .with_require(bzip2_ref)
                                                .with_build_require(br_ref),
        })
        t.run("export br/conanfile.py")
        t.run("export zlib/conanfile.py")
        t.run("export bzip2/conanfile.py")

        t.run("install boost/conanfile.py --build".format(boost_ref))
        lockfile = t.load("conan.lock")
        # TODO: Add checks, there are two 'br/version' nodes
        # TODO: Why some packages already have prev?

        t.run("create boost/conanfile.py --profile:build=default --profile:host=default --lock=conan.lock --update --build")
        # TODO: Some BR doesn't have prev!

        print(t.out)
        self.fail("AAAA")
