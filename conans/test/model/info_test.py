import unittest
from conans.model.info import ConanInfo

info_text = '''[settings]
    arch=x86_64
    build_type=Debug
    compiler=gcc
    compiler.libcxx=libstdc++11
    compiler.version=5.2
    os=Linux

[requires]
    bzip2/1.Y.Z
    zlib/1.Y.Z

[options]
    fPIC=True
    header_only=False
    shared=False

[full_settings]
    arch=x86_64
    build_type=Debug
    compiler=gcc
    compiler.libcxx=libstdc++11
    compiler.version=5.2
    os=Linux

[full_requires]
    bzip2/1.0.6@lasote/stable:c6c01ee5ea2cf4af63e7b83b722b0a2d90640641
    zlib/1.2.8@lasote/stable:2dec3996ef8de7edb0304eaf4efdd96a0477d3a3

[full_options]
    fPIC=True
    header_only=False
    shared=False
    bzip2:fPIC=True
    bzip2:shared=False
    zlib:shared=False

[scope]
    dev=True

[recipe_hash]
    asdasdasd

[env]
    A_OTHERVAR=OTHERVALUES
    Z_OTHERVAR=OTHERVALUES
    Aackage1:PATH=/PATH/TO
    Package1:PATH=/PATH/TO
'''


class ConanInfoTest(unittest.TestCase):

    def test_serialize(self):
        info = ConanInfo.loads(info_text)
        min_serial = info.serialize_min()
        expected = {'full_requires':
                    ['bzip2/1.0.6@lasote/stable:c6c01ee5ea2cf4af63e7b83b722b0a2d90640641',
                     'zlib/1.2.8@lasote/stable:2dec3996ef8de7edb0304eaf4efdd96a0477d3a3'],
                    'options': {'shared': 'False', 'fPIC': 'True', 'header_only': 'False'},
                    'recipe_hash': "asdasdasd",
                    'settings': {'arch': 'x86_64', 'compiler.libcxx': 'libstdc++11',
                                 'compiler.version': '5.2', 'os': 'Linux',
                                 'build_type': 'Debug', 'compiler': 'gcc'}}
        self.assertEquals(min_serial, expected)

        dump = info.dumps()
        self.assertEquals(dump, info_text)

    def test_modes(self):
        info_text = '''[settings]
    arch=x86_64
    build_type=Debug
    compiler=gcc
    compiler.libcxx=libstdc++11
    compiler.version=5.2
    os=Linux

[full_requires]
    bzip2/1.2.3-alpha1+build123@lasote/testing:sha1
    zlib/0.3@lasote/testing:sha2
    poco/2.3.4+build123@lasote/stable:sha3

[options]
    fPIC=True
    header_only=False
    shared=False
'''
        info = ConanInfo.loads(info_text)
        info.header_only()
        self.assertEqual(info.settings.dumps(), "")
        self.assertEqual(info.options.dumps(), "")
        self.assertEqual(info.requires.dumps(), "")

        info = ConanInfo.loads(info_text)
        info.requires.unrelated_mode()
        self.assertEqual(info.requires.dumps(), "")

        info = ConanInfo.loads(info_text)
        info.requires.semver_mode()
        self.assertEqual(info.requires.dumps(), "bzip2/1.Y.Z\npoco/2.Y.Z\nzlib/0.3")

        info = ConanInfo.loads(info_text)
        info.requires.patch_mode()
        self.assertEqual(info.requires.dumps(), "bzip2/1.2.3\npoco/2.3.4\nzlib/0.3.0")

        info = ConanInfo.loads(info_text)
        info.requires.minor_mode()
        self.assertEqual(info.requires.dumps(), "bzip2/1.2.Z\npoco/2.3.Z\nzlib/0.3.Z")

        info = ConanInfo.loads(info_text)
        info.requires.major_mode()
        self.assertEqual(info.requires.dumps(), "bzip2/1.Y.Z\npoco/2.Y.Z\nzlib/0.Y.Z")

        info = ConanInfo.loads(info_text)
        info.requires.base_mode()
        self.assertEqual(info.requires.dumps(), "bzip2/1.2.3-alpha1\npoco/2.3.4\nzlib/0.3")

        info = ConanInfo.loads(info_text)
        info.requires.full_version_mode()
        self.assertEqual(info.requires.dumps(), "bzip2/1.2.3-alpha1+build123\n"
                                                "poco/2.3.4+build123\n"
                                                "zlib/0.3")

        info = ConanInfo.loads(info_text)
        info.requires.full_recipe_mode()
        self.assertEqual(info.requires.dumps(), "bzip2/1.2.3-alpha1+build123@lasote/testing\n"
                                                "poco/2.3.4+build123@lasote/stable\n"
                                                "zlib/0.3@lasote/testing")

        info = ConanInfo.loads(info_text)
        info.requires.full_package_mode()
        self.assertEqual(info.requires.dumps(), "bzip2/1.2.3-alpha1+build123@lasote/testing:sha1\n"
                                                "poco/2.3.4+build123@lasote/stable:sha3\n"
                                                "zlib/0.3@lasote/testing:sha2")
