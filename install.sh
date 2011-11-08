#!/bin/sh
#
# Installs the plugin to the users folder

PLUGIN_FOLDER=~/.local/share/gedit/plugins/
SCHEMA_FOLDER=/usr/share/glib-2.0/schemas/
SCHEMA_NAME=org.gnome.gedit.plugins.tm_autocomplete.gschema.xml

# Install schemas
sudo install $SCHEMA_NAME $SCHEMA_FOLDER
sudo glib-compile-schemas $SCHEMA_FOLDER

# Install plugin
mkdir -p $PLUGIN_FOLDER
cp tm_autocomplete.py $PLUGIN_FOLDER
cp tm_autocomplete.plugin $PLUGIN_FOLDER



