_conanfile = '''\
from conan import ConanFile

class AliasConanfile(ConanFile):
    name = "{{name}}"
    {% if version is defined %}version = "{{version}}"{%endif%}
    alias = "{{name}}/{{target}}"
    revision_mode = "{{revision_mode|default('hash')}}"
'''


alias_file = {"conanfile.py": _conanfile}
