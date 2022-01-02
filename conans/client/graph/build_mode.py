import fnmatch

from conans.errors import ConanException


class BuildMode(object):
    """ build_mode => ["*"] if user wrote "--build"
                   => ["hello*", "bye*"] if user wrote "--build hello --build bye"
                   => ["hello/0.1@foo/bar"] if user wrote "--build hello/0.1@foo/bar"
                   => False if user wrote "never"
                   => True if user wrote "missing"
                   => "outdated" if user wrote "--build outdated"
                   => ["!foo"] means exclude when building all from sources
    """
    def __init__(self, params, output):
        self._out = output
        self.outdated = False
        self.missing = False
        self.never = False
        self.cascade = False
        self.patterns = []
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
                if param == "outdated":
                    self.outdated = True
                elif param == "missing":
                    self.missing = True
                elif param == "never":
                    self.never = True
                elif param == "cascade":
                    self.cascade = True
                else:
                    # Remove the @ at the end, to match for "conan install pkg/0.1@ --build=pkg/0.1@"
                    clean_pattern = param[:-1] if param.endswith("@") else param
                    clean_pattern = clean_pattern.replace("@#", "#")
                    if clean_pattern and clean_pattern[0] == "!":
                        self._excluded_patterns.append(clean_pattern[1:])
                    else:
                        self.patterns.append(clean_pattern)

            if self.never and (self.outdated or self.missing or self.patterns or self.cascade):
                raise ConanException("--build=never not compatible with other options")
        self._unused_patterns = list(self.patterns) + self._excluded_patterns

    def forced(self, conan_file, ref, with_deps_to_build=False):
        def pattern_match(pattern_):
            return (fnmatch.fnmatchcase(ref.name, pattern_) or
                    fnmatch.fnmatchcase(repr(ref.copy_clear_rev()), pattern_) or
                    fnmatch.fnmatchcase(repr(ref), pattern_))

        for pattern in self._excluded_patterns:
            if pattern_match(pattern):
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

        if conan_file.build_policy_always:
            conan_file.output.info("Building package from source as defined by "
                                   "build_policy='always'")
            return True

        if self.cascade and with_deps_to_build:
            return True

        # Patterns to match, if package matches pattern, build is forced
        for pattern in self.patterns:
            if pattern_match(pattern):
                try:
                    self._unused_patterns.remove(pattern)
                except ValueError:
                    pass
                return True
        return False

    def allowed(self, conan_file):
        if conan_file.build_policy == "never":  # this package has been export-pkg
            return False
        if self.missing or self.outdated:
            return True
        if conan_file.build_policy_missing:
            conan_file.output.info("Building package from source as defined by "
                                   "build_policy='missing'")
            return True
        return False

    def report_matches(self):
        for pattern in self._unused_patterns:
            self._out.error("No package matching '%s' pattern found." % pattern)
