import pytest
from mock import Mock

from conan.tools.b2 import B2Toolchain
from conan.tools.b2 import utils as b2_utils
from conan import ConanFile
from conans.model.conf import Conf
from conans.model.settings import Settings
from conans.model.conf import Conf
from conans.model.layout import Infos
from conan.tools.env.environment import Environment
from conan.tools.env.virtualbuildenv import VirtualBuildEnv


@pytest.fixture
def conanfile():
    c = ConanFile()
    settings = Settings({'os': ['Windows'],
                         'compiler': {
                             'clang': {
                                 'libcxx': ['libstdc++'],
                                 'version': ['14'],
                             }
                         },
                         'build_type': ['Release'],
                         'arch': ['x86'],})
    c.settings = settings
    c.settings.build_type = 'Release'
    c.settings.arch = 'x86'
    c.settings.compiler = 'clang'
    c.settings.compiler.libcxx = 'libstdc++'
    c.settings.compiler.version = '14'
    c.settings_build = c.settings
    c.settings.os = 'Windows'

    env = Environment()
    env.define('CXX', '/no/such/path')
    env.define('CXXFLAGS', '-foo=bar --bar=foo')
    env.define('LDFLAGS', '-xyz -abc')
    env.define('RC', '/no/such/rc')
    c._conan_buildenv = env

    c.folders.set_base_folders('.', 'conan')
    c.folders.set_base_generators('conan')
    c.folders.set_base_package('/package')
    c.folders.set_base_package('/package')

    c.cpp = Infos()
    c.cpp.package.resdirs = ['share']

    c._conan_node = Mock()
    c._conan_node.transitive_deps = {}

    return c


def test_b2_toolchain(conanfile):
    toolchain = B2Toolchain(conanfile)
    toolchain.using('asciidoctor', 'my/asciidoctor')

    variation = b2_utils.variation(conanfile)
    variation_id = b2_utils.variation_id(variation)
    variation_key = b2_utils.variation_key(variation_id)

    content = toolchain._content

    common = _common.format(variation_key=variation_key)
    assert common == content['project-config.jam']
    assert _variation == content['conan-config-%s.jam' % variation_key]


_common = '''\
# Conan automatically generated config file
# DO NOT EDIT MANUALLY, it will be overwritten

import path ;

local location = [ path.make conan ] ;
location = [ path.relative $(location) [ path.pwd ] ] ;
for local pc in [ GLOB $(location) : conan-config-*.jam : downcase ] {{
    local __define_project__ ;
    if $(pc) = $(location)/conan-config-{variation_key}.jam {{
        __define_project__ = yes ;
    }}
    include $(pc) ;
}}

use-packages $(location)/conanbuildinfo.jam ;
'''

_variation = '''\
# Conan automatically generated config file
# DO NOT EDIT MANUALLY, it will be overwritten

using clang : 14 : /no/such/path : <cxxflags>"-foo=bar" <cxxflags>"--bar=foo" <linkflags>"-xyz" <linkflags>"-abc" <rc>"/no/such/rc" : <address-model>"32" <architecture>"x86" <stdlib>"gnu" <target-os>"windows" <variant>"release" ;
using asciidoctor : my/asciidoctor ;

if $(__define_project__) = yes {
    project
        : default-build
          <address-model>32
          <architecture>x86
          <stdlib>gnu
          <target-os>windows
          <toolset>clang-14
          <variant>release
        ;
    import option ;
    option.set prefix : /package ;
    option.set bindir : /package/bin ;
    option.set libdir : /package/lib ;
    option.set includedir : /package/include ;
    option.set datarootdir : /package/share ;
}
'''
