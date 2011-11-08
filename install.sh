#!/bin/sh
#
# Installs the plugin to the users folder

PLUGIN_FOLDER=~/.local/share/gedit/plugins/

# Install plugin
mkdir -p $PLUGIN_FOLDER
cp tm_autocomplete.py $PLUGIN_FOLDER
cp tm_autocomplete.plugin $PLUGIN_FOLDER



