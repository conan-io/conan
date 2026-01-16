from jinja2 import Environment
import os

def _deactivate_func_name(filename):
    return os.path.splitext(os.path.basename(filename))[0].replace("-", "_")


def _old_env_prefix(filename):
    return f"_CONAN_OLD_{_deactivate_func_name(filename).upper()}"


def _deactivate_function_names(filenames):
    return [os.path.splitext(os.path.basename(s))[0].replace("-", "_")
            for s in reversed(filenames)]

env = Environment()
env.globals["old_env_prefix"] = _old_env_prefix
env.globals["deactivate_func_name"] = _deactivate_func_name
env.globals["deactivate_func_names"] = _deactivate_function_names
env.globals["os"] = os

ps_virtualenv_global_template = env.from_string('''<#
{% for file in files -%}
& "{{file}}"
{% endfor %}


function global:deactivate_conan{{group}} {
    # Call deactivation functions
    {% for name in deactivate_func_names(files) -%}
    & "deactivate_{{name}}"
    {% endfor %}
    # Cleanup (Remove the function itself)
    Remove-Item -Path function:deactivate_conan{{group}} -ErrorAction SilentlyContinue
}

''')

ps_virtualenv_call_scripts = env.from_string(("""
{% for file in files -%}
& "{{file}}"
{% endfor %}
""").strip())

sh_virtualenv_global_template = env.from_string(('''
{% for file in files -%}
. "{{file}}"
{% endfor %}

deactivate_conan{{group}}() {
    # Call deactivation functions
    {% for name in deactivate_func_names(files) -%}
    "deactivate_{{name}}"
    {% endfor -%}

    # Remove the function itself
    unset -f deactivate_conan{{group}}
}

''').strip())

sh_virtualenv_call_scripts = env.from_string(("""
{% for file in files -%}
. "{{file}}"
{% endfor %}
""").strip())

ps_virtualenv_function_template = env.from_string(("""
{% if generate_deactivate -%}
{% set func_name = "deactivate_" + deactivate_func_name(filename) -%}
{% set var_prefix = old_env_prefix(filename) -%}
function global:{{func_name}} {
    Write-Host "Restoring environment"
    foreach ($v in @({{vars_list}})) {
        $oldVarName = "{{var_prefix}}_$v"
        $oldValue = Get-Item -Path "Env:$oldVarName" -ErrorAction SilentlyContinue
        if (Test-Path env:$oldValue) {
            Remove-Item -Path "Env:$v" -ErrorAction SilentlyContinue
        } else {
            Set-Item -Path "Env:$v" -Value $oldValue.Value
        }
        Remove-Item -Path "Env:$oldVarName" -ErrorAction SilentlyContinue
    }
    Remove-Item -Path function:{{func_name}} -ErrorAction SilentlyContinue
}
{% endif -%}


{% for varname, (defined, value) in values.items() -%}
if ($env:{{varname}}) { $env:{{old_env_prefix(filename)}}_{{varname}} = $env:{{varname}} }
{% if defined -%}
$env:{{varname}}="{{value}}"
{% else -%}
if (Test-Path env:{{varname}}) { Remove-Item env:{{varname}} }
{% endif %}
{% endfor %}
""").strip())

ps_virtualenv_script_template = env.from_string(("""
{% set deactivate_file = "deactivate_" + filename -%}
Push-Location $PSScriptRoot
{% if generate_deactivate -%}
"echo `"Restoring environment`"" | Out-File -FilePath "{{deactivate_file}}"
$vars = (Get-ChildItem env:*).name
$updated_vars = @({{vars_list}})

foreach ($var in $updated_vars)
{
    if ($var -in $vars)
    {
        $var_value = (Get-ChildItem env:$var).value
        Add-Content "{{deactivate_file}}" "`n`$env:$var = `"$var_value`""
    }
    else
    {
        Add-Content "{{deactivate_file}}" "`nif (Test-Path env:$var) { Remove-Item env:$var }"
    }
}
Pop-Location
{% endif %}
{% for varname, (defined, value) in values.items() -%}
{% if defined -%}
$env:{{varname}}="{{value}}"
{% else -%}
if (Test-Path env:{{varname}}) { Remove-Item env:{{varname}} }
{% endif -%}
{% endfor -%}
""").strip())


sh_virtualenv_function_template = env.from_string(("""
{% if generate_deactivate -%}
{% set func_name = "deactivate_" + deactivate_func_name(filename) -%}
# sh-like function to restore environment
{{func_name}} () {
    echo "Restoring environment"
    for v in {{vars_list}}; do
        old_var="{{old_env_prefix(filename)}}_${v}"
        # Use eval for indirect expansion (POSIX safe)
        eval "is_set=\\${${old_var}+x}"
        if [ -n "${is_set}" ]; then
            eval "old_value=\\${${old_var}}"
            eval "export ${v}=\\${old_value}"
        else
            unset "${v}"
        fi
        unset "${old_var}"
    done
    unset -f {{func_name}}
}
{% endif -%}

{% for varname, (defined, value) in values.items() -%}
{% raw %}if [ -n "${{% endraw %}{{ varname }}{% raw %}+x}" ]; then export {% endraw %}{{ old_env_prefix(filename) }}{% raw %}_{% endraw %}{{ varname }}{% raw %}="${{% endraw %}{{ varname }}{% raw %}}";fi{% endraw %}
{% if defined -%}
export {{varname}}="{{value}}"
{% else -%}
unset {{varname}}
{% endif %}
{% endfor %}
""").strip())

sh_virtualenv_script_template = env.from_string(("""
{% if generate_deactivate -%}
script_folder="{{os.path.abspath(filepath)}}"
{% set deactivate_file = os.path.join("$script_folder", "deactivate_" + filename) -%}
echo "echo Restoring environment" > "{{deactivate_file}}"
for v in {{vars_list}}
do
    is_defined="true"
    value=$(printenv $v) || is_defined="" || true
    if [ -n "$value" ] || [ -n "$is_defined" ]
    then
        echo export "$v='$value'" >> "{{deactivate_file}}"
    else
        echo unset $v >> "{{deactivate_file}}"
    fi
done
{% endif %}

{% for varname, (defined, value) in values.items() -%}
{% if defined -%}
export {{varname}}="{{value}}"
{% else -%}
unset {{varname}}
{% endif -%}
{% endfor %}
""").strip())

