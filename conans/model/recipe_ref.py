from conan.api.output import ConanOutput
from conan.api.model import RecipeReference as _RecipeReference

_msg = """
*******************************************************************
Private '{}'
detected in user code (custom commands, extensions, recipes, etc).
Please stop using it, use only public documented APIs, such as
'from conan.api.model import RecipeReference'
as this will break in next releases.
*******************************************************************
"""


class RecipeReference(_RecipeReference):
    usage_counter = 0

    def __init__(self, *args, **kwargs):
        if RecipeReference.usage_counter == 0:
            ConanOutput().warning(_msg.format("from conans.model.recipe_ref import RecipeReference"),
                                  warn_tag="deprecated")
        RecipeReference.usage_counter += 1
        super(RecipeReference, self).__init__(*args, **kwargs)

    @staticmethod
    def loads(*args, **kwargs):
        if RecipeReference.usage_counter == 0:
            ConanOutput().warning(_msg.format("from conans.model.recipe_ref import RecipeReference"),
                                  warn_tag="deprecated")
        RecipeReference.usage_counter += 1
        return _RecipeReference.loads(*args, **kwargs)
