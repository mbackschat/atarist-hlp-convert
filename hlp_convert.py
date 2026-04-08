#!/usr/bin/env python3
# /// script
# requires-python = ">=3.6"
# ///
"""
hlp_convert.py - Convert Borland Help System 2.0 (.HLP) files to HTML, Markdown,
or plain text.

Decodes the nibble-compressed, XOR-encrypted help files used by Pure C / Turbo C
on the Atari ST (circa 1989-1992).

Usage:
    python3 hlp_convert.py [options] <input.hlp> [output]

Options:
    --format html   Output as HTML with CSS styling and clickable links (default)
    --format md     Output as Markdown with link references
    --format txt    Output as plain text, optimized for LLM consumption
    --all           Convert all .HLP files in the input directory
    --keywords      Include keyword index (default: yes)
    --no-keywords   Exclude keyword index
    --raw           Don't convert Atari ST charset to UTF-8

If output is omitted, it is derived from the input filename with the appropriate
extension (.html, .md, or .txt).

Format: Borland "Help System Version 2.0", magic 0xBD + "90BH2.0"
Reference: https://github.com/th-otto/pc_help
"""

import struct
import sys
import os
import argparse
import html as html_module

# ---------------------------------------------------------------------------
# Constants (from hcint.h)
# ---------------------------------------------------------------------------

HC_ENCRYPT = 0xA3
ESC_CHR = 0x1D
CHAR_DIR = 0x0C
STR_TABLE = 0x0D
STR_NEWLINE = 0x0E
CHAR_EMPTY = 0x0F
LINK_EXTERNAL = 0xFFFF
HLPHDR_SIZE = 136
HC_MAGIC = b'\xbd90BH2.0'

# ---------------------------------------------------------------------------
# Atari ST character set -> Unicode mapping (bytes 0x80-0xFF)
# ---------------------------------------------------------------------------

ATARI_TO_UNICODE = {
    0x80: '\u00C7',  # C-cedilla
    0x81: '\u00FC',  # u-umlaut
    0x82: '\u00E9',  # e-acute
    0x83: '\u00E2',  # a-circumflex
    0x84: '\u00E4',  # a-umlaut
    0x85: '\u00E0',  # a-grave
    0x86: '\u00E5',  # a-ring
    0x87: '\u00E7',  # c-cedilla
    0x88: '\u00EA',  # e-circumflex
    0x89: '\u00EB',  # e-dieresis
    0x8A: '\u00E8',  # e-grave
    0x8B: '\u00EF',  # i-dieresis
    0x8C: '\u00EE',  # i-circumflex
    0x8D: '\u00EC',  # i-grave
    0x8E: '\u00C4',  # A-umlaut
    0x8F: '\u00C5',  # A-ring
    0x90: '\u00C9',  # E-acute
    0x91: '\u00E6',  # ae-ligature
    0x92: '\u00C6',  # AE-ligature
    0x93: '\u00F4',  # o-circumflex
    0x94: '\u00F6',  # o-umlaut
    0x95: '\u00F2',  # o-grave
    0x96: '\u00FB',  # u-circumflex
    0x97: '\u00F9',  # u-grave
    0x98: '\u00FF',  # y-dieresis
    0x99: '\u00D6',  # O-umlaut
    0x9A: '\u00DC',  # U-umlaut
    0x9B: '\u00A2',  # cent sign
    0x9C: '\u00A3',  # pound sign
    0x9D: '\u00A5',  # yen sign
    0x9E: '\u00DF',  # sharp-s (Eszett)
    0x9F: '\u0192',  # f-hook (florin)
    0xA0: '\u00E1',  # a-acute
    0xA1: '\u00ED',  # i-acute
    0xA2: '\u00F3',  # o-acute
    0xA3: '\u00FA',  # u-acute
    0xA4: '\u00F1',  # n-tilde
    0xA5: '\u00D1',  # N-tilde
    0xA6: '\u00AA',  # feminine ordinal
    0xA7: '\u00BA',  # masculine ordinal
    0xA8: '\u00BF',  # inverted question mark
    0xA9: '\u2310',  # reversed not sign
    0xAA: '\u00AC',  # not sign
    0xAB: '\u00BD',  # one-half
    0xAC: '\u00BC',  # one-quarter
    0xAD: '\u00A1',  # inverted exclamation
    0xAE: '\u00AB',  # left guillemet
    0xAF: '\u00BB',  # right guillemet
    0xB0: '\u00E3',  # a-tilde
    0xB1: '\u00F5',  # o-tilde
    0xB2: '\u00D8',  # O-stroke
    0xB3: '\u00F8',  # o-stroke
    0xB4: '\u0153',  # oe-ligature
    0xB5: '\u0152',  # OE-ligature
    0xB6: '\u00C0',  # A-grave
    0xB7: '\u00C3',  # A-tilde
    0xB8: '\u00D5',  # O-tilde
    0xB9: '\u00A8',  # dieresis
    0xBA: '\u00B4',  # acute accent
    0xBB: '\u2020',  # dagger
    0xBC: '\u00B6',  # pilcrow
    0xBD: '\u00A9',  # copyright
    0xBE: '\u00AE',  # registered
    0xBF: '\u2122',  # trademark
    0xC0: '\u0133',  # ij-ligature
    0xC1: '\u0132',  # IJ-ligature
    0xC2: '\u05D0',  # Hebrew alef
    0xC3: '\u05D1',  # Hebrew bet
    0xC4: '\u05D2',  # Hebrew gimel
    0xC5: '\u05D3',  # Hebrew dalet
    0xC6: '\u05D4',  # Hebrew he
    0xC7: '\u05D5',  # Hebrew vav
    0xC8: '\u05D6',  # Hebrew zayin
    0xC9: '\u05D7',  # Hebrew het
    0xCA: '\u05D8',  # Hebrew tet
    0xCB: '\u05D9',  # Hebrew yod
    0xCC: '\u05DB',  # Hebrew kaf
    0xCD: '\u05DC',  # Hebrew lamed
    0xCE: '\u05DE',  # Hebrew mem
    0xCF: '\u05E0',  # Hebrew nun
    0xD0: '\u05E1',  # Hebrew samekh
    0xD1: '\u05E2',  # Hebrew ayin
    0xD2: '\u05E4',  # Hebrew pe
    0xD3: '\u05E6',  # Hebrew tsadi
    0xD4: '\u05E7',  # Hebrew qof
    0xD5: '\u05E8',  # Hebrew resh
    0xD6: '\u05E9',  # Hebrew shin
    0xD7: '\u05EA',  # Hebrew tav
    0xD8: '\u05DA',  # Hebrew final kaf
    0xD9: '\u05DD',  # Hebrew final mem
    0xDA: '\u05DF',  # Hebrew final nun
    0xDB: '\u05E3',  # Hebrew final pe
    0xDC: '\u05E5',  # Hebrew final tsadi
    0xDD: '\u00A7',  # section sign
    0xDE: '\u2227',  # logical and
    0xDF: '\u221E',  # infinity
    0xE0: '\u03B1',  # alpha
    0xE1: '\u00DF',  # sharp-s (duplicate)
    0xE2: '\u0393',  # Gamma
    0xE3: '\u03C0',  # pi
    0xE4: '\u03A3',  # Sigma
    0xE5: '\u03C3',  # sigma
    0xE6: '\u00B5',  # micro sign
    0xE7: '\u03C4',  # tau
    0xE8: '\u03A6',  # Phi
    0xE9: '\u0398',  # Theta
    0xEA: '\u03A9',  # Omega
    0xEB: '\u03B4',  # delta
    0xEC: '\u222E',  # contour integral
    0xED: '\u03C6',  # phi
    0xEE: '\u2208',  # element of
    0xEF: '\u2229',  # intersection
    0xF0: '\u2261',  # identical to
    0xF1: '\u00B1',  # plus-minus
    0xF2: '\u2265',  # greater-than or equal
    0xF3: '\u2264',  # less-than or equal
    0xF4: '\u2320',  # top half integral
    0xF5: '\u2321',  # bottom half integral
    0xF6: '\u00F7',  # division sign
    0xF7: '\u2248',  # almost equal
    0xF8: '\u00B0',  # degree sign
    0xF9: '\u2022',  # bullet
    0xFA: '\u00B7',  # middle dot
    0xFB: '\u221A',  # square root
    0xFC: '\u207F',  # superscript n
    0xFD: '\u00B2',  # superscript 2
    0xFE: '\u25A0',  # black square
    0xFF: '\u00A0',  # non-breaking space
}


def atari_to_utf8(byte_val):
    """Convert an Atari ST character byte to a Unicode character."""
    if byte_val < 0x80:
        return chr(byte_val)
    return ATARI_TO_UNICODE.get(byte_val, chr(byte_val))


# ---------------------------------------------------------------------------
# HLP file parser
# ---------------------------------------------------------------------------

class HLPFile:
    """Parser for Borland Help System 2.0 (.HLP) files."""

    def __init__(self, filepath, raw_charset=False):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.raw_charset = raw_charset

        with open(filepath, 'rb') as f:
            self.data = f.read()

        self._parse_header()
        self._read_screen_table()
        self._read_string_table()
        self._read_keyword_tables()

    def _read_u32(self, offset):
        return struct.unpack('>I', self.data[offset:offset + 4])[0]

    def _read_u16(self, offset):
        return struct.unpack('>H', self.data[offset:offset + 2])[0]

    def _read_i32(self, offset):
        return struct.unpack('>i', self.data[offset:offset + 4])[0]

    def _parse_header(self):
        if len(self.data) < HLPHDR_SIZE:
            raise ValueError(f"File too small ({len(self.data)} bytes)")

        magic = self.data[0x50:0x58]
        if magic != HC_MAGIC:
            raise ValueError(f"Bad magic: {magic!r} (expected {HC_MAGIC!r})")

        self.copyright = self.data[0:80].split(b'\x00')[0].decode('latin-1').strip()
        self.scr_tab_size = self._read_u32(0x58)
        self.str_offset = self._read_u32(0x5C)
        self.str_size = self._read_u32(0x60)
        self.char_table = self.data[0x64:0x70]
        self.caps_offset = self._read_u32(0x70)
        self.caps_size = self._read_u32(0x74)
        self.caps_cnt = self._read_u32(0x78)
        self.sens_offset = self._read_u32(0x7C)
        self.sens_size = self._read_u32(0x80)
        self.sens_cnt = self._read_u32(0x84)
        self.screen_cnt = self.scr_tab_size // 4 - 1

    def _read_screen_table(self):
        self.screen_table = []
        for i in range(self.screen_cnt + 1):
            off = HLPHDR_SIZE + i * 4
            self.screen_table.append(self._read_u32(off))

    def _read_string_table(self):
        self.string_tab = self.data[self.str_offset:self.str_offset + self.str_size]

    def _read_keyword_tables(self):
        self.keywords = []  # list of (keyword_str, screen_no, attr, table_type)
        self._read_keyword_table(self.caps_offset, self.caps_size, self.caps_cnt, 'caps')
        self._read_keyword_table(self.sens_offset, self.sens_size, self.sens_cnt, 'sens')

    def _read_keyword_table(self, offset, size, count, table_type):
        if count == 0 or size == 0:
            return
        for i in range(count):
            entry_off = offset + i * 6
            pos = self._read_i32(entry_off)
            code = self._read_u16(entry_off + 4)
            screen_no = ((code >> 3) & 0xFFF) - 1
            attr = code & 0x7

            str_pos = entry_off + pos
            end = self.data.index(0, str_pos)
            keyword = self.data[str_pos:end].decode('latin-1')
            self.keywords.append((keyword, screen_no, attr, table_type))

    def decode_screen(self, index):
        """Decode a screen and return raw bytes (Atari ST encoding)."""
        if index >= self.screen_cnt:
            return b''
        start = self.screen_table[index]
        end = self.screen_table[index + 1]
        coded = self.data[start:end]

        pos = 0
        must_read = True
        byte_read = 0
        result = bytearray()

        def get_nibble():
            nonlocal pos, must_read, byte_read
            if must_read:
                if pos >= len(coded):
                    return CHAR_EMPTY
                byte_read = coded[pos]
                pos += 1
                must_read = False
                return byte_read >> 4
            else:
                must_read = True
                return byte_read & 0x0F

        def get_byte():
            return (get_nibble() << 4) | get_nibble()

        while pos <= len(coded):
            nibble = get_nibble()

            if nibble < CHAR_DIR:
                result.append(self.char_table[nibble])
            elif nibble == CHAR_DIR:
                result.append(get_byte())
            elif nibble == STR_TABLE:
                idx = (get_byte() << 4) | get_nibble()
                try:
                    str_off = self._read_u32_buf(self.string_tab, idx * 4)
                    str_end = self._read_u32_buf(self.string_tab, (idx + 1) * 4)
                    length = str_end - str_off
                    for j in range(length):
                        result.append(self.string_tab[str_off + j] ^ HC_ENCRYPT)
                except (IndexError, struct.error):
                    pass
            elif nibble == STR_NEWLINE:
                result.append(0x0D)
                result.append(0x0A)
            else:  # CHAR_EMPTY or unknown -> end
                break

        return bytes(result)

    @staticmethod
    def _read_u32_buf(buf, offset):
        return struct.unpack('>I', buf[offset:offset + 4])[0]

    def get_screen_name(self, index):
        """Try to find a name for a screen from keywords."""
        for keyword, scr_no, attr, _ in self.keywords:
            if scr_no == index and attr == 0:  # SCR_NAME
                return keyword
        return None


# ---------------------------------------------------------------------------
# Charset conversion for raw byte spans (outside of link codes)
# ---------------------------------------------------------------------------

def _raw_bytes_to_text(raw, raw_charset=False):
    """Convert raw decoded bytes to a Unicode string, stripping CR."""
    if raw_charset:
        return raw.decode('latin-1')
    chars = []
    for b in raw:
        if b == 0x0D:
            continue
        elif b == 0x0A:
            chars.append('\n')
        elif b < 0x20 and b != 0x09:
            chars.append(chr(b))
        else:
            chars.append(atari_to_utf8(b))
    return ''.join(chars)


# ---------------------------------------------------------------------------
# Link parser - extracts cross-references from raw decoded bytes
# ---------------------------------------------------------------------------

def parse_links(raw, raw_charset=False):
    """Parse raw decoded bytes and split into segments of plain text and links.

    Operates on raw bytes so that the 2-byte screen codes embedded after
    ESC_CHR are read before any charset conversion can mangle them.

    Returns a list of tuples:
        ('text', string)           - plain text segment (already Unicode)
        ('link', screen_no, attr, display_text)  - cross-reference
        ('extlink', display_text)  - external link (to another .HLP file)
    """
    segments = []
    i = 0
    while i < len(raw):
        esc_pos = raw.find(ESC_CHR, i)
        if esc_pos == -1:
            segments.append(('text', _raw_bytes_to_text(raw[i:], raw_charset)))
            break

        if esc_pos > i:
            segments.append(('text', _raw_bytes_to_text(raw[i:esc_pos], raw_charset)))

        # Parse link: ESC + 2-byte code + display_text + ESC
        j = esc_pos + 1
        if j + 2 > len(raw):
            segments.append(('text', _raw_bytes_to_text(raw[esc_pos:], raw_charset)))
            break

        code_hi = raw[j]
        code_lo = raw[j + 1]
        code = (code_hi << 8) | code_lo
        j += 2

        # Find end ESC
        end_esc = raw.find(ESC_CHR, j)
        if end_esc == -1:
            display_text = _raw_bytes_to_text(raw[j:], raw_charset)
            i = len(raw)
        else:
            display_text = _raw_bytes_to_text(raw[j:end_esc], raw_charset)
            i = end_esc + 1

        if code == LINK_EXTERNAL:
            segments.append(('extlink', display_text))
        else:
            screen_no = ((code >> 3) & 0xFFF) - 1
            attr = code & 0x7
            segments.append(('link', screen_no, attr, display_text))

        continue

    return segments


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------

def screen_anchor(index):
    return f"screen-{index}"


def generate_html(hlp, include_keywords=True):
    """Generate a complete HTML document from an HLP file."""
    lines = []
    lines.append('<!DOCTYPE html>')
    lines.append('<html lang="de">')
    lines.append('<head>')
    lines.append('<meta charset="utf-8">')
    lines.append(f'<title>{html_module.escape(hlp.filename)} - Borland Help</title>')
    lines.append('<style>')
    lines.append('''
body {
    font-family: "Courier New", Courier, monospace;
    background: #f5f5dc;
    color: #1a1a1a;
    max-width: 80em;
    margin: 2em auto;
    padding: 0 2em;
    font-size: 14px;
    line-height: 1.4;
}
h1 { font-size: 1.5em; border-bottom: 2px solid #333; padding-bottom: 0.3em; }
h2 { font-size: 1.2em; margin-top: 2em; border-bottom: 1px solid #999; }
.screen {
    border: 1px solid #ccc;
    background: #fff;
    padding: 1em;
    margin: 1em 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.screen-header {
    background: #2c5f8a;
    color: #fff;
    padding: 0.3em 0.6em;
    margin: 2em 0 0 0;
    font-weight: bold;
}
a { color: #2c5f8a; }
a:hover { color: #c0392b; }
.extlink { color: #8e44ad; font-style: italic; }
.keyword-table { border-collapse: collapse; width: 100%; margin: 1em 0; }
.keyword-table th, .keyword-table td {
    border: 1px solid #ccc; padding: 0.3em 0.6em; text-align: left;
}
.keyword-table th { background: #eee; }
.toc { column-count: 3; column-gap: 2em; margin: 1em 0; }
.toc a { display: block; padding: 0.1em 0; }
.info { color: #666; font-size: 0.9em; margin: 1em 0; }
''')
    lines.append('</style>')
    lines.append('</head>')
    lines.append('<body>')

    # Title
    lines.append(f'<h1>{html_module.escape(hlp.filename)}</h1>')
    lines.append(f'<p class="info">{html_module.escape(hlp.copyright)}<br>')
    lines.append(f'{hlp.screen_cnt} screens, {len(hlp.keywords)} keywords, ')
    lines.append(f'{len(hlp.data):,} bytes</p>')

    # Table of contents
    lines.append('<h2>Table of Contents</h2>')
    lines.append('<div class="toc">')
    for i in range(hlp.screen_cnt):
        name = hlp.get_screen_name(i)
        label = name if name else f"Screen {i}"
        lines.append(f'<a href="#{screen_anchor(i)}">{html_module.escape(label)}</a>')
    lines.append('</div>')

    # Keyword index
    if include_keywords and hlp.keywords:
        lines.append('<h2>Keyword Index</h2>')
        lines.append('<table class="keyword-table">')
        lines.append('<tr><th>Keyword</th><th>Screen</th><th>Type</th></tr>')
        for keyword, scr_no, attr, table_type in sorted(hlp.keywords, key=lambda x: x[0].lower()):
            attr_names = {0: 'name', 1: 'caps', 2: 'insensitive', 3: 'link'}
            lines.append(f'<tr><td><a href="#{screen_anchor(scr_no)}">'
                         f'{html_module.escape(keyword)}</a></td>'
                         f'<td>{scr_no}</td>'
                         f'<td>{attr_names.get(attr, str(attr))}</td></tr>')
        lines.append('</table>')

    # Screens
    lines.append('<h2>Help Screens</h2>')
    for i in range(hlp.screen_cnt):
        name = hlp.get_screen_name(i)
        label = f"Screen {i}"
        if name:
            label += f" - {name}"

        lines.append(f'<div class="screen-header" id="{screen_anchor(i)}">{html_module.escape(label)}</div>')
        lines.append('<div class="screen">')

        raw = hlp.decode_screen(i)
        segments = parse_links(raw, hlp.raw_charset)

        for seg in segments:
            if seg[0] == 'text':
                lines.append(html_module.escape(seg[1]))
            elif seg[0] == 'link':
                _, scr_no, attr, display = seg
                escaped = html_module.escape(display)
                lines.append(f'<a href="#{screen_anchor(scr_no)}">{escaped}</a>')
            elif seg[0] == 'extlink':
                escaped = html_module.escape(seg[1])
                lines.append(f'<span class="extlink" title="External: {escaped}">{escaped}</span>')

        lines.append('</div>')

    lines.append('</body>')
    lines.append('</html>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def generate_markdown(hlp, include_keywords=True):
    """Generate a Markdown document from an HLP file."""
    lines = []

    lines.append(f'# {hlp.filename}')
    lines.append('')
    lines.append(f'*{hlp.copyright}*  ')
    lines.append(f'{hlp.screen_cnt} screens, {len(hlp.keywords)} keywords, '
                 f'{len(hlp.data):,} bytes')
    lines.append('')

    # Table of contents
    lines.append('## Table of Contents')
    lines.append('')
    for i in range(hlp.screen_cnt):
        name = hlp.get_screen_name(i)
        label = name if name else f"Screen {i}"
        lines.append(f'- [{label}](#{screen_anchor(i)})')
    lines.append('')

    # Keyword index
    if include_keywords and hlp.keywords:
        lines.append('## Keyword Index')
        lines.append('')
        lines.append('| Keyword | Screen | Type |')
        lines.append('|---------|--------|------|')
        attr_names = {0: 'name', 1: 'caps', 2: 'insensitive', 3: 'link'}
        for keyword, scr_no, attr, table_type in sorted(hlp.keywords, key=lambda x: x[0].lower()):
            lines.append(f'| [{keyword}](#{screen_anchor(scr_no)}) '
                         f'| {scr_no} | {attr_names.get(attr, str(attr))} |')
        lines.append('')

    # Screens
    lines.append('## Help Screens')
    lines.append('')
    for i in range(hlp.screen_cnt):
        name = hlp.get_screen_name(i)
        label = f"Screen {i}"
        if name:
            label += f" - {name}"

        lines.append(f'### <a id="{screen_anchor(i)}"></a>{label}')
        lines.append('')
        lines.append('```')

        raw = hlp.decode_screen(i)
        segments = parse_links(raw, hlp.raw_charset)

        # In the code block, we can't have real links, so we annotate them
        plain_parts = []
        for seg in segments:
            if seg[0] == 'text':
                plain_parts.append(seg[1])
            elif seg[0] == 'link':
                _, scr_no, attr, display = seg
                plain_parts.append(display)
            elif seg[0] == 'extlink':
                plain_parts.append(f'{seg[1]} [external]')
        lines.append(''.join(plain_parts))

        lines.append('```')
        lines.append('')

        # Add link references below the code block
        has_links = any(s[0] in ('link', 'extlink') for s in segments)
        if has_links:
            lines.append('Links: ')
            seen = set()
            for seg in segments:
                if seg[0] == 'link':
                    _, scr_no, attr, display = seg
                    key = (scr_no, display)
                    if key not in seen:
                        seen.add(key)
                        target_name = hlp.get_screen_name(scr_no) or f"Screen {scr_no}"
                        lines.append(f'  [{display}](#{screen_anchor(scr_no)}) -> {target_name}')
                elif seg[0] == 'extlink':
                    lines.append(f'  {seg[1]} *(external reference)*')
            lines.append('')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Plain text output (LLM-friendly)
# ---------------------------------------------------------------------------

def generate_text(hlp, include_keywords=True):
    """Generate a plain text document optimized for LLM consumption.

    - No markup, no fences, no decoration
    - Sections separated by clear headers
    - Cross-references inlined as "Display Text (see: Topic Name)"
    - Keyword index as a flat lookup list
    """
    lines = []

    lines.append(f'{hlp.filename}')
    lines.append(f'{hlp.copyright}')
    lines.append(f'{hlp.screen_cnt} screens, {len(hlp.keywords)} keywords')
    lines.append('')

    # Build a screen_no -> name map for resolving link targets
    screen_names = {}
    for keyword, scr_no, attr, _ in hlp.keywords:
        if attr == 0 and scr_no not in screen_names:
            screen_names[scr_no] = keyword

    # Keyword index
    if include_keywords and hlp.keywords:
        lines.append('=' * 70)
        lines.append('KEYWORD INDEX')
        lines.append('=' * 70)
        lines.append('')
        for keyword, scr_no, attr, table_type in sorted(hlp.keywords, key=lambda x: x[0].lower()):
            target = screen_names.get(scr_no, f'Screen {scr_no}')
            if target == keyword:
                lines.append(f'  {keyword}')
            else:
                lines.append(f'  {keyword}  ->  {target}')
        lines.append('')

    # Screens
    for i in range(hlp.screen_cnt):
        name = screen_names.get(i)
        label = name if name else f'Screen {i}'

        lines.append('=' * 70)
        lines.append(label)
        lines.append('=' * 70)
        lines.append('')

        raw = hlp.decode_screen(i)
        segments = parse_links(raw, hlp.raw_charset)

        parts = []
        for seg in segments:
            if seg[0] == 'text':
                parts.append(seg[1])
            elif seg[0] == 'link':
                _, scr_no, attr, display = seg
                target = screen_names.get(scr_no)
                if target and target != display:
                    parts.append(f'{display} (see: {target})')
                else:
                    parts.append(display)
            elif seg[0] == 'extlink':
                parts.append(f'{seg[1]} (external)')

        lines.append(''.join(parts))
        lines.append('')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FORMAT_EXT = {'html': '.html', 'md': '.md', 'txt': '.txt'}


def convert_file(input_path, output_path, fmt, include_keywords, raw_charset):
    """Convert a single HLP file."""
    print(f"Reading: {input_path}")
    hlp = HLPFile(input_path, raw_charset=raw_charset)
    print(f"  {hlp.screen_cnt} screens, {len(hlp.keywords)} keywords")

    if fmt == 'html':
        content = generate_html(hlp, include_keywords)
    elif fmt == 'md':
        content = generate_markdown(hlp, include_keywords)
    else:
        content = generate_text(hlp, include_keywords)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Written: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Convert Borland Help System 2.0 (.HLP) files to HTML, Markdown, or plain text.',
        epilog='Format: "Help System Version 2.0 (c) 1990 Borland International"'
    )
    parser.add_argument('input', help='Input .HLP file (or directory with --all)')
    parser.add_argument('output', nargs='?', help='Output file (auto-generated if omitted)')
    parser.add_argument('--format', choices=['html', 'md', 'txt'], default='html',
                        help='Output format: html (default), md (Markdown), txt (plain text for LLMs)')
    parser.add_argument('--all', action='store_true',
                        help='Convert all .HLP files in the input directory')
    parser.add_argument('--keywords', action='store_true', default=True,
                        help='Include keyword index (default: yes)')
    parser.add_argument('--no-keywords', action='store_false', dest='keywords',
                        help='Exclude keyword index')
    parser.add_argument('--raw', action='store_true',
                        help='Don\'t convert Atari ST charset to UTF-8')

    args = parser.parse_args()

    ext = FORMAT_EXT[args.format]

    if args.all:
        # Convert all HLP files in directory
        search_dir = args.input if os.path.isdir(args.input) else os.path.dirname(args.input)
        if not search_dir:
            search_dir = '.'
        hlp_files = sorted([f for f in os.listdir(search_dir)
                            if f.upper().endswith('.HLP')])
        if not hlp_files:
            print(f"No .HLP files found in {search_dir}")
            sys.exit(1)

        out_dir = args.output if args.output else search_dir
        if args.output and not os.path.isdir(args.output):
            os.makedirs(args.output, exist_ok=True)

        for hlp_name in hlp_files:
            input_path = os.path.join(search_dir, hlp_name)
            base = os.path.splitext(hlp_name)[0]
            output_path = os.path.join(out_dir, base + ext)
            try:
                convert_file(input_path, output_path, args.format,
                             args.keywords, args.raw)
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
    else:
        if not os.path.isfile(args.input):
            print(f"File not found: {args.input}", file=sys.stderr)
            sys.exit(1)

        if args.output:
            output_path = args.output
        else:
            base = os.path.splitext(args.input)[0]
            output_path = base + ext

        convert_file(args.input, output_path, args.format,
                     args.keywords, args.raw)


if __name__ == '__main__':
    main()
