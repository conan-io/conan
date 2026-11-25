from conan.api.model import RecipeReference


def ref_matches(ref, pattern, is_consumer):
    if not ref or not str(ref):
        assert is_consumer
        # An unnamed consumer (conanfile.txt, conanfile.py without name, test_package, virtual
        # --requires) is not a recipe reference. Patterns restricted to recipes without
        # user/channel ("*@") must not select it, so a generic "*@:xxx" can define the
        # "third-party" packages without forcing it into the consumer. The consumer can still be
        # selected explicitly with "&" or "&@"
        selector = pattern.lstrip("!~")
        no_user_channel = selector.endswith("@")
        if no_user_channel and not selector.startswith("&"):
            ref = RecipeReference.loads("*/*@*/*")
        else:
            ref = RecipeReference.loads("*/*")
    return ref.matches(pattern, is_consumer=is_consumer)
