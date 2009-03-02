#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2009 Zuza Software Foundation
#
# This file is part of Virtaal.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.


import gobject
import gtk
from gobject import SIGNAL_RUN_FIRST, TYPE_NONE, TYPE_PYOBJECT, TYPE_STRING

from translate.misc.typecheck import accepts, Self, IsOneOf
from translate.storage.placeables import parse as elem_parse, placeables, StringElem


class StringElemGUI(object):
    """
    A convenient container for all GUI properties of a L{StringElem}.
    """

    # MEMBERS #
    fg = '#000000'
    """The current foreground colour."""
    bg = '#ffffff'
    """The current background colour."""

    cursor_allowed = True
    """Whether the cursor is allowed to enter this element."""


    # INITIALIZERS #
    def __init__(self, elem, textbox, **kwargs):
        if not isinstance(elem, StringElem):
            raise ValueError('"elem" parameter must be a StringElem.')
        if not isinstance(textbox, TextBox):
            raise ValueError('"textbox" parameter must be a TextBox.')
        self.elem = elem
        self.textbox = textbox
        self.marks = {}

        attribs = ('fg', 'bg', 'cursor_allowed')
        for kw in kwargs:
            if kw in attribs:
                setattr(self, kw, kwargs[kw])

    # METHODS #
    def create_tag(self):
        tag = gtk.TextTag()
        if self.fg:
            tag.props.foreground = self.fg

        if self.bg:
            tag.props.background = self.bg

        return tag

    def copy(self):
        return StringElemGUI(
            elem=self.elem, textbox=self.textbox,
            fg=self.fg, bg=self.bg,
            cursor_allowed=self.cursor_allowed
        )


class XMLEntityGUI(StringElemGUI):
    fg = '#ffffff'
    bg = '#0000ff'


class XMLTagGUI(StringElemGUI):
    fg = '#ffffff'
    bg = '#550099'


element_gui_map = {
    placeables.XMLEntityPlaceable: XMLEntityGUI,
    placeables.XMLTagPlaceable:    XMLTagGUI,
}


class TextBox(gtk.TextView):
    """
    A C{gtk.TextView} extended to work with our nifty L{StringElem} parsed
    strings.
    """

    __gtype_name__ = 'TextBox'
    __gsignals__ = {
        'after-apply-tags': (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_PYOBJECT,)),
        'before-apply-tags': (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_PYOBJECT,)),
        'key-pressed': (SIGNAL_RUN_FIRST, TYPE_NONE, (TYPE_PYOBJECT, TYPE_STRING)),
    }

    SPECIAL_KEYS = {
        'alt-down': [(gtk.keysyms.Down, gtk.gdk.MOD1_MASK)],
        'enter':    [(gtk.keysyms.Return, None), (gtk.keysyms.KP_Enter, None)],
    }
    """A table of name-keybinding mappings. The name (key) is passed as the
    second parameter to the 'key-pressed' event."""

    # INITIALIZERS #
    def __init__(self):
        super(TextBox, self).__init__()
        self.buffer = self.get_buffer()
        self.elem = None
        self.selected_elem = None
        self.selected_elem_index = 0
        self.__connect_default_handlers()

    def __connect_default_handlers(self):
        self.connect('key-press-event', self._on_key_pressed)
        self.buffer.connect('changed', self._on_changed)
        self.buffer.connect('insert-text', self._on_insert_text)
        self.buffer.connect('delete-range', self._on_delete_range)


    # OVERRIDDEN METHODS #
    def get_stringelem(self):
        return elem_parse(self.get_text())

    def get_text(self, start_iter=None, end_iter=None):
        """Return the text rendered in this text box.
            Uses C{gtk.TextBuffer.get_text()}."""
        if start_iter is None:
            start_iter = self.buffer.get_start_iter()
        if end_iter is None:
            end_iter = self.buffer.get_end_iter()
        return self.buffer.get_text(start_iter, end_iter)

    @accepts(Self(), [[IsOneOf(StringElem, str, unicode)]])
    def set_text(self, text):
        """Set the text rendered in this text box.
            Uses C{gtk.TextBuffer.set_text()}.
            @type  text: str|unicode|L{StringElem}
            @param text: The text to render in this text box."""
        self.buffer.set_text(unicode(text))
        self.update_tree(text)


    # METHODS #
    @accepts(Self(), [StringElem])
    def add_default_gui_info(self, elem):
        """Add default GUI info to string elements in the tree that does not
            have any GUI info.

            Only leaf nodes are (currently) extended with a C{StringElemGUI}
            (or sub-class) instance. Other nodes has C{gui_info} set to C{None}.

            @type  elem: StringElem
            @param elem: The root of the string element tree to add default
                GUI info to.
            """
        if not isinstance(elem, StringElem):
            return

        if not hasattr(elem, 'gui_info') or not elem.gui_info:
            if  len(elem.subelems) == 1 and isinstance(elem.subelems[0], basestring):
                gui_info_class = element_gui_map.get(elem.__class__, StringElemGUI)
                elem.gui_info = gui_info_class(elem=elem, textbox=self)
            else:
                # Do we need default UI info for non-leaf nodes?
                elem.gui_info = None

        for sub in elem.subelems:
            self.add_default_gui_info(sub)

    @accepts(Self(), [StringElem, bool])
    def apply_tags(self, elem, include_subtree=True):
        offset = self.elem.find(elem) or 0
        #print '[%s] at offset %d' % (unicode(elem).encode('utf-8'), offset)
        self.emit('before-apply-tags', elem)

        iters = (
            self.buffer.get_iter_at_offset(offset),
            self.buffer.get_iter_at_offset(offset + len(elem))
        )
        if getattr(elem, 'gui_info', None):
            tag = elem.gui_info.create_tag()
            if tag:
                self.buffer.get_tag_table().add(tag)
                self.buffer.apply_tag(tag, iters[0], iters[1])

        if include_subtree:
            for sub in elem.subelems:
                if isinstance(sub, StringElem):
                    self.apply_tags(sub)

        self.emit('after-apply-tags', elem)

    @accepts(Self(), [[StringElem, None], [int, None]])
    def select_elem(self, elem=None, offset=None):
        if elem is None and offset is None:
            raise ValueError('Either "elem" or "offset" must be specified.')

        all_elems = self.elem.depth_first()
        if elem is None and offset is not None:
            return self.select_elem(elem=self.elem.depth_first()[offset % len(all_elems)])

        if not elem in all_elems:
            return

        # Reset the default tag for the previously selected element
        if self.selected_elem:
            self.selected_elem.gui_info = None
            self.add_default_gui_info(self.selected_elem)
            self.apply_tags(self.selected_elem)

        self.selected_elem = elem
        self.selected_elem_index = all_elems.index(elem)
        print 'Selected element is now %s' % (elem)
        elem.gui_info = StringElemGUI(elem, self, fg='#ff0000', bg='#000000')
        self.apply_tags(elem, include_subtree=False)

    @accepts(Self(), [[StringElem, basestring]])
    def update_tree(self, text=None):
        if text is None:
            text = self.get_text()
        if not isinstance(text, StringElem):
            text = elem_parse(text)
            self.add_default_gui_info(text)
        self.elem = text

        tagtable = self.buffer.get_tag_table()
        def remtag(tag, data):
            tagtable.remove(tag)
        tagtable.foreach(remtag)
        # At this point we have a tree of string elements with GUI info.
        self.apply_tags(text)

    def __delayed_update_tree(self):
        gobject.idle_add(self.update_tree)

    @accepts(Self(), [int])
    def __move_elem_selection(self, offset):
        self.select_elem(offset=self.selected_elem_index + offset)


    # EVENT HANDLERS #
    def _on_changed(self, buffer):
        pass

    def _on_delete_range(self, buffer, start_iter, end_iter):
        if not self.elem:
            return

        for i in (start_iter.get_offset(), end_iter.get_offset()-1):
            elem = self.elem.elem_at_offset(i)
            if not elem:
                continue
            if self.elem and not elem.iseditable:
                self.buffer.stop_emission('delete-range')
                return True

        self.__delayed_update_tree()

    def _on_insert_text(self, buffer, iter, ins_text, length):
        if not self.elem:
            return

        elem = self.elem.elem_at_offset(iter.get_offset())
        if not elem:
            return
        if iter.get_offset() == self.elem.elem_offset(elem):
            return

        if self.elem and not elem.iseditable:
            self.buffer.stop_emission('insert-text')
            return True

        self.__delayed_update_tree()

    def _on_key_pressed(self, widget, event, *args):
        evname = None
        # Alt-Left
        if event.keyval == gtk.keysyms.Left and event.state & gtk.gdk.MOD1_MASK:
            self.__move_elem_selection(-1)
        # Alt-Right
        elif event.keyval == gtk.keysyms.Right and event.state & gtk.gdk.MOD1_MASK:
            self.__move_elem_selection(1)

        for name, keyslist in self.SPECIAL_KEYS.items():
            for keyval, state in keyslist:
                if event.keyval == keyval and event.state & state:
                    evname = name
        self.emit('key-pressed', event, name)
