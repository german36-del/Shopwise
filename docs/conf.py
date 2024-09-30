# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys
from recommonmark.transform import AutoStructify

sys.path.insert(0, os.path.abspath(".."))

project = "Shopwise"
copyright = "2024, Germán Ferrando"
author = "Germán Ferrando"
release = "0.1"

add_module_names = False
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.githubpages",
    "recommonmark",
    "sphinx_markdown_tables",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static", "assets"]


source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}


def setup(app):
    app.add_config_value(
        "recommonmark_config",
        {
            "auto_toc_tree_section": "Contents",
            "enable_eval_rst": True,
        },
        True,
    )
    app.add_transform(AutoStructify)
