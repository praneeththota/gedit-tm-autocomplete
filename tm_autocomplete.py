# -*- coding: utf-8 -*-
#
# Gedit Plugin for TextMate style autocompletion. Tap Esc to cycle through 
# completions.
#
# Copyright © 2010, Kevin McGuinness <kevin.mcguinness@gmail.com>
#
# Thanks to Dan Gindikin <dgindikin@gmail.com> for the proximity based search 
# code, and most recent match promotion
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
# 
#

__version__ = '1.0.5-gnome3'
__author__ = 'Kevin McGuinness'

from gi.repository import GObject, Gtk, Gdk, Gedit, PeasGtk, Gio

import re

# The default trigger: a (keyval, mod) pair
DEFAULT_TRIGGER = (Gdk.KEY_Escape, 0)

def uniq_order_preserved(v):
  z, s = [], set()
  for x in v:
    if x not in s:
      s.add(x)
      z.append(x)
  return z

def zip_no_truncation(v,w):
  z = []
  for i in range(max(len(v),len(w))):
    if i < len(v):
      z.append(v[i])
    if i < len(w):
      z.append(w[i])
  return z

class AutoCompleter(object):
  """Class that actually does the autocompletion"""

  IgnoreUnderscore = True
  ValidScopes = ('document', 'window', 'application')
  ValidOrders = ('alphabetical', 'proximity')
  LastAcceptedMatch = None

  __slots__ = (
    'doc',       # The document autocomplete was initiated on
    'word',      # Word being completed
    'matches',   # List of potential autocompletions
    'index',     # Index of the next autocompletion to suggest
    'iter_s',    # GtkTextIterator pointing to the start of word being completed
    'iter_i',    # GtkTextIterator pointing to insertion point
    'iter_e',    # GtkTextIterator pointing to end of last insertion
    'scope',     # Search scope (document|application|window)
    'order',     # Result list ordering (proximity|alphabetical)
    'promote',   # Promote last accepted match
  )

  def __init__(self, doc, scope='document', order='alphabetical', 
    promote=False):
    """Create an autocompleter for the document. Indexes the words in the 
       current scope and builds a list of matches for the current cursor 
       position. Calling insert_next_completion will cycle through the matches,
       replacing the last match inserted (if any).

       If order is 'alphabetical' then the autocompletion list is ordered 
       alphabetically. If order is 'proximity' then the autocompletion list
       is ordered based on distance from the cursor in the current document,
       with the other open documents being ordered alphabetcially.
    """
    self.scope = scope
    self.order = order
    self.promote = promote
    self.reindex(doc)

  def _get_iter_for_beginning_of_word_at(self, iter1):
    """Returns a GtkTextIter pointing to the start of the current word"""
    if not self.IgnoreUnderscore:
      # Just use pango's word start facility
      result = iter1.copy()
      result.backward_word_start()
    else:
      # Including underscores in the words
      i = iter1.copy()
      while not i.starts_sentence() and i.backward_char():
        ch = i.get_char()
        if ch.isalnum() or ch == '_':
          continue
        else:
          i.forward_char()
          break
      result = i 
    return result

  def _can_autocomplete_at(self, iter1):
    """Returns true if autocompletion can be done at the given iterator"""
    if iter1.ends_word() or iter1.inside_word():
      return True
    if self.IgnoreUnderscore:
      i = iter1.copy()
      if not i.starts_sentence() and i.backward_char() and i.get_char() == '_':
        return True
    return False

  def _get_current_doc_words_sorted_by_proximity(self, regex):
    """Returns the words in the current document sorted by distance from 
       cursor.
    """
    fwd_text = self.doc.get_text(self.iter_i, self.doc.get_end_iter(), False)
    bck_text = self.doc.get_text(self.doc.get_start_iter(), self.iter_s, False)
    fwd_words = regex.findall(fwd_text)
    bck_words = regex.findall(bck_text)
    bck_words.reverse()
    all_words = zip_no_truncation(bck_words, fwd_words)
    return uniq_order_preserved(all_words)

  def _get_current_doc_words(self, regex):
    """Returns an unsorted list of words in the current document. The given 
       regex is used to match the words.
    """
    iter1 = self.doc.get_start_iter()
    iter2 = self.doc.get_end_iter()
    text = self.doc.get_text(iter1, iter2, False)
    words = set(regex.findall(text))
    return list(words)

  def _get_other_doc_words(self, regex):
    """Returns an unsorted list of words in the non-current document based
       on the selected scope. The given regex is used to match the words.
    """
    if self.scope == 'application':
      # Index all documents open in any gedit window
      docs = Gedit.App.get_default().get_documents()
    elif self.scope == 'window':
      # Index all documents in this gedit window
      docs = Gedit.App.get_default().get_active_window().get_documents()
    else:
      # No other documents in use
      docs = []
    words = set()
    for doc in docs:
      if doc != self.doc:
        text = doc.get_text(doc.get_start_iter(), doc.get_end_iter(), False)
        words.update(regex.findall(text))
    return list(words)

  def _create_regex_for_prefix(self, prefix):
    """Compiles a regular expression that matches words beginning with the 
       given prefix. If the prefix is empty, a match-any-word regular 
       expression is created.
    """
    return re.compile(r'\b' + prefix + r'\w+\b')

  def _get_candidate_matches(self, doc, prefix):
    """Returns all words in the document that match the given word"""
    regex = self._create_regex_for_prefix(prefix)
    if self.order == 'alphabetical':
      # Alphabetical sort
      words = self._get_current_doc_words(regex)
      other = self._get_other_doc_words(regex) 
      words.extend(other)
      words.sort()
    else:
      # Proximity sort in current doc, alphabetical in others
      words = self._get_current_doc_words_sorted_by_proximity(regex)
      other = self._get_other_doc_words(regex) 
      other.sort()
      words.extend(other)
    return uniq_order_preserved(words)

  def _should_promote_last_accepted(self, prefix):
    last = AutoCompleter.LastAcceptedMatch
    return (last is not None and self.promote and
      len(prefix) > len(last) and last.startswith(prefix))

  def reindex(self, doc):
    """Compile a list of candidate words for autocompletion"""
    self.doc = doc
    self.word = None
    self.matches = []
    self.index = 0
    self.iter_e = None
    self.iter_i = doc.get_iter_at_mark(doc.get_insert())
    if self._can_autocomplete_at(self.iter_i):
      self.iter_s = self._get_iter_for_beginning_of_word_at(self.iter_i)
      self.iter_e = self.iter_i.copy()
      self.word = doc.get_text(self.iter_s, self.iter_i, False)
      self.matches = self._get_candidate_matches(doc, self.word)
      if self._should_promote_last_accepted(self.word):
        self.matches.remove(self.LastAcceptedMatch)
        self.matches.insert(0, self.LastAcceptedMatch)
    return len(self.matches) > 0

  def has_completions(self):
    """Returns true if we can do autocompletion"""
    return 0 <= self.index < len(self.matches)

  def insert_next_completion(self):
    """Insert the next autocompletion into the document and move the cursor
       to the end of the completion. The previous autocompletion is removed.
    """
    insert_ok = self.has_completions()
    if insert_ok:
      self.doc.begin_user_action()
      
      # Store insertion offset
      insertion_point = self.iter_i.get_offset()
      
      # Remove previous completions
      if not self.iter_i.equal(self.iter_e):
        self.doc.delete(self.iter_i, self.iter_e)
        self.iter_i = self.doc.get_iter_at_offset(insertion_point)
      
      # Insert new completion
      match = self.matches[self.index]
      completion = match[len(self.word):]
      self.doc.insert(self.iter_i, completion, len(completion))
      AutoCompleter.LastAcceptedMatch = match
      
      # Update iterators
      self.iter_i = self.doc.get_iter_at_offset(insertion_point)
      self.iter_e = self.iter_i.copy()
      self.iter_s = self.iter_i.copy()
      self.iter_e.forward_chars(len(completion))
      self.iter_s.backward_chars(len(match))
      
      # Move cursor
      self.doc.place_cursor(self.iter_e)
      
      # Next completion
      self.index = self.index + 1 if self.index + 1 < len(self.matches) else 0
      self.doc.end_user_action()
    
    return insert_ok


class AutoCompletionPlugin(GObject.Object, Gedit.WindowActivatable,
    PeasGtk.Configurable):
  """TextMate style autocompletion plugin for Gedit"""
  
  __gtype_name__ = "AutoCompletionPlugin"
  SettingsKey = 'org.gnome.gedit.plugins.tm_autocomplete'
  window = GObject.property(type=Gedit.Window)

  def __init__(self):
    GObject.Object.__init__(self)
    self.autocompleter = None
    self.trigger = DEFAULT_TRIGGER
    self.scope = 'document'
    self.order = 'proximity'
    self.promote_last_accepted = True
    self.settings = Gio.Settings(self.SettingsKey)
    self.settings_signal_handlers = []

  def do_activate(self):
    self.activate_settings()
    self.update_ui()

  def do_deactivate(self):
    for view in self.window.get_views():
      for handler_id in getattr(view, 'autocomplete_handlers', []):
        view.disconnect(handler_id)
      setattr(view, 'autocomplete_handlers_attached', False)
    self.autocompleter = None   
    self.deactivate_settings()

  def do_update_state(self):
    self.update_ui()

  def update_ui(self):
    view = self.window.get_active_view()
    doc = self.window.get_active_document()
    if isinstance(view, Gedit.View) and doc:
      if not getattr(view, 'autocomplete_handlers_attached', False):
        setattr(view, 'autocomplete_handlers_attached', True)
        self.autocompleter = None
        id1 = view.connect('key-press-event', self.on_key_press, doc)
        id2 = view.connect('button-press-event', self.on_button_press, doc)
        setattr(view, 'autocomplete_handlers', (id1, id2))

  def is_autocomplete_trigger(self, event):
    keyval, modifiers = self.trigger
    if modifiers and (modifiers & event.state) == 0:
      # Required modifiers not depressed
      return False
    return event.keyval == keyval

  def on_key_press(self, view, event, doc):
    if self.is_autocomplete_trigger(event):
      if not self.autocompleter:
        self.autocompleter = AutoCompleter(doc, self.scope, self.order,
          self.promote_last_accepted)
      if self.autocompleter and self.autocompleter.has_completions():
        self.autocompleter.insert_next_completion()
      else:
        self.autocompleter = None
      return True
    elif self.autocompleter:
      self.autocompleter = None
    return False

  def on_button_press(self, view, event, doc):
    if self.autocompleter:
      self.autocompleter = None
    return False

  def set_scope(self, scope):
    if scope != self.scope and scope in AutoCompleter.ValidScopes:
      self.scope = scope
      self.autocompleter = None
      return True
    return False

  def set_order(self, order):
    if order != self.order and order in AutoCompleter.ValidOrders:
      self.order = order
      self.autocompleter = None
      return True
    return False

  def set_promote_last_accepted(self, promote_last_accepted):
    if self.promote_last_accepted != promote_last_accepted:
      self.promote_last_accepted = promote_last_accepted
      self.autocompleter = None
      return True
    return False

  def set_trigger(self, trigger):
    if isinstance(trigger, str):
      try:
        self.trigger = Gtk.accelerator_parse(trigger)
      except:
        self.trigger = DEFAULT_TRIGGER
    elif isinstance(trigger, tuple):
      self.trigger = trigger
    else:
      self.trigger = DEFAULT_TRIGGER

  def get_trigger_name(self):
    keyval, modifiers = self.trigger
    return Gtk.accelerator_name(keyval, modifiers or 0)

  def activate_settings(self):
    def on_promote_changed(settings, key, data):
      self.set_promote_last_accepted(settings.get_boolean(key))
    def on_scope_changed(settings, key, data):
      self.set_scope(settings.get_string(key))
    def on_order_changed(settings, key, data):
      self.set_order(settings.get_string(key))
    def on_trigger_changed(settings, key, data):
      self.set_trigger(settings.get_string(key))
    signals = (
      ('changed::promote', on_promote_changed),
      ('changed::scope', on_scope_changed),
      ('changed::order', on_order_changed),
      ('changed::trigger', on_trigger_changed))
    self.settings_signal_handlers = [
      self.settings.connect(s, f, None) for (s, f) in signals]

  def deactivate_settings(self):
    map(self.settings.disconnect, self.settings_signal_handlers)
    self.settings_signal_handlers = []

  def do_create_configure_widget(self):
    widget = ConfigurationWidget(self.settings)
    return widget


class ConfigurationWidget(Gtk.VBox):
  TriggerKey = 'trigger'
  TriggerText = '<b>Autocompletion trigger:</b>'
  ScopeKey = 'scope'
  ScopeFrameText = '<b>Autocomplete using words from:</b>'
  ScopeDocText = 'The current document only'
  ScopeWinText = 'All open documents in the current window'
  ScopeAppText = 'All open documents in the application'
  OrderKey = 'order'
  OrderFrameText = '<b>Sort autocompletion list:</b>'
  OrderAlphaText = 'In alphabetical order'
  OrderProximityText = 'Based on distance from cursor'
  PromoteKey = 'promote'
  PromoteLastText = 'Promote last accepted match'

  def __init__(self, settings):
    Gtk.VBox.__init__(self)
    self.settings = settings 
    mainbox = Gtk.VBox()
    mainbox.set_border_width(10)
    mainbox.set_spacing(10)
    # Scope configuration
    frame = Gtk.Frame()
    frame.set_label(self.ScopeFrameText)
    frame.set_shadow_type(Gtk.ShadowType.NONE)
    frame.get_label_widget().set_use_markup(True)
    scope_box = Gtk.VBox(False, 0)
    scope_box.set_border_width(5)
    def scope_radio(text, scope, group=None):
      btn = Gtk.RadioButton.new_with_label_from_widget(group, text)
      btn.set_data(self.ScopeKey, scope)
      btn.set_active(self.settings.get_string(self.ScopeKey) == scope)
      btn.connect('toggled', self.scope_configuration_change, self.settings)
      scope_box.pack_start(btn, True, True, 0)
      return btn
    btn1 = scope_radio(self.ScopeDocText, 'document')
    btn2 = scope_radio(self.ScopeWinText, 'window', btn1)
    btn3 = scope_radio(self.ScopeAppText, 'application', btn2)
    frame.add(scope_box)
    mainbox.pack_start(frame, True, True, 0)
    # Order configuration
    frame = Gtk.Frame()
    frame.set_label(self.OrderFrameText)
    frame.set_shadow_type(Gtk.ShadowType.NONE)
    frame.get_label_widget().set_use_markup(True)
    order_box = Gtk.VBox(False, 0)
    order_box.set_border_width(5)
    def order_radio(text, order, group=None):
      btn = Gtk.RadioButton.new_with_label_from_widget(group, text)
      btn.set_data(self.OrderKey, order)
      btn.set_active(self.settings.get_string(self.OrderKey) == order)
      btn.connect('toggled', self.order_configuration_change, self.settings)
      order_box.pack_start(btn, True, True, 0)
      return btn
    btn1 = order_radio(self.OrderAlphaText, 'alphabetical')
    btn2 = order_radio(self.OrderProximityText, 'proximity', btn1)
    btn3 = Gtk.CheckButton(self.PromoteLastText)
    btn3.connect('toggled', self.promote_configuration_change, self.settings)
    btn3.set_active(self.settings.get_boolean(self.PromoteKey))
    order_box.pack_start(btn3, True, True, 0)
    frame.add(order_box)
    mainbox.pack_start(frame, True, True, 0)
    # Autocompletion trigger
    frame = Gtk.Frame()
    frame.set_shadow_type(Gtk.ShadowType.NONE)
    hbox = Gtk.HBox()
    hbox.set_spacing(10)
    label = Gtk.Label(self.TriggerText)
    label.set_use_markup(True)
    try:
      accel = self.settings.get_string(self.TriggerKey)
      self.trigger = Gtk.accelerator_parse(accel)
    except:
      self.trigger = DEFAULT_TRIGGER
    entry = Gtk.Entry()
    entry.set_text(self.get_trigger_display_text())
    entry.connect('key-press-event', self.on_trigger_entry_key_press)
    entry.connect('focus-in-event', self.on_trigger_entry_focus_in)
    entry.connect('focus-out-event', self.on_trigger_entry_focus_out)
    hbox.pack_start(label, True, True, 0)
    hbox.pack_start(entry, True, True, 0)
    frame.add(hbox)
    mainbox.pack_start(frame, True, True, 0)
    # Show
    self.pack_start(mainbox, True, True, 0)
    self.show_all()

  def on_trigger_entry_focus_in(self, entry, event):
    entry.set_text('Type a new shortcut')

  def on_trigger_entry_key_press(self, entry, event):
    if event.keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
      entry.set_text('')
      self.set_trigger(DEFAULT_TRIGGER)
    elif self.is_valid_trigger(event.keyval, event.state):
      modifiers = event.state & Gtk.accelerator_get_default_mod_mask() 
      self.set_trigger((event.keyval, modifiers))
      entry.set_text(self.get_trigger_display_text())
    elif event.keyval == Gdk.KEY_Tab:
      return False
    return True

  def on_trigger_entry_focus_out(self, entry, event):
    entry.set_text(self.get_trigger_display_text())

  def is_valid_trigger(self, keyval, mod):
    mod &= Gtk.accelerator_get_default_mod_mask()
    if keyval == Gdk.KEY_Escape:
      return True
    if mod and Gdk.keyval_to_unicode(keyval):
      return True
    valid_keysyms = [
      Gdk.KEY_Return,
      Gdk.KEY_Tab,
      Gdk.KEY_Left,
      Gdk.KEY_Right,
      Gdk.KEY_Up,
      Gdk.KEY_Down ]
    valid_keysyms.extend(range(Gdk.KEY_F1, Gdk.KEY_F12 + 1))
    return mod and keyval in valid_keysyms

  def set_trigger(self, trigger):
    if self.trigger != trigger:
      self.trigger = keyval, modifiers = trigger
      accelerator = Gtk.accelerator_name(keyval, modifiers or 0)
      self.settings.set_string(self.TriggerKey, accelerator)

  def get_trigger_display_text(self):
    display_text = None
    if self.trigger is not None:
      keyval, modifiers = self.trigger
      display_text = Gtk.accelerator_get_label(keyval, modifiers or 0)
    return display_text or ''

  def scope_configuration_change(self, widget, data=None):
    scope = widget.get_data(self.ScopeKey)
    if scope is not None and scope in AutoCompleter.ValidScopes:
      self.settings.set_string(self.ScopeKey, scope)

  def order_configuration_change(self, widget, data=None):
    order = widget.get_data(self.OrderKey)
    if order is not None and order in AutoCompleter.ValidOrders:
      self.settings.set_string(self.OrderKey, order)

  def promote_configuration_change(self, widget, data=None):
    self.settings.set_boolean(self.PromoteKey, widget.get_active())

# ex:ts=2:sw=2:et:
