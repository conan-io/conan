import textwrap
# import collections.abc
import os
# import six

from jinja2 import Template
#
# from conans import tools
from conan.tools.b2 import utils as b2_utils
from conans.util.files import save


class B2Deps(object):
    def __init__(self, conanfile, generator=None):
        self._conanfile = conanfile

    @property
    def filename(self):
        pass

    @property
    def content(self):
        host_deps = self._conanfile.dependencies.host
        build_deps = self._conanfile.dependencies.direct_build
        test_deps = self._conanfile.dependencies.test

        result = {'conandeps.jam': _common_template}
        for require, dep in self._conanfile.dependencies.items():
            if (require.build or require.test) and not require.direct:
                continue
            result.update(**self._dependency_content(dep))
        return result

    def generate(self):
        for filename, content in self.content.items():
            path = os.path.join(self._conanfile.generators_folder, filename)
            save(path, content)

    def _dependency_content(self, dep):
        variation = b2_utils.variation(dep)
        variation_id = b2_utils.variation_id(variation)
        variation_key = b2_utils.variation_key(variation_id)

        context = {
            'package': dep,
            'project_name': b2_utils.jamify(dep.ref.name),
            'properties': b2_utils.properties(variation),
            'variation_id': variation_id,
        }
        template = Template(_dependency_template, trim_blocks=True, lstrip_blocks=True)
        file_name = 'conandep-%s-%s.jam' % (dep.ref.name, variation_key)
        return {file_name: template.render(**context)}


_common_template = textwrap.dedent("""\
    # Conan automatically generated file
    # DO NOT EDIT MANUALLY, it will be overwritten

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

    rule include-conandep ( cbi )
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

    local __conandeps__ = [ GLOB $(__file__:D) : conandep-*-*.jam : downcase ] ;
    {
        local __define_constants__ = yes ;
        for local __cdep__ in $(__conandeps__)
        {
            call-in-project : include-conandep $(__cdep__) ;
        }
    }

    {
        local __define_targets__ = yes ;
        for local __cdep__ in $(__conandeps__)
        {
            call-in-project : include-conandep $(__cdep__) ;
        }
    }

""")

_dependency_template = textwrap.dedent("""\
{% macro constant_name(constant) -%}
{{ constant }}({{ project_name }},{{ variation_id }})
{%- endmacro -%}

{% macro define_constant(constant, values, is_path=false) %}
    constant-if {{ constant_name(constant) }} :
    {% for value in values %}
        {% if is_path %}
        {% set value = value.replace("\\\\", "/") %}
        {% endif %}
        "{{ value | replace('"', '\"') }}"
    {% endfor %}
    ;
{% endmacro -%}

    # Conan automatically generated file
    # DO NOT EDIT MANUALLY, it will be overwritten

    # {{ package.ref }}
    {% set info = package.cpp_info %}
    {{ define_constant("rootpath", [package.package_folder], is_path=True) }}
    {{ define_constant("includedirs", info.includedirs, is_path=True) }}
    {{ define_constant("libdirs", info.libdirs, is_path=True) }}
    {{ define_constant("defines", info.defines) }}
    {{ define_constant("cppflags", info.cxxflags) }}
    {{ define_constant("cflags", info.cflags) }}
    {{ define_constant("sharedlinkflags", info.sharedlinkflags) }}
    {{ define_constant("exelinkflags", info.exelinkflags) }}
    {{ define_constant("requirements", properties) }}
    {{ define_constant("usage-requirements", [
        "<include>$(" ~ constant_name("includedirs") ~ ")",
        "<define>$(" ~ constant_name("defines") ~ ")",
        "<cflags>$(" ~ constant_name("cflags") ~ ")",
        "<cxxflags>$(" ~ constant_name("cppflags") ~ ")",
        "<link>shared:<linkflags>$(" ~ constant_name("sharedlinkflags") ~ ")",
    ]) }}

""")
