from conan.api.model import RecipeReference
from conan.errors import ConanException


class GitRemoteSpec:
    def __init__(self, url, ref=None):
        self.url = url
        self.ref = ref  # branch, tag, or commit (optional)

    @staticmethod
    def loads(value):
        value = value.strip()
        if "@" in value:
            # Split on the LAST @, treating it as a ref separator when the part
            # before it contains a "/" (i.e. it looks like a URL or file path).
            # This handles: https://..., file:///..., C:/..., /home/...,
            # and even SSH URLs like git@github.com:user/repo.git@branch.
            # A bare "git@github.com:user/repo.git" (no extra @) is left intact
            # because rfind finds the only @, and "git" before it has no "/".
            idx = value.rfind("@")
            before = value[:idx]
            after = value[idx + 1:]
            if "/" in before and after:
                return GitRemoteSpec(before, after)
        return GitRemoteSpec(value)

    def dumps(self):
        if self.ref:
            return f"{self.url}@{self.ref}"
        return self.url

    def __repr__(self):
        return self.dumps()


class GitRemotes:
    def __init__(self):
        self._entries = {}  # "name/version" → GitRemoteSpec

    def update(self, other):
        self._entries.update(other._entries)

    def get(self, ref):
        return self._entries.get(f"{ref.name}/{ref.version}")

    @property
    def entries(self):
        return self._entries

    @staticmethod
    def loads(text):
        result = GitRemotes()
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ConanException(f"[git_remotes] invalid entry '{line}': "
                                     f"expected 'name/version: url'")
            # Split on first colon that is followed by space (to avoid splitting on http://)
            # Use ": " as separator, fall back to ":" if needed
            if ": " in line:
                key, value = line.split(": ", 1)
            else:
                key, value = line.split(":", 1)
                value = value.strip()
            key = key.strip()
            # Validate key looks like name/version
            try:
                ref = RecipeReference.loads(key)
                if ref.name is None or ref.version is None:
                    raise ConanException(f"[git_remotes] key '{key}' must be 'name/version'")
            except Exception as e:
                raise ConanException(f"[git_remotes] invalid key '{key}': {e}")
            result._entries[key] = GitRemoteSpec.loads(value)
        return result

    def dumps(self):
        lines = []
        for key, spec in self._entries.items():
            lines.append(f"{key}: {spec.dumps()}")
        return "\n".join(lines)

    def serialize(self):
        return {k: v.dumps() for k, v in self._entries.items()}

    def __bool__(self):
        return bool(self._entries)
