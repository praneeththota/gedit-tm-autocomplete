#!/bin/sh
#
# Installs the plugin to the users folder

PLUGIN_FOLDER=~/.gnome2/gedit/plugins/

# Install plugin
mkdir -p $PLUGIN_FOLDER
cp tm_autocomplete.py $PLUGIN_FOLDER
cp tm_autocomplete.gedit-plugin $PLUGIN_FOLDER



