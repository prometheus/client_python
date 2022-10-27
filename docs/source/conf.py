"""
configuration files for Sphinx. Boostraped with sphinx-quickstart.
"""
from datetime import datetime

# -- Project information -----------------------------------------------------

project = "prometheus_client"
copyright = f"2015-{datetime.now().year}, Brian Brazil"
author = "Brian Brazil"
release = "2015"
# NOTE: sync with setup.py
version = "0.15.0"

# -- General configuration ---------------------------------------------------

source_suffix = [".md"]

# See https://github.com/readthedocs/readthedocs.org/issues/2149
master_doc = "index"

extensions = [
    "sphinxext.opengraph",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx.ext.ifconfig",
    "sphinx.ext.extlinks",
    "sphinx_click.ext",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx_issues",
    "sphinxcontrib.spelling",
    "myst_parser",
    "sphinx_inline_tabs",
]
extlinks = {
    "github": ("https://github.com/%s", "%s"),  # noqa: WPS323
}


templates_path = ["_templates"]
exclude_patterns = []

# Plugin Configurations:
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_special_with_doc = False
napoleon_attr_annotations = True
autodoc_typehints = "signature"
autodoc_typehints_format = "short"
autodoc_typehints_description_target = "documented"

autosectionlabel_prefix_document = True
autosectionlabel_maxdepth = 10

# TODO: configure opengraph
# ogp_site_url = ""
# ogp_image = ""
# ogp_site_name = ""
# ogp_use_first_image = True

issues_default_group_project = "prometheus/client_python"

todo_include_todos = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]


# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "zenburn"
pygments_dark_style = "monokai"

# https://myst-parser.readthedocs.io/en/latest/syntax/optional.html
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

# Remove the prompt when copying examples
copybutton_prompt_text = r">>> |\.\.\.|> |» |\% |\$ "
copybutton_prompt_is_regexp = True
copybutton_line_continuation_character = "\\"
copybutton_here_doc_delimiter = "EOT"
copybutton_selector = "div:not(.no-copybutton) > div.highlight > pre"

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_title = "Prometheus Python Client"
html_static_path = ["_static"]
