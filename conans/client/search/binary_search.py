from conans.client.cmd.search import Search


class BinarySearcher(object):
    """ main class responsible of searching binary packages locally and/or in remotes
    """

    def __init__(self, app, recorder):
        self._cache = app.cache
        self._remote_manager = app.remote_manager
        self._graph_manager = app.graph_manager
        self._recorder = recorder

    def _search_packages(self, ref, remotes, remote_name):
        search = Search(self._cache, self._remote_manager, remotes)
        packages = search.search_packages(ref, remote_name)
        return packages

    def _evaluate_results(self, graph_info, remotes, packages):
        deps_graph = self._graph_manager.load_graph(graph_info.root, None, graph_info,
                                                    ["never"], False, False, remotes,
                                                    self._recorder)
        root_node = deps_graph.by_levels().pop()[0]
        package_name = graph_info.root.name
        ref, conanfile, package_id = root_node.ref, root_node.conanfile, root_node.package_id
        dependencies = [str(dep.dst) for dep in root_node.dependencies]
        query = Query(package_name, conanfile.info, package_id, dependencies)
        result_processor = Processor(query, packages)
        return result_processor.result_info

    def search(self, graph_info, remotes, remote_name):
        packages = self._search_packages(graph_info.root, remotes, remote_name)
        return self._evaluate_results(graph_info, remotes, packages)


class Processor(object):
    """ this class does all the "work" for comparing a package query to a list of search results
    """

    def __init__(self, query, search_results):
        self._query = query
        self._search_results = search_results

    @property
    def result_info(self):
        comparisons = []
        for remote_name, remote_refs in self._search_results.items():
            for package_id, package_info in remote_refs.ordered_packages.items():
                search_result = SearchResult(package_id, package_info, remote_name)
                comparison = Processor.compare_query_to_result(self._query, search_result)
                comparisons.append(comparison)
        processed_results = ResultInfo(self._query, sorted(comparisons))
        return processed_results

    @staticmethod
    def compare_query_to_result(query, result):
        s_dist, s_diffs = Processor._compare_dicts(query.settings, result.settings, kv_separator="=")
        o_dist, o_diffs = Processor._compare_dicts(query.options, result.options, kv_separator="=")
        r_dist, r_diffs = Processor._compare_dicts(query.requires, result.requires, kv_separator=":")

        comparison = Comparison(result,
                                s_dist + o_dist + r_dist,
                                PackageDiff(s_diffs, o_diffs, r_diffs))
        return comparison

    @staticmethod
    def _compare_dicts(dict1, dict2, kv_separator):
        distance = 0
        diffs = []
        for key1, value1 in dict1.items():
            if key1 in dict2:
                value2 = dict2[key1]
                if value2 != value1:
                    diffs.append(Processor._dict_different(key1, kv_separator, value1, value2))
                    distance += 1
        for setting_name2, value2 in dict2.items():
            if setting_name2 not in dict1:
                diffs.append(Processor._dict_added(setting_name2, value2))
                distance += 1
        return distance, diffs

    @staticmethod
    def _dict_diff(key, value1, annotation):
        diff = (key, value1, annotation)
        return diff

    @staticmethod
    def _dict_different(key, sep, value1, value2):
        return Processor._dict_diff(
            key, value2, "### {}{}{} was supplied in query".format(key, sep, value1)
        )

    @staticmethod
    def _dict_added(key, value1):
        return Processor._dict_diff(key, value1, "# No value supplied in query")

    @staticmethod
    def _dict_removed(key, value1):
        return Processor._dict_diff(key, value1, "# Missing value supplied in query")


class ResultInfo(object):
    """ main result provided to callers with access to all relevant result data
    """

    def __init__(self, query, comparisons):
        self.query = query
        self.comparisons = comparisons


class Query(object):
    """ model the complete configuration passed by the user
    """

    def __init__(self, package_name, conanfile_info, package_id, dependencies):
        self.package_name = package_name
        self.conanfile_info = conanfile_info
        self.package_id = package_id
        self.dependencies = dependencies

    @property
    def settings(self):
        settings_list = self.conanfile_info.full_settings.dumps().splitlines()
        settings = {}
        for item in settings_list:
            setting_name, value = item.split("=")
            settings[setting_name] = value
        return settings

    @property
    def options(self):
        options_list = self.conanfile_info.full_options.dumps().splitlines()
        options = {}
        for item in options_list:
            option_name, value = item.split("=")
            # query_options are in format of package:option=value
            # result_options are in format of option=value, and only contain target package options
            # we only care about target package options and we want option=value format
            pkg_name, option_name_short = option_name.split(":")
            if pkg_name == self.package_name:
                options[option_name_short] = value
        return options

    @property
    def requires(self):
        requires = self.conanfile_info.full_requires.dumps().splitlines()
        # Convert list into map of reference to PID so we can compare package id correctly
        requires_dict = {ref: pid for ref, pid in
                         (requires.split(":") for requires in requires)}
        # The query lists the target package in full_requires, so we have to filter that out
        filtered = {k: v for (k, v) in requires_dict.items() if
                    not k.startswith(self.package_name + "/")}
        return filtered

    def dumps(self):
        result = []
        result.append("[settings]")
        for key, value in self.settings.items():
            result.append("%s=%s" % (key, value))
        result.append("[options]")
        for key, value in self.options.items():
            result.append("%s=%s" % (key, value))
        result.append("[requires]")
        for key, value in self.requires.items():
            result.append("%s:%s" % (key, value))
        return "\n".join(result)


class SearchResult(object):
    """ model the result that comes back from conan search
    """

    def __init__(self, package_id, conanfile_info, remote_name):
        self.package_id = package_id
        self.conanfile_info = conanfile_info
        self.remote_name = remote_name

    @property
    def settings(self):
        if "settings" in self.conanfile_info:
            settings = self.conanfile_info["settings"]
        else:
            settings = {}
        return settings

    @property
    def options(self):
        if "options" in self.conanfile_info:
            options = self.conanfile_info["options"]
        else:
            options = {}
        return options

    @property
    def requires(self):
        if "full_requires" in self.conanfile_info:
            # Convert list into map of reference to PID so we can compare package id correctly
            requires = {ref: pid for ref, pid in
                        (requires.split(":") for requires in self.conanfile_info["full_requires"])}
        else:
            requires = {}
        return requires

    def dumps(self):
        result = []
        result.append("[settings]")
        for key, value in self.settings.items():
            result.append("%s=%s" % (key, value))
        result.append("[options]")
        for key, value in self.options.items():
            result.append("%s=%s" % (key, value))
        result.append("[requires]")
        for key, value in self.requires.items():
            result.append("%s:%s" % (key, value))
        return "\n".join(result)


class Comparison(object):
    """ for each search result, a comparison is generated to encapsulate the diff and distance
    """

    def __init__(self, result, distance, diff):
        self.result = result
        self.distance = distance
        self.diff = diff

    def __lt__(self, other):
        return self.distance < other.distance


class PackageDiff(object):
    """ Each diff is a list of 3-tuples : key, value, annotation
    """

    def __init__(self, settings_diffs, options_diffs, requires_diffs):
        self.settings_diffs = settings_diffs
        self.options_diffs = options_diffs
        self.requires_diffs = requires_diffs

    def annotate(self, search_result_dump_string):
        string = search_result_dump_string
        for k, v, annotation in self.settings_diffs:
            string = string.replace(
                "{}={}".format(k, v),
                "{}={}                         {}".format(k, v, annotation))
        for k, v, annotation in self.options_diffs:
            string = string.replace(
                "{}={}".format(k, v),
                "{}={}                         {}".format(k, v, annotation))
        for k, v, annotation in self.requires_diffs:
            string = string.replace(
                "{}:{}".format(k, v),
                "{}:{}     {}".format(k, v, annotation))
        return string
