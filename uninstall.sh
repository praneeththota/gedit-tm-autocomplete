#!/bin/sh

PLUGIN_FOLDER=~/.gnome2/gedit/plugins/

if [ -f $PLUGIN_FOLDER/tm_autocomplete.py ]; then
  rm $PLUGIN_FOLDER/tm_autocomplete.py
fi

if [ -f $PLUGIN_FOLDER/tm_autocomplete.pyc ]; then
  rm $PLUGIN_FOLDER/tm_autocomplete.pyc
fi

if [ -f $PLUGIN_FOLDER/tm_autocomplete.gedit-plugin ]; then
  rm $PLUGIN_FOLDER/tm_autocomplete.gedit-plugin
fi


