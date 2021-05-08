import textwrap
import collections.abc
import os
import six

from jinja2 import Template

from conans import tools
from conan.tools.b2 import utils as b2_utils
from conans.util.files import save


class B2Toolchain(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.variation = b2_utils.variation(self._conanfile)
        self.install_prefix = self._conanfile.package_folder
        if self.install_prefix:
            self.install_prefix = self.install_prefix.replace("\\", "/")
            self.install_bindir = self._get_package_dir("bindirs")
            self.install_libdir = self._get_package_dir("libdirs")
            self.install_includedir = self._get_package_dir("includedirs")
            self.install_datarootdir = self._get_package_dir("resdirs")
        else:
            self.install_bindir = None
            self.install_libdir = None
            self.install_includedir = None
            self.install_datarootdir = None

        self._toolsets = {}
        self._init_toolset()

    @property
    def filename(self):
        pass

    @property
    def content(self):
        variation_id = b2_utils.variation_id(self.variation)
        variation_key = b2_utils.variation_key(variation_id)
        context = {
            'variation_key': variation_key,
            'default_build': b2_utils.properties(self.variation),
            'toolsets': self.toolsets,
            'install_prefix': self.install_prefix,
            'install_bindir': self.install_bindir,
            'install_libdir': self.install_libdir,
            'install_includedir': self.install_includedir,
            'install_datarootdir': self.install_datarootdir,
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

    def generate(self):
        for filename, content in self.content.items():
            path = os.path.join(self._conanfile.generators_folder, filename)
            save(path, content)

    def using(self, name, *args, **kw):
        '''
        Register or update initialization of a toolset module.

        :param name: name of the module or name-version pair;
        :param args: positional arguments to module initialization ;
        :param kw: options for module initialization ;
        '''

        self._toolsets[name] = (args, kw)

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
                items = [k, None]
            items += v[0]
            if v[1]:
                opts = (
                    self._dump_toolset_param(k, v)
                    for k, v in sorted(v[1].items())
                )
                items.append(' '.join(opts))
            yield items

    def _dump_toolset_param(self, param, value):
        param = b2_utils.jamify(param)
        pattern = '<{param}>"{value}"'
        if (
            not isinstance(value, six.string_types)
            and isinstance(value, collections.abc.Iterable)
        ):
            return " ".join(
                (pattern.format(param=param, value=str(v)) for v in value)
            )
        else:
            return pattern.format(param=param, value=str(value))

    def _get_package_dir(self, name):
        elements = getattr(self._conanfile.cpp.package, name)
        if elements:
            return os.path.join(self.install_prefix, elements[0])

    def _init_toolset(self):
        toolset = self.variation.get('toolset')
        if not toolset:
            return

        toolset = toolset.split('-')
        toolset = ('-'.join(toolset[:-1]), toolset[-1])

        command = tools.get_env('CXX') or tools.get_env('CC') or ''

        params = {}

        cxxflags = _get_flags('CXXFLAGS')
        cxxflags += _get_flags('CPPFLAGS')
        if cxxflags:
            params['cxxflags'] = cxxflags

        cflags = _get_flags('CFLAGS')
        if cflags:
            params['cflags'] = cflags

        ldflags = _get_flags('LDFLAGS')
        if ldflags:
            params['ldflags'] = ldflags

        archiver = tools.get_env('AR')
        if archiver:
            params['archiver'] = archiver

        ldflags = _get_flags('ARFLAGS')
        if ldflags:
            params['ldflags'] = ldflags

        assembler = tools.get_env('AS')
        if assembler:
            params['assembler'] = assembler

        ranlib = tools.get_env('RANLIB')
        if ranlib:
            params['ranlib'] = ranlib

        strip = tools.get_env('STRIP')
        if strip:
            params['striper'] = strip

        rc = tools.get_env('RC')
        if rc:
            key = 'resource-compiler' if toolset[0] == 'msvc' else 'rc'
            params[key] = rc

        self.using(toolset, command, **params)


def _get_flags(var):
    return [f for f in tools.get_env(var, "").split(" ") if f]


_common_template = textwrap.dedent("""\
    # Conan automatically generated config file
    # DO NOT EDIT MANUALLY, it will be overwritten

    import path ;

    local location = [ path.make {{ folder }} ] ;
    location = [ path.relative $(location) [ path.pwd ] ] ;
    for local pc in [ GLOB $(location) : project-config-*.jam : downcase ] {
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

    import feature ;
    local all-toolsets = [ feature.values toolset ] ;
    {% for toolset in toolsets %}
    {% if toolset[1] %}
    if ! {{ toolset[0] }} in $(all-toolsets) ||
       ! [ feature.is-subvalue toolset : {{ toolset[0] }} : version : {{ toolset[1] }} ]
    {% else %}
    if ! {{ toolset[0] }} in $(all-toolsets)
    {% endif %}
    { using {{ toolset | select('string') | join(" : ") }} ; }
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
