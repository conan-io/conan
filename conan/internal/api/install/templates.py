from jinja2 import Template

powershell_virtualenv_template = Template('''<#
.SYNOPSIS
    Activates the Conan {{group}} environment for the current shell session.
.DESCRIPTION
    Sets environment variables (like PATH) for the Conan {{group}} configuration.
    Defines a 'deactivate_conan{{group}}' function to safely restore the original environment.
.PARAMETER Verbose
    Print information about the modified variables during activation and restoration.
.EXAMPLE
    .\\conan{{group}}.ps1 -Verbose
.EXAMPLE
    .\\conan{{group}}.ps1 ; deactivate_conan{{group}} -Verbose
#>
# Requires PowerShell 3.0 or later

# --- Top-Level Script Argument Handling (Enables -Verbose implicitly) ---
[CmdletBinding()]
param()

# 1. Execute the environment setup scripts
# Note: We use @PSBoundParameters to forward all built-in and custom parameters
#       (including -Verbose) to the inner script.
{% for file in files -%}
& "{{file}}" @PSBoundParameters
{% endfor %}
Write-Verbose 'Environment activated. Run "deactivate_conan{{group}}" to restore.'


function global:deactivate_conan{{group}} {
    <#
    .SYNOPSIS
        Restores the environment modified by conan{{group}}.ps1
    .DESCRIPTION
        Restores the PATH and other environment variables set by the Conan {{group}} activation script.
    .PARAMETER Verbose
        Prints information about the restored variables.
    .EXAMPLE
        deactivate_conan{{group}} -Verbose
    #>
    # CmdletBinding enables -Verbose for this function implicitly.
    [CmdletBinding()]
    param()

    # Call deactivation functions
    {% for name in deactivate_function_names(files) -%}
    & "deactivate_{{name}}" @PSBoundParameters
    {% endfor %}
    # Cleanup (Remove the function itself)
    Remove-Item -Path function:deactivate_conan{{group}} -ErrorAction SilentlyContinue
}

''')



sh_virtualenv_template = Template('''
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    printf "%s [-v|--verbose]\\n" "$0"
    printf "  Activate Conan {{group}} environment\\n"
    printf "  -v, --verbose   Print information about the modified variables\\n"
    return 0
fi

conan_verbose=false; [ "$1" = "-v" ] || [ "$1" = "--verbose" ] && conan_verbose=true

{% for file in files -%}
. "{{file}}"
{% endfor %}

deactivate_conan{{group}}() {
    if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        printf "deactivate_conan{{group}} [-v|--verbose]\\n"
        printf "  Restores the environment modified by conan{{group}}.sh\\n"
        printf "  -v, --verbose   Print information about the restored variables\\n"
        return 0
    fi
    conan_verbose=false; [ "$1" = "-v" ] || [ "$1" = "--verbose" ] && conan_verbose=true

    # Call deactivation functions
    {% for name in deactivate_function_names(files) -%}
    "deactivate_{{name}}"
    {% endfor %}

    # Remove the function itself
    unset -f deactivate_conan{{group}}
}

''')
