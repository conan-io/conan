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

        # 1. Create build req
        t.run("create br/conanfile.py")

        # 2. Create lock
        t.run("graph lock boost/conanfile.py --build".format(boost_ref))

        # 3. Compute build order
        t.run("graph build-order conan.lock --build")

        # 4. Create the first element of build order
        t.run("install {}@ --lockfile=conan.lock --build={}".format(br_ref, br_ref.name))
