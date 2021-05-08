import pytest
from mock import Mock

from conan.tools.b2 import B2Toolchain
from conan.tools.b2 import utils as b2_utils
from conans import (
    ConanFile,
    Settings,
    tools,
)
from conans.client.conf import get_default_settings_yml
from conans.model.conf import Conf
from conans.model.env_info import EnvValues


@pytest.fixture
def conanfile():
    c = ConanFile(Mock(), None)
    c.initialize(Settings({}), EnvValues())
    c.conf = Conf()
    c.folders.set_base_package("/package")
    c.folders.set_base_install("conan")
    c.folders.set_base_generators(".")

    settings = Settings.loads(get_default_settings_yml())
    settings.arch = 'x86'
    settings.os = 'Windows'
    settings.compiler = 'gcc'
    settings.compiler.version = '9.3'
    settings.build_type = 'Release'
    c.settings = settings

    return c


def test_b2_toolchain(conanfile):
    with tools.environment_append({
        'CXX': '/no/such/path',
        'CPPFLAGS': '-foo=bar --bar=foo',
        'LDFLAGS': '-xyz -abc',
        'RC': '/no/such/rc',
    }):
        toolchain = B2Toolchain(conanfile)
        toolchain.using('asciidoctor', 'my/asciidoctor')

        variation = b2_utils.variation(conanfile)
        variation_id = b2_utils.variation_id(variation)
        variation_key = b2_utils.variation_key(variation_id)

        assert toolchain.filename is None

        content = toolchain.content

        common = _common.format(variation_key=variation_key)
        assert common == content['project-config.jam']
        assert _variation == content['conan-config-%s.jam' % variation_key]


_common = '''\
# Conan automatically generated config file
# DO NOT EDIT MANUALLY, it will be overwritten

import path ;

local location = [ path.make conan ] ;
location = [ path.relative $(location) [ path.pwd ] ] ;
for local pc in [ GLOB $(location) : project-config-*.jam : downcase ] {{
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

import feature ;
local all-toolsets = [ feature.values toolset ] ;
if ! gcc in $(all-toolsets) ||
   ! [ feature.is-subvalue toolset : gcc : version : 9.3 ]
{ using gcc : 9.3 : /no/such/path : <cxxflags>"-foo=bar" <cxxflags>"--bar=foo" <ldflags>"-xyz" <ldflags>"-abc" <rc>"/no/such/rc" ; }
if ! asciidoctor in $(all-toolsets)
{ using asciidoctor : my/asciidoctor ; }

if $(__define_project__) = yes {
    project
        : default-build
          <address-model>32
          <architecture>x86
          <target-os>windows
          <toolset>gcc-9.3
          <variant>release
        ;
    import option ;
    option.set prefix : /package ;
    option.set bindir : /package/bin ;
    option.set libdir : /package/lib ;
    option.set includedir : /package/include ;
    option.set datarootdir : /package/res ;
}
'''
