from conans.model.ref import ConanFileReference


class GenConanfile(object):
    """
    USAGE:

    x = GenConanfile().with_import("import os").\
        with_setting("os").\
        with_option("shared", [True, False]).\
        with_default_option("shared", True).\
        with_build_msg("holaaa").\
        with_build_msg("adiooos").\
        with_package_file("file.txt", "hola").\
        with_package_file("file2.txt", "hola")
    """

    def __init__(self, name=None, version=None):
        self._imports = ["from conans import ConanFile"]
        self._name = name
        self._version = version
        self._settings = []
        self._options = {}
        self._generators = []
        self._default_options = {}
        self._provides = []
        self._deprecated = None
        self._package_files = {}
        self._package_files_env = {}
        self._package_files_link = {}
        self._build_messages = []
        self._scm = {}
        self._requires = []
        self._requirements = []
        self._build_requires = []
        self._build_requirements = []
        self._revision_mode = None
        self._package_info = {}
        self._package_id_lines = []
        self._test_lines = []

    def with_name(self, name):
        self._name = name
        return self

    def with_version(self, version):
        self._version = version
        return self

    def with_provides(self, provides):
        self._provides.append(provides)
        return self

    def with_deprecated(self, deprecated):
        self._deprecated = deprecated
        return self

    def with_revision_mode(self, revision_mode):
        self._revision_mode = revision_mode
        return self

    def with_scm(self, scm):
        self._scm = scm
        return self

    def with_generator(self, generator):
        self._generators.append(generator)
        return self

    def with_require(self, ref, private=False, override=False):
        ref_str = ref.full_str() if isinstance(ref, ConanFileReference) else ref
        self._requires.append((ref_str, private, override))
        return self

    def with_requires(self, *refs):
        for ref in refs:
            self.with_require(ref)
        return self

    def with_requirement(self, ref, private=False, override=False):
        ref_str = ref.full_str() if isinstance(ref, ConanFileReference) else ref
        self._requirements.append((ref_str, private, override))
        return self

    def with_build_requires(self, *refs):
        for ref in refs:
            ref_str = ref.full_str() if isinstance(ref, ConanFileReference) else ref
            self._build_requires.append(ref_str)
        return self

    def with_build_requirement(self, ref, force_host_context=False):
        ref_str = ref.full_str() if isinstance(ref, ConanFileReference) else ref
        self._build_requirements.append((ref_str, force_host_context))
        return self

    def with_import(self, i):
        if i not in self._imports:
            self._imports.append(i)
        return self

    def with_setting(self, setting):
        self._settings.append(setting)
        return self

    def with_settings(self, *settings):
        self._settings.extend(settings)
        return self

    def with_option(self, option_name, values):
        self._options[option_name] = values
        return self

    def with_default_option(self, option_name, value):
        self._default_options[option_name] = value
        return self

    def with_package_file(self, file_name, contents=None, env_var=None, link=None):
        if not contents and not env_var:
            raise Exception("Specify contents or env_var")
        self.with_import("import os")
        self.with_import("from conans import tools")
        if contents:
            self._package_files[file_name] = contents
        if link:
            self._package_files_link[file_name] = link
        if env_var:
            self._package_files_env[file_name] = env_var
        return self

    def with_build_msg(self, msg):
        self._build_messages.append(msg)
        return self

    def with_package_info(self, cpp_info=None, env_info=None):
        assert isinstance(cpp_info, dict), "cpp_info ({}) expects dict".format(type(cpp_info))
        assert isinstance(env_info, dict), "env_info ({}) expects dict".format(type(env_info))
        if cpp_info:
            self._package_info["cpp_info"] = cpp_info
        if env_info:
            self._package_info["env_info"] = env_info
        return self

    def with_package_id(self, line):
        self._package_id_lines.append(line)
        return self

    def with_test(self, line):
        self._test_lines.append(line)
        return self

    @property
    def _name_line(self):
        if not self._name:
            return ""
        return "name = '{}'".format(self._name)

    @property
    def _version_line(self):
        if not self._version:
            return ""
        return "version = '{}'".format(self._version)

    @property
    def _provides_line(self):
        if not self._provides:
            return ""
        line = ", ".join('"{}"'.format(provide) for provide in self._provides)
        return "provides = {}".format(line)

    @property
    def _deprecated_line(self):
        if not self._deprecated:
            return ""
        return "deprecated = {}".format(self._deprecated)

    @property
    def _scm_line(self):
        if not self._scm:
            return ""
        line = ", ".join('"%s": "%s"' % (k, v) for k, v in self._scm.items())
        return "scm = {%s}" % line

    @property
    def _generators_line(self):
        if not self._generators:
            return ""
        line = ", ".join('"{}"'.format(generator) for generator in self._generators)
        return "generators = {}".format(line)

    @property
    def _revision_mode_line(self):
        if not self._revision_mode:
            return ""
        line = "revision_mode=\"{}\"".format(self._revision_mode)
        return line

    @property
    def _settings_line(self):
        if not self._settings:
            return ""
        line = ", ".join('"%s"' % s for s in self._settings)
        return "settings = {}".format(line)

    @property
    def _options_line(self):
        if not self._options:
            return ""
        line = ", ".join('"%s": %s' % (k, v) for k, v in self._options.items())
        tmp = "options = {%s}" % line
        return tmp

    @property
    def _default_options_line(self):
        if not self._default_options:
            return ""
        line = ", ".join('"%s": %s' % (k, v) for k, v in self._default_options.items())
        tmp = "default_options = {%s}" % line
        return tmp

    @property
    def _build_requirements_method(self):
        if not self._build_requirements:
            return ""

        lines = []
        for ref, force_host_context in self._build_requirements:
            force_host = ", force_host_context=True" if force_host_context else ""
            lines.append('        self.build_requires("{}"{})'.format(ref, force_host))
        return "def build_requirements(self):\n{}\n".format("\n".join(lines))

    @property
    def _build_requires_line(self):
        if not self._build_requires:
            return ""
        line = ", ".join(['"{}"'.format(r) for r in self._build_requires])
        tmp = "build_requires = %s" % line
        return tmp

    @property
    def _requires_line(self):
        if not self._requires:
            return ""
        items = []
        for ref, private, override in self._requires:
            if private or override:
                private_str = ", 'private'" if private else ""
                override_str = ", 'override'" if override else ""
                items.append('("{}"{}{})'.format(ref, private_str, override_str))
            else:
                items.append('"{}"'.format(ref))
        tmp = "requires = ({}, )".format(", ".join(items))
        return tmp

    @property
    def _requirements_method(self):
        if not self._requirements:
            return ""

        lines = []
        for ref, private, override in self._requirements:
            private_str = ", private=True" if private else ""
            override_str = ", override=True" if override else ""
            lines.append('        self.requires("{}"{}{})'.format(ref, private_str, override_str))

        return """
    def requirements(self):
{}
        """.format("\n".join(lines))

    @property
    def _package_method(self):
        lines = []
        if self._package_files:
            lines = ['        tools.save(os.path.join(self.package_folder, "{}"), "{}")'
                     ''.format(key, value)
                     for key, value in self._package_files.items()]

        if self._package_files_env:
            lines.extend(['        tools.save(os.path.join(self.package_folder, "{}"), '
                          'os.getenv("{}"))'.format(key, value)
                          for key, value in self._package_files_env.items()])
        if self._package_files_link:
            lines.extend(['        with tools.chdir(os.path.dirname('
                          'os.path.join(self.package_folder, "{}"))):\n'
                          '            os.symlink(os.path.basename("{}"), '
                          'os.path.join(self.package_folder, "{}"))'.format(key, key, value)
                          for key, value in self._package_files_link.items()])

        if not lines:
            return ""
        return """
    def package(self):
{}
    """.format("\n".join(lines))

    @property
    def _build_method(self):
        if not self._build_messages:
            return ""
        lines = ['        self.output.warn("{}")'.format(m) for m in self._build_messages]
        return """
    def build(self):
{}
    """.format("\n".join(lines))

    @property
    def _package_info_method(self):
        if not self._package_info:
            return ""
        lines = []
        if "cpp_info" in self._package_info:
            for k, v in self._package_info["cpp_info"].items():
                if k == "components":
                    for comp_name, comp in v.items():
                        for comp_attr_name, comp_attr_value in comp.items():
                            lines.append('        self.cpp_info.components["{}"].{} = {}'.format(
                                comp_name, comp_attr_name, str(comp_attr_value)))
                else:
                    lines.append('        self.cpp_info.{} = {}'.format(k, str(v)))
        if "env_info" in self._package_info:
            for k, v in self._package_info["env_info"].items():
                lines.append('        self.env_info.{} = {}'.format(k, str(v)))

        return """
    def package_info(self):
{}
        """.format("\n".join(lines))

    @property
    def _package_id_method(self):
        if not self._package_id_lines:
            return ""
        lines = ['        {}'.format(line) for line in self._package_id_lines]
        return """
    def package_id(self):
{}
        """.format("\n".join(lines))

    @property
    def _test_method(self):
        if not self._test_lines:
            return ""
        lines = ['', '    def test(self):'] + ['        %s' % m for m in self._test_lines]
        return "\n".join(lines)

    def __repr__(self):
        ret = []
        ret.extend(self._imports)
        ret.append("class HelloConan(ConanFile):")
        if self._name_line:
            ret.append("    {}".format(self._name_line))
        if self._version_line:
            ret.append("    {}".format(self._version_line))
        if self._provides_line:
            ret.append("    {}".format(self._provides_line))
        if self._deprecated_line:
            ret.append("    {}".format(self._deprecated_line))
        if self._generators_line:
            ret.append("    {}".format(self._generators_line))
        if self._requires_line:
            ret.append("    {}".format(self._requires_line))
        if self._build_requires_line:
            ret.append("    {}".format(self._build_requires_line))
        if self._requirements_method:
            ret.append("    {}".format(self._requirements_method))
        if self._build_requirements_method:
            ret.append("    {}".format(self._build_requirements_method))
        if self._scm:
            ret.append("    {}".format(self._scm_line))
        if self._revision_mode_line:
            ret.append("    {}".format(self._revision_mode_line))
        if self._settings_line:
            ret.append("    {}".format(self._settings_line))
        if self._options_line:
            ret.append("    {}".format(self._options_line))
        if self._default_options_line:
            ret.append("    {}".format(self._default_options_line))
        if self._build_method:
            ret.append("    {}".format(self._build_method))
        if self._package_method:
            ret.append("    {}".format(self._package_method))
        if self._package_info_method:
            ret.append("    {}".format(self._package_info_method))
        if self._package_id_lines:
            ret.append("    {}".format(self._package_id_method))
        if self._test_method:
            ret.append("    {}".format(self._test_method))
        if len(ret) == 2:
            ret.append("    pass")
        return "\n".join(ret)
