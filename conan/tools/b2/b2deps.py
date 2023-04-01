from conan.internal import check_duplicated_generator
from conan.tools.b2.util import *
from conans.errors import ConanException
from conans.util.files import save, chdir
from conans.paths import get_conan_user_home
from hashlib import md5


class B2Deps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self._conanhome = get_conan_user_home()

    def generate(self):
        """
        This method will save the generated files to the conanfile.generators_folder
        """
        source_folder = self._conanfile.source_folder
        self._conanfile.output.highlight(f"Writing B2Deps to {source_folder}")
        with chdir(source_folder):
            check_duplicated_generator(self, self._conanfile)
            generator_files = self.content
            for generator_file, content in generator_files.items():
                save(generator_file, content)

    @property
    def content(self):
        """
        Generates two content files: conanbuildinfo.jam and
        conanbuildinfo-ID.jam which the former defines sub-projects for each
        package and loads the other files and the latter define variables and
        targets for the packages.
        """
        self._content = {}
        self._content_conanbuildinfo_jam()
        self._content_conanbuildinfo_variation_jam()
        for ck in self._content.keys():
            self._content[ck] = self._conanbuildinfo_header_text+"\n"+self._content[ck]
        return self._content

    def _content_conanbuildinfo_jam(self):
        # Generate the common conanbuildinfo.jam which does four things:
        #
        # Defines common utility functions to make the rest of the code short
        # and includes the conanbuildinfo-*.jam sub-files.
        cbi = [self._conanbuildinfo_common_text]
        # The combined text.
        self._content['conanbuildinfo.jam'] = "\n".join(cbi)

    def _content_conanbuildinfo_variation_jam(self):
        # Generate the current build variation conanbuildinfo-/variation/.jam.
        for require, dependency in self._conanfile.dependencies.items():
            # Only generate defs for direct dependencies.
            if not require.direct:
                continue
            # The base name of the dependency.
            dep_name = dependency.ref.name
            # B2 equivalent of the dependency name. We keep all names lower case.
            dep_name_b2 = dep_name.lower()
            # The dependency cpp_info. We need to consider that there's a
            # "_depname" component. Such components are a kludge to appease
            # cmake generators and will eventually go away. This special
            # component holds the real root definitions of the dependency.
            dep_cpp_info = dependency.cpp_info
            if '_'+dep_name in dep_cpp_info.components:
                dep_cpp_info = dep_cpp_info.components['_'+dep_name]
            # The settings the dependency requires, i.e. finds relevant.
            dep_settings = dependency.settings
            # The variant specific file to add this dependency to.
            dep_variant_jam = B2Deps._conanbuildinfo_variation_jam(dep_settings)
            if not dep_variant_jam in self._content:
                self._content[dep_variant_jam] = ""
            # Declare/define the local project for the dependency.
            cbiv = [
                f'# {dependency.pref}',
                f'pkg-project {dep_name_b2} ;']
            # Declare any system libs that we refer to (in usage requirements).
            system_libs = set(dependency.cpp_info.system_libs)
            for name, component in dependency.cpp_info.get_sorted_components().items():
                system_libs |= set(component.system_libs)
            cbiv += self._content_conanbuildinfo_variation_declare_syslibs(
                dep_name_b2, system_libs, settings=dep_settings)
            # Declare any package libs for usage requirements. The first one is
            # the main/global dependency.
            cbiv += self._content_conanbuildinfo_variation_declare_libs(
                dep_name_b2, dep_cpp_info, settings=dep_settings)
            # Followed by any components of the dependency. But skipping the
            # special _depname component. As that is already declare as the
            # main/global lib.
            for name, component in dependency.cpp_info.get_sorted_components().items():
                if name.lower() == '_'+dep_name_b2:
                    continue
                cbiv += self._content_conanbuildinfo_variation_declare_libs(
                    dep_name_b2, component, settings=dep_settings)
            # Declare the main target of the dependency. This is an alias that
            # refers to all the previous targets and adds all the defines,
            # flags, etc for consumers.
            cbiv += self._content_conanbuildinfo_variation_declare_target(
                dep_name_b2, dep_name_b2,
                dep_cpp_info,
                settings=dep_settings)
            # Similarly declare the component targets, if any.
            for name, component in dependency.cpp_info.get_sorted_components().items():
                # Again, always skipping the kludge component as it's already
                # defined.
                if "_"+dep_name_b2 == name.lower():
                    continue
                cbiv += self._content_conanbuildinfo_variation_declare_target(
                    dep_name_b2, name.lower(), component, settings=dep_settings)
            # Add the combined text.
            self._content[dep_variant_jam] += "\n".join(cbiv)+"\n"

    def _content_conanbuildinfo_variation_declare_libs(self, name, cpp_info, settings=None):
        name = name.lower()
        cbi_libs = []
        variation = ' '.join(b2_features(B2Deps._b2_variation(settings)))
        for lib in cpp_info.libs:
            search = ' '.join(
                [f'<search>"{b2_path(d.replace(self._conanhome, "$(CONAN_HOME)"))}"' for d in cpp_info.libdirs+cpp_info.bindirs])
            # The lib targets are prefixed with "lib." to distinguish them
            # from dependency main targets as it's often the case that the
            # dependency has the same name as the library consumers link to.
            cbi_libs += [
                f'pkg-lib {name}//lib.{lib} : : <name>{lib}',
                f'  {variation}',
                f'  {search} ;']
        return cbi_libs

    def _content_conanbuildinfo_variation_declare_syslibs(self, name, systemlibs, settings=None):
        name = name.lower()
        cbi_libs = []
        variation = ' '.join(b2_features(self._b2_variation(settings)))
        for lib in systemlibs:
            # Although system libs won't collide in the names. We still prefix
            # the target names with "lib." for consistency and easier reference
            # in the main targets.
            cbi_libs += [
                f'pkg-lib {name}//lib.{lib} : : <name>{lib}',
                f'  {variation} ;']
        return cbi_libs

    def _content_conanbuildinfo_variation_declare_target(self, name, target, cpp_info, settings=None):
        cbi_target = []
        # Target, no sources. The empty target is to catch incompatible build
        # requirements matches by falling back to an unbuildable result.
        cbi_target += [
            f'pkg-alias {name}//{target} : : <build>no ;',
            f'pkg-alias {name}//{target} : :']
        # Requirements:
        cbi_target += [
            f'  {" ".join(b2_features(self._b2_variation(settings)))}']
        cbi_target += [
            f'  <source>lib.{l}' for l in cpp_info.libs+cpp_info.system_libs]
        # No default-build:
        cbi_target += ["  : :"]
        # Usage-requirements:
        cbi_target += [
            f'  <include>"{b2_path(d.replace(self._conanhome, "$(CONAN_HOME)"))}"' for d in cpp_info.includedirs]
        cbi_target += [f'  <define>"{d}"' for d in cpp_info.defines]
        cbi_target += [f'  <cflags>"{f}"' for f in cpp_info.cflags]
        cbi_target += [f'  <cxxflags>"{f}"' for f in cpp_info.cxxflags]
        cbi_target += [
            f'  <main-target-type>SHARED_LIB:<linkflags>"{f}"' for f in cpp_info.sharedlinkflags]
        cbi_target += [f'  <main-target-type>EXE:<linkflags>"{f}"' for f in cpp_info.exelinkflags]
        cbi_target += ["  ;"]
        return cbi_target

    @staticmethod
    def _conanbuildinfo_variation_jam(settings):
        return 'conanbuildinfo-%s.jam' % B2Deps._b2_variation_key(settings)

    @staticmethod
    def _b2_variation_key(settings):
        """
        A hashed key of the variation to use a UID for the variation.
        """
        return md5(B2Deps._b2_variation_id(settings).encode('utf-8')).hexdigest()

    @staticmethod
    def _b2_variation_id(settings):
        """
        A compact single comma separated list of the variation where only the
        values of the b2 variation are included in sorted by feature name order.
        """
        vid = []
        b2_variation = B2Deps._b2_variation(settings)
        for k in sorted(b2_variation.keys()):
            if b2_variation[k]:
                vid += [b2_variation[k]]
        return ",".join(vid)

    @staticmethod
    def _setting(settings, name, default=None, optional=True):
        result = settings.get_safe(name, default) if settings else None
        if not result and not optional:
            raise ConanException(
                "B2Deps needs 'settings.{}', but it is not defined.".format(name))
        return result

    @staticmethod
    def _b2_variation(settings):
        """
        Returns a map of b2 features & values as translated from conan settings
        that can affect the link compatibility of libraries.
        """
        _b2_variation_v = {
            'toolset': b2_toolset(
                B2Deps._setting(settings, "compiler"),
                B2Deps._setting(settings, "compiler.version")),
            'architecture': b2_architecture(
                B2Deps._setting(settings, "arch")),
            'instruction-set': b2_instruction_set(
                B2Deps._setting(settings, "arch")),
            'address-model': b2_address_model(
                B2Deps._setting(settings, "arch")),
            'target-os': b2_os(
                B2Deps._setting(settings, "os")),
            'variant': b2_variant(
                B2Deps._setting(settings, "build_type")),
            'cxxstd': b2_cxxstd(
                B2Deps._setting(settings, "cppstd")),
            'cxxstd:dialect': b2_cxxstd_dialect(
                B2Deps._setting(settings, "cppstd")),
        }
        return _b2_variation_v

    _conanbuildinfo_header_text = """\
#|
    B2 definitions for Conan packages. This is a generated file.
    Edit the corresponding conanfile.txt/py instead.
|#
"""

    _conanbuildinfo_common_text = """\
import path ;
import project ;
import modules ;
import feature ;
import os ;

rule pkg-project ( id )
{
    local id-mod = [ project.find $(id:L) : . ] ;
    if ! $(id-mode)
    {
        local parent-prj = [ project.current ] ;
        local parent-mod = [ $(parent-prj).project-module ] ;
        local id-location = [ path.join
            [ project.attribute $(parent-mod) location ]
            $(id:L) ] ;
        id-mod = [ project.load $(id-location) : synthesize ] ;
        project.push-current [ project.current ] ;
        project.initialize $(id-mod) : $(id-location) ;
        project.pop-current ;
        project.inherit-attributes $(id-mod) : $(parent-mod) ;
        local attributes = [ project.attributes $(id-mod) ] ;
        $(attributes).set parent-module : $(parent-mod) : exact ;
        if [ project.is-jamroot-module $(parent-mod) ]
        {
            use-project /$(id:L) : $(id:L) ;
        }
    }
    return $(id-mod) ;
}

rule pkg-target ( target : sources * : requirements * : default-build * : usage-requirements * )
{
    target = [ MATCH "(.*)//(.*)" : $(target) ] ;
    local id-mod = [ pkg-project $(target[1]) ] ;
    project.push-current [ project.target $(id-mod) ] ;
    local bt = [ BACKTRACE 1 ] ;
    local rulename = [ MATCH "pkg-(.*)" : $(bt[4]) ] ;
    modules.call-in $(id-mod) :
        $(rulename) $(target[2]) : $(sources) : $(requirements) : $(default-build)
            : $(usage-requirements) ;
    project.pop-current ;
}

IMPORT $(__name__) : pkg-target : $(__name__) : pkg-alias ;
IMPORT $(__name__) : pkg-target : $(__name__) : pkg-lib ;

rule conan-home ( )
{
    local conan_home = [ os.environ CONAN_HOME ] ;
    if ! $(conan_home)
    {
        local conanrc = [ path.glob-in-parents [ path.join [ path.pwd ] "_" ] : ".conanrc" ] ;
        if $(conanrc)
        {
            local conanrc_file = [ FILE_OPEN [ path.native $(conanrc) ] : t ] ;
            conan_home = [ MATCH "^conan_home=(.*)
" ^conan_home=(.*) : $(conanrc_file) ] ;
            conan_home = [ path.make $(conan_home[1]) ] ;
            if [ MATCH ^(~/) : $(conan_home) ]
            {
                local home = [ os.home-directories ] ;
                conan_home = [ path.join [ path.make $(home[1]) ] [ MATCH "^~/(.*)" : $(conan_home) ] ] ;
            }
            else if ! [ path.is-rooted $(conan_home) ]
            {
                conan_home = [ path.root $(conan_home) $(conanrc:D) ] ;
            }
        }
    }
    if ! $(conan_home)
    {
        local home = [ os.home-directories ] ;
        conan_home = [ path.join [ path.make $(home[1]) ] .conan2 ] ;
    }
    return $(conan_home) ;
}

path-constant CONAN_HOME : [ conan-home ] ;

if ! ( relwithdebinfo in [ feature.values variant ] )
{
    variant relwithdebinfo : : <optimization>speed <debug-symbols>on <inlining>full <runtime-debugging>off ;
}
if ! ( minsizerel in [ feature.values variant ] )
{
    variant minsizerel : : <optimization>space <debug-symbols>off <inlining>full <runtime-debugging>off ;
}

for local __cbi__ in [ GLOB $(__file__:D) : conanbuildinfo-*.jam ]
{
    include $(__cbi__) ;
}
"""
