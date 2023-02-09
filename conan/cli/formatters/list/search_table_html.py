list_packages_html_template = r"""
<!DOCTYPE html>
<html lang="en">
    <head>
        <title>Conan | {{ reference }}</title>
        <link rel="stylesheet" type="text/css" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css"/>
        <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.21/css/dataTables.bootstrap.min.css"/>
        <style>
            tr td {
                white-space:nowrap;
            }
        </style>
    </head>
    <body>
        <div class="container-fluid">
        <h1>{{ reference }}</h1>
        <div class="info">
            <p>
                Depending on your package_id_mode, any combination of settings, options and requirements
                can give you a different packageID. Take into account that your configuration might be
                different from the one used to generate the packages.
            </p>
        </div>


        <table id="results" class="table table-striped table-bordered" style="width:100%">
            <thead>

            </thead>
            <tbody>

            </tbody>
            <tfoot>

            </tfoot>
        </table>

        <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js" integrity="sha384-DfXdz2htPH0lsSSs5nCTpuj/zy4C+OGpamoFVy38MVBnE+IbbVYUew+OrCXaRkfj" crossorigin="anonymous"></script>
        <script src="https://stackpath.bootstrapcdn.com/bootstrap/3.4.1/js/bootstrap.min.js" integrity="sha384-aJ21OjlMXNL5UyIl/XNwTMqvzeRMZH2w8c5cRVpzpU8Y5bApTppSuUkhZXN0VxHd" crossorigin="anonymous"></script>
        <script type="text/javascript" src="https://cdn.datatables.net/v/dt/dt-1.10.20/datatables.min.js"></script>
        <script type="text/javascript" src="https://cdn.datatables.net/1.10.21/js/dataTables.bootstrap.min.js"></script>
        <script>

        </script>
    </div>
    </body>
    <footer>
        <div class="container-fluid">
            <div class="info">
                <p>
                      Conan <b>v{{ version }}</b> <script>document.write(new Date().getFullYear())</script> JFrog LTD. <a>https://conan.io</a>
                </p>
            </div>
        </div>
    </footer>
</html>
"""
