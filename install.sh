#!/bin/sh
#
# Installs the plugin to the users folder

PLUGIN_FOLDER=~/.gnome2/gedit/plugins/

mkdir -p $PLUGIN_FOLDER
cp tm_autocomplete.py $PLUGIN_FOLDER
cp tm_autocomplete.gedit-plugin $PLUGIN_FOLDER
cp tm_autocomplete.png $PLUGIN_FOLDER

