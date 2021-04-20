import unittest

from mock import Mock

from conans.client.conf import get_default_settings_yml
from conans.client.generators.b2 import B2Generator
from conans.model.build_info import CppInfo
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings


class B2GeneratorTest(unittest.TestCase):

    def test_b2(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        settings.cppstd = "gnu17"

        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())
        conanfile.settings = settings

        ref = ConanFileReference.loads("MyPkg/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder1")
        cpp_info.defines = ["MYDEFINE1"]
        cpp_info.cflags.append("-Flag1=23")
        cpp_info.version = "1.3"
        cpp_info.description = "My cool description"
        cpp_info.libs = ["MyLib1"]

        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        ref = ConanFileReference.loads("MyPkg2/0.1@lasote/stables")
        cpp_info = CppInfo(ref.name, "dummy_root_folder2")
        cpp_info.libs = ["MyLib2"]
        cpp_info.defines = ["MYDEFINE2"]
        cpp_info.version = "2.3"
        cpp_info.exelinkflags = ["-exelinkflag"]
        cpp_info.sharedlinkflags = ["-sharedlinkflag"]
        cpp_info.cxxflags = ["-cxxflag"]
        cpp_info.public_deps = ["MyPkg"]
        cpp_info.libdirs.extend(["Path\\with\\slashes", "regular/path/to/dir"])
        cpp_info.includedirs.extend(["other\\Path\\with\\slashes", "other/regular/path/to/dir"])
        cpp_info.filter_empty = False
        conanfile.deps_cpp_info.add(ref.name, cpp_info)

        generator = B2Generator(conanfile)

        content = {
            'conanbuildinfo.jam': _main_buildinfo_full,
            'conanbuildinfo-316f2f0b155dc874a672d40d98d93f95.jam':
                _variation_full,
        }

        for ck, cv in generator.content.items():
            self.assertEqual(cv, content[ck])

    def test_b2_empty_settings(self):
        conanfile = ConanFile(Mock(), None)
        conanfile.initialize(Settings({}), EnvValues())

        generator = B2Generator(conanfile)

        content = {
            'conanbuildinfo.jam': _main_buildinfo_empty,
            'conanbuildinfo-d41d8cd98f00b204e9800998ecf8427e.jam':
                _variation_empty,
        }

        for ck, cv in generator.content.items():
            self.assertEqual(cv, content[ck])

_main_buildinfo_full = '''\
#|
    B2 definitions for Conan packages. This is a generated file.
    Edit the corresponding conanfile.txt instead.
|#

import path ;
import project ;
import modules ;
import feature ;

local base-project = [ project.current ] ;
local base-project-mod = [ $(base-project).project-module ] ;
local base-project-location = [ project.attribute $(base-project-mod) location ] ;

rule project-define ( id )
{
    id = $(id:L) ;
    local saved-project = [ modules.peek project : .base-project ] ;
    local id-location = [ path.join $(base-project-location) $(id) ] ;
    local id-mod = [ project.load $(id-location) : synthesize ] ;
    project.initialize $(id-mod) : $(id-location) ;
    project.inherit-attributes $(id-mod) : $(base-project-mod) ;
    local attributes = [ project.attributes $(id-mod) ] ;
    $(attributes).set parent-module : $(base-project-mod) : exact ;
    modules.poke $(base-project-mod) : $(id)-mod : $(id-mod) ;
    modules.poke [ CALLER_MODULE ] : $(id)-mod : $(id-mod) ;
    modules.poke project : .base-project : $(saved-project) ;
    IMPORT $(__name__)
        : constant-if call-in-project
        : $(id-mod)
        : constant-if call-in-project ;
    if [ project.is-jamroot-module $(base-project-mod) ]
    {
        use-project /$(id) : $(id) ;
    }
    return $(id-mod) ;
}

rule constant-if ( name : value * )
{
    if $(__define_constants__) && $(value)
    {
        call-in-project : constant $(name) : $(value) ;
        modules.poke $(__name__) : $(name) : [ modules.peek $(base-project-mod) : $(name) ] ;
    }
}

rule call-in-project ( project-mod ? : rule-name args * : * )
{
    project-mod ?= $(base-project-mod) ;
    project.push-current [ project.target $(project-mod) ] ;
    local result = [ modules.call-in $(project-mod) :
        $(2) : $(3) : $(4) : $(5) : $(6) : $(7) : $(8) : $(9) : $(10) :
        $(11) : $(12) : $(13) : $(14) : $(15) : $(16) : $(17) : $(18) :
        $(19) ] ;
    project.pop-current ;
    return $(result) ;
}

rule include-conanbuildinfo ( cbi )
{
    include $(cbi) ;
}

IMPORT $(__name__)
    : project-define constant-if call-in-project include-conanbuildinfo
    : $(base-project-mod)
    : project-define constant-if call-in-project include-conanbuildinfo ;

if ! ( relwithdebinfo in [ feature.values variant ] )
{
    variant relwithdebinfo : : <optimization>speed <debug-symbols>on <inlining>full <runtime-debugging>off ;
}
if ! ( minsizerel in [ feature.values variant ] )
{
    variant minsizerel : : <optimization>space <debug-symbols>off <inlining>full <runtime-debugging>off ;
}

local __conanbuildinfo__ = [ GLOB $(__file__:D) : conanbuildinfo-*.jam : downcase ] ;
{
    local __define_constants__ = yes ;
    for local __cbi__ in $(__conanbuildinfo__)
    {
        call-in-project : include-conanbuildinfo $(__cbi__) ;
    }
}


# mypkg
project-define mypkg ;


# mypkg2
project-define mypkg2 ;

{
    local __define_targets__ = yes ;
    for local __cbi__ in $(__conanbuildinfo__)
    {
        call-in-project : include-conanbuildinfo $(__cbi__) ;
    }
}
'''

_variation_full = '''\
#|
    B2 definitions for Conan packages. This is a generated file.
    Edit the corresponding conanfile.txt instead.
|#

# global
constant-if rootpath(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    ""
    ;

constant-if includedirs(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    "dummy_root_folder2/include"
    "dummy_root_folder2/other/Path/with/slashes"
    "dummy_root_folder2/other/regular/path/to/dir"
    ;

constant-if libdirs(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    "dummy_root_folder2/lib"
    "dummy_root_folder2/Path/with/slashes"
    "dummy_root_folder2/regular/path/to/dir"
    ;

constant-if defines(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    "MYDEFINE2"
    "MYDEFINE1"
    ;

constant-if cppflags(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    "-cxxflag"
    ;

constant-if cflags(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    "-Flag1=23"
    ;

constant-if sharedlinkflags(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    "-sharedlinkflag"
    ;

constant-if exelinkflags(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    "-exelinkflag"
    ;

constant-if requirements(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    <address-model>32
    <architecture>x86
    <cxxstd>17
    <cxxstd:dialect>gnu
    <target-os>linux
    <toolset>gcc-6.3
    <variant>release
    ;

constant-if usage-requirements(conan,32,x86,17,gnu,linux,gcc-6.3,release) :
    <include>$(includedirs(conan,32,x86,17,gnu,linux,gcc-6.3,release))
    <define>$(defines(conan,32,x86,17,gnu,linux,gcc-6.3,release))
    <cflags>$(cflags(conan,32,x86,17,gnu,linux,gcc-6.3,release))
    <cxxflags>$(cppflags(conan,32,x86,17,gnu,linux,gcc-6.3,release))
    <link>shared:<linkflags>$(sharedlinkflags(conan,32,x86,17,gnu,linux,gcc-6.3,release))
    ;

# mypkg
constant-if rootpath(mypkg,32,x86,17,gnu,linux,gcc-6.3,release) :
    "dummy_root_folder1"
    ;

constant-if defines(mypkg,32,x86,17,gnu,linux,gcc-6.3,release) :
    "MYDEFINE1"
    ;

constant-if cflags(mypkg,32,x86,17,gnu,linux,gcc-6.3,release) :
    "-Flag1=23"
    ;

constant-if requirements(mypkg,32,x86,17,gnu,linux,gcc-6.3,release) :
    <address-model>32
    <architecture>x86
    <cxxstd>17
    <cxxstd:dialect>gnu
    <target-os>linux
    <toolset>gcc-6.3
    <variant>release
    ;

constant-if usage-requirements(mypkg,32,x86,17,gnu,linux,gcc-6.3,release) :
    <include>$(includedirs(mypkg,32,x86,17,gnu,linux,gcc-6.3,release))
    <define>$(defines(mypkg,32,x86,17,gnu,linux,gcc-6.3,release))
    <cflags>$(cflags(mypkg,32,x86,17,gnu,linux,gcc-6.3,release))
    <cxxflags>$(cppflags(mypkg,32,x86,17,gnu,linux,gcc-6.3,release))
    <link>shared:<linkflags>$(sharedlinkflags(mypkg,32,x86,17,gnu,linux,gcc-6.3,release))
    ;

# mypkg2
constant-if rootpath(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    "dummy_root_folder2"
    ;

constant-if includedirs(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    "dummy_root_folder2/include"
    "dummy_root_folder2/other/Path/with/slashes"
    "dummy_root_folder2/other/regular/path/to/dir"
    ;

constant-if libdirs(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    "dummy_root_folder2/lib"
    "dummy_root_folder2/Path/with/slashes"
    "dummy_root_folder2/regular/path/to/dir"
    ;

constant-if defines(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    "MYDEFINE2"
    ;

constant-if cppflags(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    "-cxxflag"
    ;

constant-if sharedlinkflags(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    "-sharedlinkflag"
    ;

constant-if exelinkflags(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    "-exelinkflag"
    ;

constant-if requirements(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    <address-model>32
    <architecture>x86
    <cxxstd>17
    <cxxstd:dialect>gnu
    <target-os>linux
    <toolset>gcc-6.3
    <variant>release
    ;

constant-if usage-requirements(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release) :
    <include>$(includedirs(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release))
    <define>$(defines(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release))
    <cflags>$(cflags(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release))
    <cxxflags>$(cppflags(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release))
    <link>shared:<linkflags>$(sharedlinkflags(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release))
    ;

# mypkg
if $(__define_targets__) {
    call-in-project $(mypkg-mod) : lib MyLib1
        : ''' + '''
        : <name>MyLib1 <search>$(libdirs(mypkg,32,x86,17,gnu,linux,gcc-6.3,release)) $(requirements(mypkg,32,x86,17,gnu,linux,gcc-6.3,release))
        :
        : $(usage-requirements(mypkg,32,x86,17,gnu,linux,gcc-6.3,release)) ;
    call-in-project $(mypkg-mod) : explicit MyLib1 ; }

if $(__define_targets__) {
    call-in-project $(mypkg-mod) : alias libs
        : MyLib1
        : $(requirements(mypkg,32,x86,17,gnu,linux,gcc-6.3,release))
        :
        : $(usage-requirements(mypkg,32,x86,17,gnu,linux,gcc-6.3,release)) ;
    call-in-project $(mypkg-mod) : explicit libs ; }

# mypkg2
if $(__define_targets__) {
    call-in-project $(mypkg2-mod) : lib MyLib2
        : /MyPkg//libs
        : <name>MyLib2 <search>$(libdirs(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release)) $(requirements(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release))
        :
        : $(usage-requirements(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release)) ;
    call-in-project $(mypkg2-mod) : explicit MyLib2 ; }

if $(__define_targets__) {
    call-in-project $(mypkg2-mod) : alias libs
        : /MyPkg//libs MyLib2
        : $(requirements(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release))
        :
        : $(usage-requirements(mypkg2,32,x86,17,gnu,linux,gcc-6.3,release)) ;
    call-in-project $(mypkg2-mod) : explicit libs ; }
'''

_main_buildinfo_empty = '''\
#|
    B2 definitions for Conan packages. This is a generated file.
    Edit the corresponding conanfile.txt instead.
|#

import path ;
import project ;
import modules ;
import feature ;

local base-project = [ project.current ] ;
local base-project-mod = [ $(base-project).project-module ] ;
local base-project-location = [ project.attribute $(base-project-mod) location ] ;

rule project-define ( id )
{
    id = $(id:L) ;
    local saved-project = [ modules.peek project : .base-project ] ;
    local id-location = [ path.join $(base-project-location) $(id) ] ;
    local id-mod = [ project.load $(id-location) : synthesize ] ;
    project.initialize $(id-mod) : $(id-location) ;
    project.inherit-attributes $(id-mod) : $(base-project-mod) ;
    local attributes = [ project.attributes $(id-mod) ] ;
    $(attributes).set parent-module : $(base-project-mod) : exact ;
    modules.poke $(base-project-mod) : $(id)-mod : $(id-mod) ;
    modules.poke [ CALLER_MODULE ] : $(id)-mod : $(id-mod) ;
    modules.poke project : .base-project : $(saved-project) ;
    IMPORT $(__name__)
        : constant-if call-in-project
        : $(id-mod)
        : constant-if call-in-project ;
    if [ project.is-jamroot-module $(base-project-mod) ]
    {
        use-project /$(id) : $(id) ;
    }
    return $(id-mod) ;
}

rule constant-if ( name : value * )
{
    if $(__define_constants__) && $(value)
    {
        call-in-project : constant $(name) : $(value) ;
        modules.poke $(__name__) : $(name) : [ modules.peek $(base-project-mod) : $(name) ] ;
    }
}

rule call-in-project ( project-mod ? : rule-name args * : * )
{
    project-mod ?= $(base-project-mod) ;
    project.push-current [ project.target $(project-mod) ] ;
    local result = [ modules.call-in $(project-mod) :
        $(2) : $(3) : $(4) : $(5) : $(6) : $(7) : $(8) : $(9) : $(10) :
        $(11) : $(12) : $(13) : $(14) : $(15) : $(16) : $(17) : $(18) :
        $(19) ] ;
    project.pop-current ;
    return $(result) ;
}

rule include-conanbuildinfo ( cbi )
{
    include $(cbi) ;
}

IMPORT $(__name__)
    : project-define constant-if call-in-project include-conanbuildinfo
    : $(base-project-mod)
    : project-define constant-if call-in-project include-conanbuildinfo ;

if ! ( relwithdebinfo in [ feature.values variant ] )
{
    variant relwithdebinfo : : <optimization>speed <debug-symbols>on <inlining>full <runtime-debugging>off ;
}
if ! ( minsizerel in [ feature.values variant ] )
{
    variant minsizerel : : <optimization>space <debug-symbols>off <inlining>full <runtime-debugging>off ;
}

local __conanbuildinfo__ = [ GLOB $(__file__:D) : conanbuildinfo-*.jam : downcase ] ;
{
    local __define_constants__ = yes ;
    for local __cbi__ in $(__conanbuildinfo__)
    {
        call-in-project : include-conanbuildinfo $(__cbi__) ;
    }
}

{
    local __define_targets__ = yes ;
    for local __cbi__ in $(__conanbuildinfo__)
    {
        call-in-project : include-conanbuildinfo $(__cbi__) ;
    }
}
'''

_variation_empty = '''\
#|
    B2 definitions for Conan packages. This is a generated file.
    Edit the corresponding conanfile.txt instead.
|#

# global
constant-if rootpath(conan,) :
    ""
    ;

constant-if usage-requirements(conan,) :
    <include>$(includedirs(conan,))
    <define>$(defines(conan,))
    <cflags>$(cflags(conan,))
    <cxxflags>$(cppflags(conan,))
    <link>shared:<linkflags>$(sharedlinkflags(conan,))
    ;
'''
