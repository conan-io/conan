import collections.abc
import os
import textwrap

from jinja2 import Template

from conan.tools.apple.apple import (
    is_apple_os,
    XCRun,
)
from conan.tools.b2 import utils as b2_utils
from conan.tools.env import VirtualBuildEnv
from conans.util.files import save


class B2Toolchain(object):
    """
    B2Toolchain generator
    """

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile
        self._variation = b2_utils.variation(self._conanfile)
        self._xc_run =None
        self._toolsets = {}

        self._install_prefix = self._conanfile.package_folder
        if self._install_prefix:
            self._install_bindir = self._get_package_dir('bindirs')
            self._install_libdir = self._get_package_dir("libdirs")
            self._install_includedir = self._get_package_dir("includedirs")
            self._install_datarootdir = self._get_package_dir("resdirs")
        else:
            self._install_bindir = None
            self._install_libdir = None
            self._install_includedir = None
            self._install_datarootdir = None

        self._init_toolset()

    @property
    def variation(self):
        return self._variation

    def generate(self):
        """
        Creates a ``project-config.jam`` and ``conan-config-XXX.jam`` with the
        proper content.
        """

        for filename, content in self._content.items():
            path = os.path.join(self._conanfile.generators_folder, filename)
            save(path, content)

    def using(self, name, *args):
        '''
        Register or update initialization of a toolset module.

        :param name: name of the module or name-version pair;
        :param args: arguments for module initialization ;
        '''

        self._toolsets[name] = args

    @property
    def _content(self):
        variation_id = b2_utils.variation_id(self.variation)
        variation_key = b2_utils.variation_key(variation_id)
        context = {
            'variation_key': variation_key,
            'default_build': b2_utils.properties(self._variation),
            'toolsets': self.toolsets,
            'install_prefix': self._install_prefix,
            'install_bindir': self._install_bindir,
            'install_libdir': self._install_libdir,
            'install_includedir': self._install_includedir,
            'install_datarootdir': self._install_datarootdir,
        }
        common_template = Template(_common_template, trim_blocks=True, lstrip_blocks=True)
        variation_template = Template(_variation_template, trim_blocks=True, lstrip_blocks=True)
        variation_config = 'conan-config-%s.jam' % variation_key
        return {
            'project-config.jam': common_template.render(
                variation_key=variation_key,
                folder=self._conanfile.generators_folder,
            ),
            variation_config: variation_template.render(**context),
        }

    @property
    def toolsets(self):
        '''
        Dumps each toolset module configuraions into a multiline string usable
        as a part of b2 configuration file.
        For example, if a module was registerd via
        `self.using(("a", "b"), "c", "d", e="f")`, then result will contain
        the line `using a : b : c : d : <e>"f" ;`
        '''

        for k, v in self._toolsets.items():
            if isinstance(k, tuple):
                items = list(k)
            else:
                items = [k]
            items += [ self._toolset_param(param) for param in v ]
            items = [ x if x is not None else "" for x in items ]
            yield items

    def _toolset_param(self, param):
        if isinstance(param, collections.abc.Mapping):
            param = [
                self._mapping_item(k, v)
                for k, v in sorted(param.items())
                if v
            ]

        if (
            isinstance(param, collections.abc.Iterable)
            and not isinstance(param, str)
        ):
            param = ' '.join(param)

        return param

    def _mapping_item(self, key, value):
        key = b2_utils.jamify(key)
        pattern = '<{key}>"{value}"'
        if (
            isinstance(value, collections.abc.Iterable)
            and not isinstance(value, str)
        ):
            return ' '.join(
                (pattern.format(key=key, value=v) for v in value if v)
            )
        else:
            return pattern.format(key=key, value=value)

    def _get_package_dir(self, name):
        elements = getattr(self._conanfile.cpp.package, name)
        if elements:
            return os.path.join(self._install_prefix, elements[0])

    def _init_toolset(self):
        toolset = self.variation.get('toolset')
        if not toolset:
            return

        toolset = toolset.split('-')
        if len(toolset) > 1:
            toolset = ('-'.join(toolset[:-1]), toolset[-1])
        else:
            toolset = (toolset[0], None)

        build_env = VirtualBuildEnv(self._conanfile).vars()

        compilers_by_conf = self._conanfile.conf.get(
            'tools.build:compiler_executables',
            default={},
            check_type=dict)

        def get_tool(var, apple_tool=None):
            result = build_env.get(var)
            if not result and apple_tool:
                result = self._get_apple_tool(var.lower())
            return result

        def get_flags(var, conf=None):
            result = [f for f in build_env.get(var, "").split(" ") if f]
            if conf:
                result += self._conanfile.conf.get(
                    f'tools.build:{conf}', default=[], check_type=list)
            return result

        def get_compiler(var, comp):
            return compilers_by_conf.get(comp) or build_env.get(var)

        opts = {}

        archiver = get_tool('AR')
        if archiver:
            opts['archiver'] = archiver

        ranlib = get_tool('RANLIB')
        if ranlib:
            opts['ranlib'] = ranlib

        strip = get_tool('STRIP')
        if strip:
            opts['striper'] = strip

        cxxflags = get_flags('CXXFLAGS', 'cxxflags')
        if cxxflags:
            opts['cxxflags'] = cxxflags

        cflags = get_flags('CFLAGS', 'cflags')
        if cflags:
            opts['cflags'] = cflags

        compileflags = get_flags('CPPLAGS')
        if compileflags:
            opts['compileflags'] = compileflags

        linkflags = get_flags('LDFLAGS', 'sharedlinkflags')
        if linkflags:
            opts['linkflags'] = linkflags

        arflags = get_flags('ARFLAGS')
        if arflags:
            opts['arflags'] = arflags

        asmflags = get_flags('ASMFLAGS')
        if asmflags:
            opts['asmflags'] = asmflags

        rc = get_compiler('RC', 'rc')
        if rc:
            key = 'resource-compiler' if toolset[0] == 'msvc' else 'rc'
            opts[key] = rc

        assembler = get_compiler('AS', 'asm')
        if assembler:
            opts['assembler'] = assembler

        command = get_compiler('CXX', 'cpp') or get_compiler('CC', 'c') or ''

        property_set = dict()
        property_set.update(self._variation)
        del property_set['toolset']
        self.using(toolset, command, opts, property_set)

    def _get_apple_tool(self, name):
        if self._xc_run is None:
          if (is_apple_os(self._conanfile)
              and self._conanfile.settings.compiler == "apple-clang"):
              self._xc_run = dict()
          else:
              self._xc_run = XCRun(self._conanfile)
        return getattr(self._xc_run, name)



_common_template = textwrap.dedent("""\
    # Conan automatically generated config file
    # DO NOT EDIT MANUALLY, it will be overwritten

    import path ;

    local location = [ path.make {{ folder }} ] ;
    location = [ path.relative $(location) [ path.pwd ] ] ;
    for local pc in [ GLOB $(location) : conan-config-*.jam : downcase ] {
        local __define_project__ ;
        if $(pc) = $(location)/conan-config-{{variation_key}}.jam {
            __define_project__ = yes ;
        }
        include $(pc) ;
    }

    use-packages $(location)/conanbuildinfo.jam ;

""")

_variation_template = textwrap.dedent("""\
    # Conan automatically generated config file
    # DO NOT EDIT MANUALLY, it will be overwritten

    {% for toolset in toolsets %}
    using {{ toolset | join(" : ") }} ;
    {% endfor %}

    if $(__define_project__) = yes {
        project
            : default-build
            {% for property in default_build %}
              {{ property }}
            {% endfor %}
            ;
        import option ;
        {% if install_prefix %}
        option.set prefix : {{ install_prefix }} ;
        {% endif %}
        {% if install_bindir %}
        option.set bindir : {{ install_bindir }} ;
        {% endif %}
        {% if install_libdir %}
        option.set libdir : {{ install_libdir }} ;
        {% endif %}
        {% if install_includedir %}
        option.set includedir : {{ install_includedir }} ;
        {% endif %}
        {% if install_datarootdir %}
        option.set datarootdir : {{ install_datarootdir }} ;
        {% endif %}
    }

""")
