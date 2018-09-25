
"""
B2 Conan Generator
This is a generator for conanbuildinfo.jam files declaring all conan dependencies
as B2 project and library targets. This generates multiple tagged build info
source files, each containing a single variant as specified by the user's
conan install profile in addition to the central generic one that includes
all possible variants.
"""

from conans.model import Generator
from hashlib import md5


class B2Generator(Generator):

    @property
    def filename(self):
        pass  # in this case, filename defined in return value of content method

    @property
    def content(self):
        '''
        Generates two content files: conanbuildinfo.jam and conanbuildinfo-ID.jam which
        the former defines sub-projects for each package and loads the other files and
        the latter define variables and targets for the packages.
        '''
        result = {
            'conanbuildinfo.jam': None,
            self.conanbuildinfo_variation_jam: None
        }

        # Generate the common conanbuildinfo.jam which does four things:
        # 1. Defines some common utility functions to make the rest of the code short.
        # 2. Includes the conanbuildinfo-*.jam sub-files for constant declarations.
        # 3. Defines all the package sub-projects.
        # 4. Includes the conanbuildinfo-*.jam sub-files again, this time for declaring targets.
        cbi = [self.conanbuildinfo_header_text]
        # The prefix that does 1 & 2.
        cbi += [self.conanbuildinfo_prefix_text]
        # The sub-project definitions, i.e. 3.
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            cbi += ["", "# %s" % (dep_name.lower())]
            cbi += self.b2_project_for_dep(dep_name, dep_cpp_info)
        # The postfix which does 4.
        cbi += [self.conanbuildinfo_postfix_text]
        # The combined text.
        result['conanbuildinfo.jam'] = "\n".join(cbi)

        # Generate the current build variation conanbuildinfo-/variation/.jam which does two things:
        # 1. Defines project constants for the corresponding conan buildinfo variables.
        # 2. Declares targets, with b2 requirements to select the variation, for each
        #   library in a package and one "libs" target for the collection of all the libraries
        #   in the package.
        cbiv = [self.conanbuildinfo_header_text]
        # The first, 1, set of variables are collective in that they have the info for all
        # of the packages combined, 1a.
        cbiv += ["# global" ]
        cbiv += self.b2_constants_for_dep('conan', self.deps_build_info)
        # Now the constants for individual packages, 1b.
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            cbiv += ["# %s" % (dep_name.lower())]
            cbiv += self.b2_constants_for_dep(
                dep_name, dep_cpp_info, self.deps_user_info[dep_name])
        # Second, 2, part are the targets for the packages.
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            cbiv += ["# %s" % (dep_name.lower())]
            cbiv += self.b2_targets_for_dep(dep_name, dep_cpp_info)
        result[self.conanbuildinfo_variation_jam] = "\n".join(cbiv)

        return result

    def b2_project_for_dep(self, name, info):
        '''
        Generates a sub-project definition to match the package. Which is used later
        to define targets for the package libs.
        '''
        if not info:
            return []
        name = name.lower()
        # Create a b2 project for the package dependency.
        return [self.conanbuildinfo_project_template.format(name=name)]
    
    def b2_constants_for_dep(self, name, info, user=None):
        '''
        Generates a list of constant variable definitions for the information in the
        CppInfo conan data given for the package. If user variables map is also given
        those are also generated following the package variables.
        '''
        if not info:
            return []
        name = name.lower()

        # Define the info specific variables. Note that the 'usage-requirements' one
        # needs to be last as it references the others.
        result = \
            self.b2_constant(name, 'rootpath', [info.rootpath], True) + \
            self.b2_constant(name, 'includedirs', info.include_paths, True) + \
            self.b2_constant(name, 'libdirs', info.lib_paths, True) + \
            self.b2_constant(name, 'defines', info.defines) + \
            self.b2_constant(name, 'cppflags', info.cppflags) + \
            self.b2_constant(name, 'cflags', info.cflags) + \
            self.b2_constant(name, 'sharedlinkflags', info.sharedlinkflags) + \
            self.b2_constant(name, 'exelinkflags', info.exelinkflags) + \
            self.b2_constant(name, 'requirements', self.b2_features(self.b2_variation)) + \
            self.b2_constant(name, 'usage-requirements', [
                '<include>$(includedirs({name},{variation}))'.format(name=name, variation=self.b2_variation_id),
                '<define>$(defines({name},{variation}))'.format(name=name, variation=self.b2_variation_id),
                '<cflags>$(cflags({name},{variation}))'.format(name=name, variation=self.b2_variation_id),
                '<cxxflags>$(cppflags({name},{variation}))'.format(name=name, variation=self.b2_variation_id),
                '<link>shared:<linkflags>$(sharedlinkflags({name},{variation}))'.format(name=name, variation=self.b2_variation_id)
                ])

        if user:
            for uk, uv in user.vars.items():
                result += self.b2_constant(uk.lower() + ',' + name, 'user', [uv])

        return result

    def b2_targets_for_dep(self, name, info):
        '''
        Generates individual targets for the libraries in a package and a single "libs"
        collective alias target that refers to them.
        '''
        if not info:
            return []
        name = name.lower()
        result = []
        if info.libs:
            for lib in info.libs:
                result += [self.conanbuildinfo_variation_lib_template.format(
                    name=name, lib=lib, variation=self.b2_variation_id)]
            result += [self.conanbuildinfo_variation_alias_template.format(
                name=name, libs=" ".join(info.libs), variation=self.b2_variation_id)]
        else:
            result += [self.conanbuildinfo_variation_alias_template.format(
                name=name, libs="", variation=self.b2_variation_id)]

        return result

    def b2_constant(self, name, var, val, is_paths=False):
        '''
        Generates a constant definition for the given variable and value(s). If is_path
        is True the value(s) are reformated to be acceptable to b2.
        '''
        if not val:
            return []
        if is_paths:
            val = list(self.b2_path(p) for p in val)
        value = []
        for v in val:
            if v.startswith('<'):
                value += ['    {val}'.format(val=v)]
            else:
                value += ['    "{val}"'.format(val=v)]
        return [self.conanbuildinfo_variation_constant_template.format(
            name=name, var=var, variation=self.b2_variation_id, value="\n".join(value)
        )]

    def b2_path(self, p):
        '''
        Adjust a ragular path to the form b2 can use in source code.
        '''
        return p.replace('\\', '/')

    def b2_features(self, m):
        '''
        Generated a b2 requirements list, i.e. <name>value list, from the given
        map of key-values.
        '''
        result = []
        for k, v in sorted(m.items()):
            if v:
                result += ['<%s>%s' % (k, v)]
        return result

    @property
    def conanbuildinfo_variation_jam(self):
        return 'conanbuildinfo-%s.jam'%(self.b2_variation_key)

    _b2_variation_key = None

    @property
    def b2_variation_key(self):
        '''
        A hashed key of the variation to use a UID for the variation.
        '''
        if not self._b2_variation_key:
            self._b2_variation_key = md5(self.b2_variation_id.encode('utf-8')).hexdigest()
        return self._b2_variation_key

    _b2_variation_id = None

    @property
    def b2_variation_id(self):
        '''
        A compact single comma separated list of the variation where only the values
        of the b2 variation are included in sorted by feature name order.
        '''
        if not self._b2_variation_id:
            vid = []
            for k in sorted(self.b2_variation.keys()):
                if self.b2_variation[k]:
                    vid += [self.b2_variation[k]]
            self._b2_variation_id = ",".join(vid)
        return self._b2_variation_id

    @property
    def b2_variation(self):
        '''
        Returns a map of b2 features & values as translated from conan settings that
        can affect the link compatibility of libraries.
        '''
        if not getattr(self, "_b2_variation_key", None):
            self._b2_variation = {}
            self._b2_variation['toolset'] = {
                'sun-cc': 'sun',
                'gcc': 'gcc',
                'Visual Studio': 'msvc',
                'clang': 'clang',
                'apple-clang': 'clang'
            }.get(self.conanfile.settings.get_safe('compiler'))+'-'+self.b2_toolset_version
            self._b2_variation['architecture'] = {
                'x86': 'x86', 'x86_64': 'x86',
                'ppc64le': 'power', 'ppc64': 'power',
                'armv6': 'arm', 'armv7': 'arm', 'armv7hf': 'arm', 'armv8': 'arm',
                'armv7s': 'arm', 'armv7k': 'arm',
                'sparc': 'sparc', 'sparcv9': 'sparc',
                'mips': 'mips1', 'mips64': 'mips64',
            }.get(self.conanfile.settings.get_safe('arch'))
            self._b2_variation['instruction-set'] = {
                'armv6': 'armv6', 'armv7': 'armv7', 'armv7hf': None, 'armv7k': None,
                'armv7s': 'armv7s', 'armv8': None, 'avr': None,
                'mips': None, 'mips64': None,
                'ppc64le': None, 'ppc64': 'powerpc64',
                'sparc': None, 'sparcv9': 'v9',
                'x86': None, 'x86_64': None,
            }.get(self.conanfile.settings.get_safe('arch'))
            self._b2_variation['address-model'] = {
                'x86': '32', 'x86_64': '64',
                'ppc64le': '64', 'ppc64': '64',
                'armv6': '32', 'armv7': '32', 'armv7hf': '32', 'armv8': '64',
                'armv7s': '32', 'armv7k': '32',
                'sparc': '32', 'sparcv9': '64',
                'mips': '32', 'mips64': '64',
            }.get(self.conanfile.settings.get_safe('arch'))
            self._b2_variation['target-os'] = {
                'Windows': 'windows', 'WindowsStore': 'windows',
                'Linux': 'linux',
                'Macos': 'darwin',
                'Android': 'android',
                'iOS': 'darwin', 'watchOS': 'darwin', 'tvOS': 'darwin',
                'FreeBSD': 'freebsd',
                'SunOS': 'solaris',
                'Arduino': 'linux',
            }.get(self.conanfile.settings.get_safe('os'))
            self._b2_variation['variant'] = {
                'Debug': 'debug',
                'Release': 'release',
                'RelWithDebInfo': 'relwithdebinfo',
                'MinSizeRel': 'minsizerel',
            }.get(self.conanfile.settings.get_safe('build_type'))
            self._b2_variation['cxxstd'] = {
                '98': '98', 'gnu98': '98',
                '11': '11', 'gnu11': '11',
                '14': '14', 'gnu14': '14',
                '17': '17', 'gnu17': '17',
                '2a': '2a', 'gnu2a': '2a',
                '2b': '2b', 'gnu2b': '2b',
                '2c': '2c', 'gnu2c': '2c',
            }.get(self.conanfile.settings.get_safe('cppstd'))
            self._b2_variation['cxxstd:dialect'] = {
                '98': None, 'gnu98': 'gnu',
                '11': None, 'gnu11': 'gnu',
                '14': None, 'gnu14': 'gnu',
                '17': None, 'gnu17': 'gnu',
                '2a': None, 'gnu2a': 'gnu',
                '2b': None, 'gnu2b': 'gnu',
                '2c': None, 'gnu2c': 'gnu',
            }.get(self.conanfile.settings.get_safe('cppstd'))
        return self._b2_variation
    
    @property
    def b2_toolset_version(self):
        if self.conanfile.settings.compiler == 'Visual Studio':
            if self.conanfile.settings.compiler.version == '15':
                return '14.1'
            else:
                return str(self.conanfile.settings.compiler.version)+'.0'
        return str(self.conanfile.settings.compiler.version)

    conanbuildinfo_header_text = '''\
#|
    B2 definitions for Conan packages. This is a generated file.
    Edit the corresponding conanfile.txt instead.
|#
'''

    conanbuildinfo_prefix_text = '''\
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
'''

    conanbuildinfo_project_template = '''\
# {name}
project-define {name} ;
'''

    conanbuildinfo_postfix_text = '''\
{
    local __define_targets__ = yes ;
    for local __cbi__ in $(__conanbuildinfo__)
    {
        call-in-project : include-conanbuildinfo $(__cbi__) ;
    }
}
'''

    conanbuildinfo_variation_constant_template = '''\
constant-if {var}({name},{variation}) :
{value}
    ;
'''

    conanbuildinfo_variation_lib_template = '''\
if $(__define_targets__) {{
    call-in-project $({name}-mod) : lib {lib}
        :
        : <name>{lib} <search>$(libdirs({name},{variation})) $(requirements({name},{variation}))
        :
        : $(usage-requirements({name},{variation})) ;
    call-in-project $({name}-mod) : explicit {lib} ; }}
'''

    conanbuildinfo_variation_alias_template = '''\
if $(__define_targets__) {{
    call-in-project $({name}-mod) : alias libs
        : {libs}
        : $(requirements({name},{variation}))
        :
        : $(usage-requirements({name},{variation})) ;
    call-in-project $({name}-mod) : explicit libs ; }}
'''
