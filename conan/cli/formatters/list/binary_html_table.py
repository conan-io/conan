from collections import OrderedDict, defaultdict

from conans.model.package_ref import PkgReference


class RowResult(object):
    def __init__(self, remote, reference, data):
        self.remote = remote
        self.reference = reference
        self._data = data

    @property
    def recipe(self):
        return self.reference

    @property
    def package_id(self):
        return self._data['id']

    def row(self, headers):
        """ Returns package data according to headers """
        assert isinstance(headers, Headers), "Wrong type: {}".format(type(headers))

        for it in headers.keys:
            try:
                yield getattr(self, it)
            except AttributeError:
                yield self._data[it]
        for it in headers.settings:
            yield self._data['settings'].get(it, None)
        for it in headers.options:
            yield self._data['options'].get(it, None)
        if headers.requires:
            prefs = [PkgReference.loads(it) for it in self._data['requires']]
            yield ', '.join(map(str, [it.ref for it in prefs]))


class Headers(object):
    _preferred_ordering = ['os', 'arch', 'compiler', 'build_type']

    def __init__(self, settings, options, requires, keys):
        # Keys: columns to classify
        self.keys = keys
        self.options = options
        self.requires = requires

        # - Order settings
        _settings = defaultdict(list)
        for it in settings:
            try:
                category, _ = it.split('.', 1)
            except ValueError:
                _settings[it].append(it)
            else:
                _settings[category].append(it)

        self.settings = []
        for it in self._preferred_ordering:
            if it in _settings:
                self.settings.extend(sorted(_settings[it]))
        for it, values in _settings.items():
            if it not in self._preferred_ordering:
                self.settings.extend(sorted(values))

    def row(self, n_rows=2):
        """
        Retrieve list of headers as a single list (1-row) or as a list of tuples with
        settings organized by categories (2-row).

        Example output:
            1-row: ['os', 'arch', 'compiler', 'compiler.version', 'compiler.libcxx', 'build_type']
            2-row: [('os', ['']), ('arch', ['']), ('compiler', ['', 'version', 'libcxx']),]
        """
        headers = list(self.keys)
        if n_rows == 1:
            headers.extend(self.settings + self.options)
            if self.requires:
                headers.append('requires')
            return headers
        elif n_rows == 2:
            headers = [(it, ['']) for it in headers]
            settings = self._group_settings(self.settings)
            headers.extend(settings)
            headers.append(('options', self.options))
            if self.requires:
                headers.append(('requires', ['']))
            return headers
        else:
            raise NotImplementedError("not yet")

    @staticmethod
    def _group_settings(settings):
        """
        From one row to two-rows using '.' as separator
        """
        ret = OrderedDict()
        for setting in settings:
            try:
                category, value = setting.split(".", 1)
            except ValueError:
                ret.setdefault(setting, []).append('')
            else:
                ret.setdefault(category, []).append(value)
        return [(key, values) for key, values in ret.items()]


class Results(object):
    def __init__(self, results):
        self._results = results

        # Collect data inspecting the packages
        _settings = set()
        _options = set()
        _remotes = set()
        self.requires = False

        for it in results:
            _remotes.add(it['remote'])
            for p in it['items'][0]['packages']:
                _settings = _settings.union(list(p['settings'].keys()))
                _options = _options.union(list(p['options'].keys()))
                if len(p['requires']):
                    self.requires = True

        self.settings = list(_settings)
        self.options = list(_options)
        self.remotes = list(_remotes)

    def get_headers(self, keys=('remote', 'reference', 'package_id')):
        return Headers(self.settings, self.options, self.requires, keys=keys)

    def packages(self):
        for it in self._results:
            remote = it['remote']
            reference = it['items'][0]['recipe']['id']
            for p in it['items'][0]['packages']:
                r = RowResult(remote, reference, p)
                yield r



