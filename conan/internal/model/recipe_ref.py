from conan.api.model import RecipeReference


def ref_matches(ref, pattern, is_consumer):
    if not ref or not str(ref):
        assert is_consumer
        ref = RecipeReference.loads("*/*")  # FIXME: ugly
    return ref.matches(pattern, is_consumer=is_consumer)
