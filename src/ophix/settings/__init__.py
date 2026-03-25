"""
ophix.settings
~~~~~~~~~~~~~~
Settings assembly for all Ophix Project Servers.

Import order is deliberate:
  1. base.py     — establishes all core settings
  2. plugins.py  — discovers installed plugins, extends INSTALLED_APPS,
                   folds in plugin-level setting defaults

Set DJANGO_SETTINGS_MODULE=ophix.settings in every OPS server deployment.
"""

from .base import *          # noqa: F401, F403  — core settings
from . import plugins

# Fold in plugin apps and their setting defaults.
# plugins.apply() mutates this module's globals() in-place.
plugins.apply(globals())
