"""Sphinx configuration for Intraday Momentum documentation."""

import os
import sys

# Add project root to path for autodoc
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------
project = "Intraday Momentum"
copyright = "2025, Szatan, Lambert, Kowalczyk, Szostak"
author = "Eryk Szatan, Kacper Rickie Lambert, Natalia Kowalczyk, Radoslaw Szostak"
release = "0.1.0"

# -- General configuration ---------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# -- Napoleon settings -------------------------------------------------
napoleon_google_style = False
napoleon_numpy_style = True
napoleon_include_init_with_doc = True

# -- Intersphinx -------------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
}

# -- Autodoc settings --------------------------------------------------
autodoc_member_order = "bysource"
autodoc_typehints = "description"
