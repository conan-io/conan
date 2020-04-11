from collections import OrderedDict

from jinja2 import Template

from conans.assets.templates import search_table
from conans.model.ref import PackageReference
from conans.util.files import save


class RowResult(object):
    def __init__(self, remote, reference, data, headers):
        self.remote = remote
        self.reference = reference
        self._data = data
        self._headers = headers

    @property
    def recipe(self):
        return self.reference

    @property
    def package_id(self):
        return self._data['id']

    @property
    def outdated(self):
        return self._data['outdated']

    def row(self):
        """ Returns package data according to headers """
        for it in self._headers.keys:
            try:
                yield getattr(self, it)
            except AttributeError:
                yield self._data[it]
        for it in self._headers.settings:
            yield self._data['settings'].get(it, None)
        for it in self._headers.options:
            yield self._data['options'].get(it, None)
        if self._headers.requires:
            prefs = [PackageReference.loads(it) for it in self._data['requires']]
            yield ', '.join(map(str, [it.ref for it in prefs]))


class Headers(object):
    _preferred_ordering = ['os', 'arch', 'compiler', 'build_type']

    def __init__(self, results, add_reference=False, add_outdated=False):
        # Process results
        self.keys = ['remote', 'reference', 'package_id'] \
            if add_reference else ['remote', 'package_id']
        if add_outdated:
            self.keys.append('outdated')
        _settings = set()
        self.options = set()
        self.requires = False

        # - Collect data from the packages
        for it in results:
            for p in it['items'][0]['packages']:
                _settings = _settings.union(list(p['settings'].keys()))
                self.options = self.options.union(list(p['options'].keys()))
                if len(p['requires']):
                    self.requires = True
        self.options = list(self.options)

        # - Order settings
        self.settings = []
        for it in self._preferred_ordering:
            if it in _settings:
                self.settings.append(it)
        for it in _settings:
            if it not in self.settings:
                self.settings.append(it)

    def row(self, n_rows=2):
        """
        Retrieve list of headers as a single list (1-row) or as a list of tuples with
        settings organized by categories (2-row).

        Example output:
            1-row: ['os', 'arch', 'compiler', 'compiler.version', 'compiler.libcxx', 'build_type']
            2-row: [('os', ['']), ('arch', ['']), ('compiler', ['', 'version', 'libcxx']),]
        """
        headers = self.keys.copy()
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
        Returns a list of tuples with the settings organized by categories (and ordered
        according to the conventional 'os', 'arch', 'compiler', 'build_type'), useful for
        tables with two rows for headers.

        Output looks like:
        [('os', ['']), ('arch', ['']), ('compiler', ['', 'version', 'libcxx']), ('build_type', [''])]
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

    def get_headers(self, add_reference=False, add_outdated=False):
        return Headers(self._results, add_reference=add_reference, add_outdated=add_outdated)

    def packages(self, headers):
        assert isinstance(headers, Headers), "Wrong type: {}".format(type(headers))
        for it in self._results:
            remote = it['remote']
            reference = it['items'][0]['recipe']['id']
            for p in it['items'][0]['packages']:
                r = RowResult(remote, reference, p, headers)
                yield r


def html_binary_graph(search_info, reference, table_filename):
    # Adapt data to the template (think twice about the format before documenting)
    search = {'reference': str(reference)}
    results = Results(search_info)

    # Render and save
    content = Template(search_table.content).render(search=search, results=results)
    save(table_filename, content)
