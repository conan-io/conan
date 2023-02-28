list_packages_html_template = r"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>conan list results</title>
    <script>
      var list_results = {{ results|safe }};
      document.addEventListener("DOMContentLoaded", function () {
        var divContainer = document.getElementById("showResults");
        divContainer.innerHTML = JSON.stringify(list_results, null, 2);
      });
    </script>
  </head>

  <body>
  <pre id="showResults"></pre>
  </body>
  <footer>
    <p>
      Conan <b>{{ version }}</b>
      <script>
        document.write(new Date().getFullYear());
      </script>
      JFrog LTD. <a href="https://conan.io">https://conan.io</a>
    </p>
  </footer>
</html>
"""
