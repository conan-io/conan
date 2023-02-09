from conan.api.output import ConanOutput
from conans.errors import ConanException
from conans.model.recipe_ref import ref_matches


class BuildMode:
    """ build_mode => ["*"] if user wrote "--build"
                   => ["hello*", "bye*"] if user wrote "--build hello --build bye"
                   => ["hello/0.1@foo/bar"] if user wrote "--build hello/0.1@foo/bar"
                   => False if user wrote "never"
                   => True if user wrote "missing"
                   => ["!foo"] means exclude when building all from sources
    """
    def __init__(self, params):
        self.missing = False
        self.never = False
        self.cascade = False
        self.editable = False
        self.patterns = []
        self.build_missing_patterns = []
        self._unused_patterns = []
        self._excluded_patterns = []
        self.all = False
        if params is None:
            return

        assert isinstance(params, list)
        if len(params) == 0:
            self.all = True
        else:
            for param in params:
                if param == "missing":
                    self.missing = True
                elif param == "editable":
                    self.editable = True
                elif param == "never":
                    self.never = True
                elif param == "cascade":
                    self.cascade = True
                else:
                    if param.startswith("missing:"):
                        clean_pattern = param[len("missing:"):]
                        clean_pattern = clean_pattern[:-1] if param.endswith("@") else clean_pattern
                        clean_pattern = clean_pattern.replace("@#", "#")
                        self.build_missing_patterns.append(clean_pattern)
                    else:
                        # Remove the @ at the end, to match for
                        # "conan install --requires=pkg/0.1@ --build=pkg/0.1@"
                        clean_pattern = param[:-1] if param.endswith("@") else param
                        clean_pattern = clean_pattern.replace("@#", "#")
                        if clean_pattern and clean_pattern[0] == "!":
                            self._excluded_patterns.append(clean_pattern[1:])
                        else:
                            self.patterns.append(clean_pattern)

            if self.never and (self.missing or self.patterns or self.cascade):
                raise ConanException("--build=never not compatible with other options")
        self._unused_patterns = list(self.patterns) + self._excluded_patterns

    def forced(self, conan_file, ref, with_deps_to_build=False):
        # TODO: ref can be obtained from conan_file

        for pattern in self._excluded_patterns:
            if ref_matches(ref, pattern, is_consumer=conan_file._conan_is_consumer):
                try:
                    self._unused_patterns.remove(pattern)
                except ValueError:
                    pass
                conan_file.output.info("Excluded build from source")
                return False

        if conan_file.build_policy == "never":  # this package has been export-pkg
            return False

        if self.never:
            return False
        if self.all:
            return True

        if conan_file.build_policy == "always":
            raise ConanException("{}: build_policy='always' has been removed. "
                                 "Please use 'missing' only".format(conan_file))

        if self.cascade and with_deps_to_build:
            return True

        # Patterns to match, if package matches pattern, build is forced
        for pattern in self.patterns:
            if ref_matches(ref, pattern, is_consumer=conan_file._conan_is_consumer):
                try:
                    self._unused_patterns.remove(pattern)
                except ValueError:
                    pass
                return True
        return False

    def allowed(self, conan_file):
        if self.never or conan_file.build_policy == "never":  # this package has been export-pkg
            return False
        if self.missing:
            return True
        if conan_file.build_policy == "missing":
            conan_file.output.info("Building package from source as defined by "
                                   "build_policy='missing'")
            return True
        if self.should_build_missing(conan_file):
            return True
        return False

    def should_build_missing(self, conanfile):
        for pattern in self.build_missing_patterns:
            if ref_matches(conanfile.ref, pattern, is_consumer=False):
                return True

    def report_matches(self):
        for pattern in self._unused_patterns:
            ConanOutput().error("No package matching '%s' pattern found." % pattern)
