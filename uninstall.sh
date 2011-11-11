#!/bin/sh

PLUGIN_FOLDER=~/.local/share/gedit/plugins/
ICONS_FOLDER=~/.local/share/icons/

# Uninstall plugin
if [ -f $PLUGIN_FOLDER/tm_autocomplete.py ]; then
  rm $PLUGIN_FOLDER/tm_autocomplete.py
fi

if [ -f $PLUGIN_FOLDER/tm_autocomplete.pyc ]; then
  rm $PLUGIN_FOLDER/tm_autocomplete.pyc
fi

if [ -f $PLUGIN_FOLDER/tm_autocomplete.plugin ]; then
  rm $PLUGIN_FOLDER/tm_autocomplete.plugin
fi

# Uninstall icon
if [ -f $ICONS_FOLDER/tm_autocomplete.png ]; then
  rm $ICONS_FOLDER/tm_autocomplete.png
fi

