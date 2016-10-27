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

[scope]'''


class ConanInfoTest(unittest.TestCase):

    def test_serialize(self):
        info = ConanInfo.loads(info_text)
        min_serial = info.serialize_min()
        expected = {'full_requires':
                    ['bzip2/1.0.6@lasote/stable:c6c01ee5ea2cf4af63e7b83b722b0a2d90640641',
                     'zlib/1.2.8@lasote/stable:2dec3996ef8de7edb0304eaf4efdd96a0477d3a3'],
                    'options': {'shared': 'False', 'fPIC': 'True', 'header_only': 'False'},
                    'recipe_hash': None,
                    'settings': {'arch': 'x86_64', 'compiler.libcxx': 'libstdc++11',
                                 'compiler.version': '5.2', 'os': 'Linux',
                                 'build_type': 'Debug', 'compiler': 'gcc'}}
        self.assertEquals(min_serial, expected)
