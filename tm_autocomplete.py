# -*- coding: utf-8 -*-
#
# Gedit Plugin for TextMate style autocompletion. Tap Esc to cycle through 
# completions.
#
# Copyright © 2010, Kevin McGuinness <kevin.mcguinness@gmail.com>
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

__version__ = '1.0.1'
__author__ = 'Kevin McGuinness'

import gedit
import gtk
import re

class AutoCompleter(object):
  """Class that actually does the autocompletion"""

  WordRegex = re.compile(r'\w+')
  IgnoreUnderscore = True
  ValidScopes = ('document', 'window', 'application')

  __slots__ = (
    'doc',       # The document autocomplete was initiated on
    'word',      # Word being completed
    'matches',   # List of potential autocompletions
    'index',     # Index of the next autocompletion to suggest
    'iter_s',    # GtkTextIterator pointing to the start of word being completed
    'iter_i',    # GtkTextIterator pointing to insertion point
    'iter_e',    # GtkTextIterator pointing to end of last insertion
    'scope',     # Search scope (document|application|window)
  )

  def __init__(self, doc, scope='document'):
    """Create an autocompleter for the document. Indexes the words in the 
       current scope and builds a list of matches for the current cursor 
       position. Calling insert_next_completion will cycle through the matches,
       replacing the last match inserted (if any).
    """
    self.scope = scope
    self.reindex(doc)
    
  def _get_words(self, doc):
    """Returns all words in the current scope"""
    words = set()
    # Subfunction to index a single document
    def _index(document):
      text = document.get_text(
        document.get_start_iter(), 
        document.get_end_iter())
      words.update(self.WordRegex.findall(text))
    if self.scope == 'application':
      # Index all documents open in any gedit window
      map(_index, gedit.app_get_default().get_documents())
    elif self.scope == 'window':
      # Index all documents in this gedit window
      map(_index, gedit.app_get_default().get_active_window().get_documents())
    else:
      # Index just this document
      _index(doc)
    return words
      
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
        if ch.isalpha() or ch == '_':
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
    
  def _get_candidate_matches(self, doc, word):
    """Returns all words in the document that match the given word"""
    return [w for w in self._get_words(doc) if w.startswith(word) ]
    
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
      self.word = doc.get_text(self.iter_s, self.iter_i)
      self.matches = self._get_candidate_matches(doc, self.word)
      self.matches.sort()
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
      
      # Next completion
      self.index = self.index + 1 if self.index + 1 < len(self.matches) else 0
      
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
            
      # Update iterators
      self.iter_i = self.doc.get_iter_at_offset(insertion_point)
      self.iter_e = self.iter_i.copy()
      self.iter_s = self.iter_i.copy()
      self.iter_e.forward_chars(len(completion))
      self.iter_s.backward_chars(len(match))
      
      # Move cursor
      self.doc.place_cursor(self.iter_e)
      self.doc.end_user_action()
    return insert_ok
       

class AutoCompletionPlugin(gedit.Plugin):
  """TextMate style autocompletion plugin for Gedit"""

  def __init__(self):
    self.autocompleter = None
    self.trigger = gtk.keysyms.Escape
    self.scope = 'document'
    gedit.Plugin.__init__(self)
 
  def activate(self, window):
    self.update_ui(window)
    
  def deactivate(self, window):
    for view in window.get_views():
      for handler_id in getattr(view, 'autocomplete_handlers', []):
        view.disconnect(handler_id)
      setattr(view, 'autocomplete_handlers_attached', False)
    self.autocompleter = None   
    
  def update_ui(self, window):
    view = window.get_active_view()
    doc = window.get_active_document()
    if isinstance(view, gedit.View) and doc:
      if not getattr(view, 'autocomplete_handlers_attached', False):
        setattr(view, 'autocomplete_handlers_attached', True)
        self.autocompleter = None
        id1 = view.connect('key-press-event', self.on_key_press, doc)
        id2 = view.connect('button-press-event', self.on_button_press, doc)
        setattr(view, 'autocomplete_handlers', (id1, id2))
   
  def on_key_press(self, view, event, doc):
    if event.keyval == self.trigger:
      if not self.autocompleter:
        self.autocompleter = AutoCompleter(doc, self.scope)
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

