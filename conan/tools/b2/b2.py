
"""
B2 Conan Generator
This is a generator for conanbuildinfo.jam files declaring all conan dependencies
as B2 project and library targets. This generates multiple tagged build info
source files, each containing a single variant as specified by the user's
conan install profile in addition to the central generic one that includes
all possible variants.
"""

from conans.model import Generator
from conan.tools.b2 import utils as b2_utils


class B2Generator(Generator):
    _b2_variation_key = None
    _b2_variation_id = None

    @property
    def filename(self):
        pass  # in this case, filename defined in return value of content method

    @property
    def content(self):
        """
        Generates two content files: conanbuildinfo.jam and conanbuildinfo-ID.jam which
        the former defines sub-projects for each package and loads the other files and
        the latter define variables and targets for the packages.
        """
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
        cbiv += ["# global"]
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
        """
        Generates a sub-project definition to match the package. Which is used later
        to define targets for the package libs.
        """
        if info is None:
            return []
        name = name.lower()
        # Create a b2 project for the package dependency.
        return [self.conanbuildinfo_project_template.format(name=name)]

    def b2_constants_for_dep(self, name, info, user=None):
        """
        Generates a list of constant variable definitions for the information in the
        CppInfo conan data given for the package. If user variables map is also given
        those are also generated following the package variables.
        """
        if info is None:
            return []
        name = name.lower()

        # Define the info specific variables. Note that the 'usage-requirements' one
        # needs to be last as it references the others.
        # TODO: Should be cppflags -> cxxflags
        result = \
            self.b2_constant(name, 'rootpath', [info.rootpath], True) + \
            self.b2_constant(name, 'includedirs', info.include_paths, True) + \
            self.b2_constant(name, 'libdirs', info.lib_paths, True) + \
            self.b2_constant(name, 'defines', info.defines) + \
            self.b2_constant(name, 'cppflags', info.cxxflags) + \
            self.b2_constant(name, 'cflags', info.cflags) + \
            self.b2_constant(name, 'sharedlinkflags', info.sharedlinkflags) + \
            self.b2_constant(name, 'exelinkflags', info.exelinkflags) + \
            self.b2_constant(name, 'requirements', b2_utils.properties(self.b2_variation)) + \
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
        """
        Generates individual targets for the libraries in a package and a single "libs"
        collective alias target that refers to them.
        """
        if info is None:
            return []
        name = name.lower()
        result = []
        deps = ['/%s//libs' % dep for dep in info.public_deps]
        if info.libs:
            for lib in info.libs:
                result += [self.conanbuildinfo_variation_lib_template.format(
                    name=name, lib=lib, deps=" ".join(deps), variation=self.b2_variation_id)]
            deps.extend(info.libs)
        result += [self.conanbuildinfo_variation_alias_template.format(
            name=name, libs=" ".join(deps), variation=self.b2_variation_id)]

        return result

    def b2_constant(self, name, var, val, is_paths=False):
        """
        Generates a constant definition for the given variable and value(s). If is_path
        is True the value(s) are reformatted to be acceptable to b2.
        """
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

    @staticmethod
    def b2_path(path):
        """
        Adjust a regular path to the form b2 can use in source code.
        """
        return path.replace('\\', '/')

    @property
    def conanbuildinfo_variation_jam(self):
        return 'conanbuildinfo-%s.jam' % b2_utils.variation_key(self.b2_variation_id)

    @property
    def b2_variation_id(self):
        if not self._b2_variation_id:
            self._b2_variation_id = b2_utils.variation_id(self.b2_variation)
        return self._b2_variation_id

    @property
    def b2_variation(self):
        if not getattr(self, "_b2_variation", None):
            self._b2_variation = b2_utils.variation(self.conanfile)
        return self._b2_variation

    conanbuildinfo_header_text = """\
#|
    B2 definitions for Conan packages. This is a generated file.
    Edit the corresponding conanfile.txt instead.
|#
"""

    conanbuildinfo_prefix_text = """\
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
"""

    conanbuildinfo_project_template = """\

# {name}
project-define {name} ;
"""

    conanbuildinfo_postfix_text = """\
{
    local __define_targets__ = yes ;
    for local __cbi__ in $(__conanbuildinfo__)
    {
        call-in-project : include-conanbuildinfo $(__cbi__) ;
    }
}
"""

    conanbuildinfo_variation_constant_template = """\
constant-if {var}({name},{variation}) :
{value}
    ;
"""

    conanbuildinfo_variation_lib_template = """\
if $(__define_targets__) {{
    call-in-project $({name}-mod) : lib {lib}
        : {deps}
        : <name>{lib} <search>$(libdirs({name},{variation})) $(requirements({name},{variation}))
        :
        : $(usage-requirements({name},{variation})) ;
    call-in-project $({name}-mod) : explicit {lib} ; }}
"""

    conanbuildinfo_variation_alias_template = """\
if $(__define_targets__) {{
    call-in-project $({name}-mod) : alias libs
        : {libs}
        : $(requirements({name},{variation}))
        :
        : $(usage-requirements({name},{variation})) ;
    call-in-project $({name}-mod) : explicit libs ; }}
"""
