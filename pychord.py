#!/usr/bin/env python
#
# Copyright (c) 2010, Jonathan Perkin <jonathan@perkin.org.uk>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#

import getopt
import re
import string
import sys

from reportlab.platypus import *
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# load custom fonts from osx
#from reportlab.pdfbase import pdfmetrics
#from reportlab.pdfbase.ttfonts import TTFont
#pdfmetrics.registerFont(TTFont('GillSans', '/Library/Fonts/GillSans.ttc'))
#pdfmetrics.registerFont(TTFont('Georgia-Bold', '/Library/Fonts/Georgia Bold.ttf'))

CHORD_OUT = 0
CHORD_IN = 1
CHORD_FIN = 2

#
# PDF table style
#
chord_table_style = [
    ('ALIGN',         (1,1),   (-1,-1),  'LEFT'),
    ('LEFTPADDING',   (0,0),   (-1,-1),  0),
    ('RIGHTPADDING',  (0,0),   (-1,-1),  0),
    ('TOPPADDING',    (0,0),   (-1,-1),  0),
    ('BOTTOMPADDING', (0,0),   (-1,-1),  0),
    ('FONT',          (0,0),   (-1,0),  'Times-Bold',  10),
    ('FONT',          (0,-1),  (-1,-1), 'Times-Roman', 12),
]

def make_pdf_table(chords, text):
    """Take list of chords and text and return pdf table"""
    #
    # Always ensure there is at least one space between chords
    #
    idx = 0
    pairs = zip(chords, text)
    for c, t in pairs:
        if idx < (len(pairs) - 1):
            if len(c) > len(t):
                text[idx] += ' -'
            chords[idx] += ' '
            idx += 1
    data = [chords, text]
    t = Table(data, style=chord_table_style)
    return t

#
# Transposing algorithm taken from chordpack, licensed under the GPL, slightly
# modified by me to use a positive multiplier rather than negative.
#
#  - convert each chord to an offset
#  - record how many times each chord is seen
#  - use the chord_multiplier algorithm to calculate the most likely key,
#    based upon frequency of chords
#  - shift up/down the offset tree according to the required transposition
#
chord_to_offset = {
    'C':    0,
    'C#':   1,
    'Db':   1,
    'D':    2,
    'D#':   3,
    'Eb':   3,
    'E':    4,
    'F':    5,
    'F#':   6,
    'Gb':   6,
    'G':    7,
    'G#':   8,
    'Ab':   8,
    'A':    9,
    'A#':   10,
    'Bb':   10,
    'B':    11,
}
#
# Accidental normalisation
#
# [C]  [A/C#]  [Dm]  [Eb] [Em]  [F]  [D/F#] [G]  [E/G#]  [Am]  [Bb] [G/B]
# [D]  [B/D#]  [Em]  [F]  [F#m] [G]  [E/G#] [A]  [F#/A#] [Bm]  [C]  [A/C#]
# [F]  [D/F#]  [Gm]  [Ab] [Am]  [Bb] [G/B]  [C]  [A/C#]  [Dm]  [Eb] [C/E]
# [G]  [E/G#]  [Am]  [Bb] [Bm]  [C]  [A/C#] [D]  [B/D#]  [Em]  [F]  [D/F#]
# [A]  [F#/A#] [Bm]  [C]  [C#m] [D]  [B/D#] [E]  [C#/F]  [F#m] [G]  [E/G#]
# [Bb] [G/B]   [Cm]  [Db] [Dm]  [Eb] [C/E]  [F]  [D/F#]  [Gm]  [Ab] [F/A]
# [B]  [G#/C]  [C#m] [D]  [D#m] [E]  [C#/F] [F#] [D#/G]  [G#m] [A]  [F#/A#]
#
key_norm = ['b', '#', '#', 'b', '#', 'b', '#', '#', '#', '#', 'b', '#']

#
# Assign a chord multiplier
#
# For each offset that we try, apply a multiplier according to the likelyhood
# of that chord being the primary key, so e.g.
#
#   C/Am        = * 2
#   F/G/Dm/Em   = * 1
#   All others  = * 0
#
# This filters out unusual chords and leaves us with the most likely key having
# the largest result when multiplying the chord_count with the multiplier.
#
chord_multiplier = {}
for i in range(12):
    chord_multiplier["%s" % i]  = 0
    chord_multiplier["%sm" % i] = 0
chord_multiplier['0']  = 2
chord_multiplier['5']  = 1
chord_multiplier['7']  = 1
chord_multiplier['2m'] = 1
chord_multiplier['4m'] = 1
chord_multiplier['9m'] = 2

map_transpose_semitone = {
    'C#': 'D',
    'D#': 'E',
    'F#': 'G',
    'G#': 'A',
    'A#': 'B',
    'Db': 'D',
    'Eb': 'E',
    'Gb': 'G',
    'Ab': 'A',
    'Bb': 'B',
    'C':  'C#',
    'D':  'D#',
    'E':  'F',
    'F':  'F#',
    'G':  'G#',
    'A':  'A#',
    'B':  'C',
}

map_accidental_flat = {
    'C#': 'Db',
    'D#': 'Eb',
    'F#': 'Gb',
    'G#': 'Ab',
    'A#': 'Bb',
}

map_accidental_sharp = {
    'Db': 'C#',
    'Eb': 'D#',
    'Gb': 'F#',
    'Ab': 'G#',
    'Bb': 'A#',
}

class ChordError:
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class Chord:
    """A chord object"""

    def __init__(self, chord):
        #
        # Chord("abm7sus4/g#") =>
        #
        #  [Ab][m7sus4]/[G#]
        #
        #  root = Ab
        #  triad = m7sus4
        #  bass  = G#
        #
        #  minor = True
        #
        self.root = None
        self.triad = None
        self.bass = None
        self.bassrest = None
        self.minor = None

        c = re.match("^([(])?([A-Ga-g][b#]?)([^/]*)[/]?([A-Ga-g][b#]?)?(.*)$", chord)
        if not c:
            raise ChordError("Unable to parse '%s' as a valid chord" % chord)
        self.opening_brace = c.group(1)
        self.root = string.capitalize(c.group(2))
        if c.group(3):
            self.triad = c.group(3)
        if c.group(4):
            self.bass = string.capitalize(c.group(4))
        if c.group(5):
            self.bassrest = c.group(5)

        if self.triad:
            t = re.sub("maj", "", self.triad)
            if t.startswith("m"):
                self.minor = True

    def chord(self):
        ch = self.root
        if self.opening_brace:
            ch = "(%s" % (ch)
        if self.triad:
            ch += self.triad
        if self.bass:
            ch += "/%s" % self.bass
        if self.bassrest:
            ch += self.bassrest
        return ch

    def transpose(self, shift):
        while shift:
            self.root = map_transpose_semitone[self.root]
            if self.bass:
                self.bass = map_transpose_semitone[self.bass]
            shift -= 1

    def normalise(self, accidental):
        if accidental == 'b':
            map = map_accidental_flat
        else:
            map = map_accidental_sharp
        if self.root in map:
            self.root = map[self.root]
        if self.bass and self.bass in map:
            self.bass = map[self.bass]

#
# Parse each line
#
# [Em7]Hello, [Dsus4]why not try the [Em]ChordPro for[Am]mat
#
# Em7    Dsus4           Em          Am
# Hello, why not try the ChordPro format
#
def parse_file(file, format, transpose=None):
    out = ""
    title = ""
    subtitle = ""
    song = []

    with open(file) as f:
        text = f.readlines()

    #
    # For transposing, we:
    #
    #  - parse the entire text, extract a count of each chord seen, and
    #    calculate the most likely original key
    #  - parse the text again, transposing chords as requested
    #  - call parse() with our transposed text
    #
    if transpose:

        #
        # Count separately for each paragraph, so that we can correctly
        # handle key changes.
        #
        paragraphs = [{}]
        para_index = 0
        paragraphs[para_index]["chord_count"] = {}
        for i in range(12):
            paragraphs[para_index]["chord_count"]["%s" % i]  = 0
            paragraphs[para_index]["chord_count"]["%sm" % i] = 0

        for line in text:

            #
            # Whitespace, save current chord_count, reset and move to the next
            # paragraph.
            #
            if re.match("^\s*$", line):
                paragraphs.append({})
                para_index += 1
                paragraphs[para_index]["chord_count"] = {}
                for i in range(12):
                    paragraphs[para_index]["chord_count"]["%s" % i]  = 0
                    paragraphs[para_index]["chord_count"]["%sm" % i] = 0

            #
            # Split the line into a list, ['text', 'chord', ..], then slice the
            # list starting at list[1] and stepping two at a time to return
            # just the chords.  Mmm python.
            #
            chords = re.split("\[([^\]]*)\]", line)
            chords = chords[1::2]
            for chord in chords:
                chord = Chord(chord)
                minor = ""
                if chord.minor:
                    minor = "m"
                paragraphs[para_index]["chord_count"]["%s%s" % (chord_to_offset[chord.root], minor)] += 1

        #
        # We now have a chord count for each paragraph, go through them and
        # calculate the key
        #
        for p in paragraphs:

            #
            # Iterate through all possible keys, apply the chord_multipler to each
            # chord count, and calculate the total.  The key with the highest total
            # is the most likely original key.
            #
            bestvalue = 0
            bestkey = 0
            for key in range(12):
                value = 0
                for i in range(12):
                    value += chord_multiplier["%s" % ((i - key) % 12)] * p["chord_count"]["%s" % i]
                    value += chord_multiplier["%sm" % ((i - key) % 12)] * p["chord_count"]["%sm" % i]
                    if value > bestvalue:
                        bestvalue = value
                        bestkey = key

            # Dictionary object holding our best guess at the key
            p["key"] = bestkey
            p["val"] = bestvalue

        #
        # Calculate transposition shift based upon user input
        #
        shift = -1
        first_key = None
        for p in paragraphs:
            if p["key"] and not first_key:
                first_key = p["key"]
            if p["val"] > 0:
                shift = ((chord_to_offset[transpose] - p["key"]) % 12)
                break
        print first_key
        print transpose
        if transpose in key_norm:
            norm = key_norm[transpose]
        # Check for valid key
        elif transpose in chord_to_offset:
            norm = key_norm[chord_to_offset[transpose]]

        # XXX: norm needs to be what the new key will be, not original!

        #
        # We now have our best guess at the original key, and the requested
        # transposition.  Re-parse the text and apply the transposition.
        #
        # Likliest choice of b/# for the original key
        #
        para_index = 0
        transposed_text = []
        for line in text:
            #
            # Find key for this paragraph.  If it isn't the original, then
            # ignore the original transpose request and work out more natural
            # normalisation if new key is white notes-based.
            #
            pkey = paragraphs[para_index]["key"]
            if pkey and pkey != first_key:
                print "==> New %s (%s)" % (pkey, first_key)
                first_key = pkey
                if first_key in key_norm:
                    print "Switch to %s because of %s" % (key_norm[first_key], first_key)
                    norm = key_norm[first_key]
            #
            #norm = key_norm[(paragraphs[para_index]["key"] % 12)]

            #
            # Whitespace, move to next paragraph
            #
            if re.match("^\s*$", line):
                para_index += 1

            #
            # Split the line into a list of words,chords, iterate over
            # the chords and tranpose, then put everything back together
            #
            line = re.split("\[([^\]]*)\]", line)
            line_index = 1
            for chord in line[1::2]:
                if chord:
                    chord = Chord(chord)
                    chord.transpose(shift)
                    chord.normalise(norm)
                    line[line_index] = "[%s]" % chord.chord()
                line_index += 2
            newline = ""
            for l in line:
                newline += l
            transposed_text.append(newline)
        #
        # We have our transposed text, send it back through for output
        #
        parse(transposed_text)

    else:
        for line in text:

            line = line.rstrip('\n')

            # comments
            if line.startswith("#"):
                continue

            #
            # commands
            #
            if line.startswith("{"):
                command = line.strip("{} \t").split(":", 1)
                args = ""
                if len(command) > 1:
                    command, args = command

                if command in ["title", "t"]:
                    title = args
                    continue
                elif command in ["subtitle", "st"]:
                    subtitle = args
                    continue
                else:
                    print "Unsupported command %s" % (command)

            parts = re.split("\[([^\]]*)\]", line)
            #
            # To make these lists match up:
            #
            #  - if we start with a chord, skip the first blank text
            #  - if we start with text, prepend a blank chord
            #
            if line.startswith("["):
                song.append(make_pdf_table(parts[1::2], parts[2::2]))
            else:
                song.append(make_pdf_table([''] + parts[1::2], parts[0::2]))
            #
            # The rest of this is irrelevant for PDF generation
            #
            inside_chord = 0
            chord_pad = 0
            prev_chord_len = 0
            chord_line = ""
            text_line = ""
            for c in line:
                #
                # Start of chord.
                #
                if c == "[":
                    inside_chord = CHORD_IN
                    chord = ""

                    # If previous chord was longer than the text, pad the chord by
                    # a space to separate them, and pad the text to align.
                    if prev_chord_len and prev_chord_len >= chord_pad:
                        chord_line += " "

                        # If text_line ends with a space, pad with spaces, if not
                        # then assume we are in the middle of a word, so try to
                        # show that continuation.
                        if not text_line or text_line.endswith(" "):
                            text_line += " " * (prev_chord_len - chord_pad + 1)
                        else:
                            l = (prev_chord_len - chord_pad + 1)
                            if l % 2:
                                text_line += " " * (l / 2)
                            else:
                                text_line += " " * ((l / 2) - 1)
                            text_line += "-"
                            text_line += " " * (l / 2)

                    # if previous chord was shorter than the text, pad the chord
                    if prev_chord_len < chord_pad:
                        chord_line += " " * (chord_pad - prev_chord_len)

                    continue
                #
                # End of chord, save it and continue
                #
                if c == "]":

                    # Transpose if requested
                    #if transpose != 0:

                    chord_line += chord
                    prev_chord_len = len(chord)
                    chord = ""
                    chord_pad = 0
                    inside_chord = CHORD_OUT
                    continue
                #
                # Inside chord, keep saving it
                #
                if inside_chord == CHORD_IN:
                    chord += c
                #
                # Outside chord, save text and increase chord padding
                #
                else:
                    text_line += c
                    chord_pad += 1
            if chord_line:
                out += chord_line + "\n" + text_line + "\n"
            else:
                out += text_line + "\n"

    if format == "pdf":
        styles = getSampleStyleSheet()

        if subtitle:
            style = styles["Heading2"]
            style.alignment = TA_CENTER
            t = Paragraph(subtitle, style)
            song.insert(0, t)

        if title:
            style = styles['Heading1']
            style.alignment = TA_CENTER
            t = Paragraph(title, style)
            song.insert(0, t)

        doc = SimpleDocTemplate('song.pdf', pagesize=A4)
        doc.build(song)
    # Default to dumping to stdout
    else:
        print out

def usage():
    print "pychord.py [-t <transpose>] <file> ..."

def main():
    format = "text"
    transpose = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "f:ht:", ["format=", "help", "transpose="])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    output = None
    verbose = False
    for o, a in opts:
        if o in ("-f", "--format"):
            format = a
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-t", "--transpose"):
            transpose = a
        else:
            assert False, "unhandled option"

    for file in args:
        parse_file(file, format=format, transpose=transpose)

if __name__ == "__main__":
    main()
