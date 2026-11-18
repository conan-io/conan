from functools import lru_cache

from jinja2 import Template, Undefined


class _Template(Template):

    def render(self, *args, **kwargs):
        """ The same as ``Template.render()``, but it clears the render context afterwards. The
        macros that look up other names (other macros, globals) reference the context, and the
        context references the macros, so every render would leave a reference cycle that only
        the cyclic GC can free.
        """
        ctx = self.new_context(dict(*args, **kwargs))
        try:
            return self.environment.concat(self.root_render_func(ctx))
        except Exception:
            self.environment.handle_exception()
        finally:
            ctx.vars.clear()
            ctx.exported_vars.clear()


@lru_cache(maxsize=256)
def compiled_template(text, trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=False,
                      undefined=Undefined):
    """ Compiled jinja2 ``Template`` of ``text``, cached for the generators that render the same
    templates for every package or dependency. Compiling a Template is expensive, and each one
    creates reference cycles that only the cyclic GC can free.

    The key is the full text, so templates replaced per instance (as the ``template`` of a
    CMakeToolchain block) or defined by users still get their own compiled template. The
    returned Template is shared, so it should only be rendered, never modified.
    """
    return _Template(text, trim_blocks=trim_blocks, lstrip_blocks=lstrip_blocks,
                     keep_trailing_newline=keep_trailing_newline, undefined=undefined)
