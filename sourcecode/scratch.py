#!/usr/bin/env python


"""
    Pygments Tkinter example
    copyleft 2014 by Jens Diemer
    licensed under GNU GPL v3
"""

import os

try:
    # Python 3
    import tkinter
    from tkinter import font
    from tkinter import scrolledtext
except ImportError:
    # Python 2
    import Tkinter as tkinter
    import tkFont as font
    import ScrolledText as scrolledtext

from pygments.lexers.python import PythonLexer
from pygments.styles import get_style_by_name


class TkTest(object):
    def __init__(self, lexer):
        self.lexer = lexer

        self.root = tkinter.Tk()
        self.root.title("%s (%s)" % (lexer.name, os.path.basename(__file__)))

        self.text = scrolledtext.ScrolledText(
            master=self.root, height=30, width=120
        )
        self.text.pack(side=tkinter.LEFT, fill=tkinter.Y)

        self.root.bind("<Key>", self.event_key)

        self.root.bind('<Control-KeyPress-a>', self.event_select_all)
        self.root.bind('<Control-KeyPress-x>', self.event_cut)
        self.root.bind('<Control-KeyPress-c>', self.event_copy)
        self.root.bind('<Control-KeyPress-v>', self.event_paste)

        self.root.update()

        self.create_tags()

    def event_select_all(self, event=None):
        self.text.tag_add(tkinter.SEL, "1.0", tkinter.END)
        self.text.mark_set(tkinter.INSERT, "1.0")
        self.text.see(tkinter.INSERT)
        return "break"

    def event_cut(self, event=None):
        if self.text.tag_ranges(tkinter.SEL):
            self.event_copy()
            self.text.delete(tkinter.SEL_FIRST, tkinter.SEL_LAST)
            self.recolorize()
        return "break"

    def event_copy(self, event=None):
        if self.text.tag_ranges(tkinter.SEL):
            text = self.text.get(tkinter.SEL_FIRST, tkinter.SEL_LAST)
            self.clipboard_clear()
            self.clipboard_append(text)
        return "break"

    def paste(self, text):
        if text:
            self.text.insert(tkinter.INSERT, text)
            self.text.tag_remove(tkinter.SEL, '1.0', tkinter.END)
            self.text.see(tkinter.INSERT)
            self.recolorize()

    def event_paste(self, event=None):
        text = self.text.selection_get(selection='CLIPBOARD')
        self.paste(text)
        return "break"

    def event_key(self, event):
        keycode = event.keycode
        char = event.char
        print("\tkeycode %s - char %s" % (keycode, repr(char)))
        self.recolorize()

    def mainloop(self):
        self.root.mainloop()

    # ---------------------------------------------------------------------------------------

    def create_tags(self):
        bold_font = font.Font(self.text, self.text.cget("font"))
        bold_font.configure(weight=font.BOLD)

        italic_font = font.Font(self.text, self.text.cget("font"))
        italic_font.configure(slant=font.ITALIC)

        bold_italic_font = font.Font(self.text, self.text.cget("font"))
        bold_italic_font.configure(weight=font.BOLD, slant=font.ITALIC)

        style = get_style_by_name('default')
        for ttype, ndef in style:
            # print(ttype, ndef)
            tag_font = None
            if ndef['bold'] and ndef['italic']:
                tag_font = bold_italic_font
            elif ndef['bold']:
                tag_font = bold_font
            elif ndef['italic']:
                tag_font = italic_font

            if ndef['color']:
                foreground = "#%s" % ndef['color']
            else:
                foreground = None

            self.text.tag_configure(str(ttype), foreground=foreground, font=tag_font)

    def recolorize(self):
        print("recolorize")
        code = self.text.get("1.0", "end-1c")
        tokensource = self.lexer.get_tokens(code)

        start_line=1
        start_index = 0
        end_line=1
        end_index = 0
        for ttype, value in tokensource:
            if "\n" in value:
                end_line += value.count("\n")
                end_index = len(value.rsplit("\n",1)[1])
            else:
                end_index += len(value)

            if value not in (" ", "\n"):
                index1 = "%s.%s" % (start_line, start_index)
                index2 = "%s.%s" % (end_line, end_index)

                for tagname in self.text.tag_names(index1): # FIXME
                    self.text.tag_remove(tagname, index1, index2)

                # print(ttype, repr(value), index1, index2)
                self.text.tag_add(str(ttype), index1, index2)

            start_line = end_line
            start_index = end_index


    def removecolors(self):
        for tag in self.tagdefs:
            self.text.tag_remove(tag, "1.0", "end")


if __name__ == "__main__":
    tk_win = TkTest(lexer = PythonLexer())

    with open(__file__, "r") as f:
        tk_win.paste(f.read())

    tk_win.mainloop()