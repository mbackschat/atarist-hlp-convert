# Borland HLP File Format Tools

Decoder and converter for the Borland Help System 2.0 (`.HLP`) files used by
**Pure C** and **Turbo C** on the **Atari ST** (circa 1989-1992).

## Files

| File | Description |
|------|-------------|
| `hlp_convert.py` | Python 3 converter -- decodes `.HLP` files to HTML, Markdown, or plain text |
| `HLP-ANALYSIS.md` | Complete reverse-engineered binary format specification |

## Quick Start

The script is a single-file Python 3.6+ program with **no external dependencies**.

### Using uv (recommended)

No installation needed -- [uv](https://docs.astral.sh/uv/) runs the script
directly without setting up a virtual environment or installing Python manually:

```bash
# Convert a single file to HTML (default)
uv run hlp_convert.py help/PC.HLP

# Convert to Markdown
uv run hlp_convert.py --format md help/LIB.HLP

# Convert to plain text (LLM-friendly, no markup)
uv run hlp_convert.py --format txt help/LIB.HLP

# Batch-convert all .HLP files in a directory
uv run hlp_convert.py --all --format html help/ output/
uv run hlp_convert.py --all --format txt help/ output/
```

### Using python directly

```bash
python3 hlp_convert.py help/PC.HLP
python3 hlp_convert.py --format md help/LIB.HLP
python3 hlp_convert.py --format txt help/LIB.HLP
python3 hlp_convert.py --all --format html help/ output/
```

## Output Formats

### HTML (`--format html`)

Styled document with a table of contents, keyword index table, and clickable
cross-reference links between help screens. Opens in any browser.

### Markdown (`--format md`)

Markdown with screen content in fenced code blocks and link references listed
below each screen. Suitable for documentation repos and static site generators.

### Plain Text (`--format txt`)

Clean UTF-8 text with no markup. Sections are separated by `======` headers.
Cross-references are inlined as `Display Text (see: Topic Name)`. Designed
to be directly consumable by LLMs as context.

## Command-Line Options

```
hlp_convert.py [options] <input.hlp> [output]

positional arguments:
  input                 Input .HLP file (or directory with --all)
  output                Output file (auto-generated if omitted)

options:
  --format {html,md,txt}  Output format (default: html)
  --all                   Convert all .HLP files in the input directory
  --no-keywords           Exclude keyword index from output
  --raw                   Don't convert Atari ST charset to UTF-8
```

## Format Overview

The HLP format uses:

- **136-byte header** with copyright, magic (`0xBD` + `"90BH2.0"`), section offsets
- **Nibble-based compression** -- each byte encodes two 4-bit values indexing a 12-character lookup table of the most frequent characters
- **XOR-encrypted string table** (key `0xA3`) for reusable text fragments
- **Cross-references** embedded as `ESC (0x1D)` + 16-bit screen code + display text + `ESC`
- **Keyword search tables** mapping search terms to screen numbers

See [HLP-ANALYSIS.md](HLP-ANALYSIS.md) for the complete byte-level specification.

## References

- [th-otto/pc_help](https://github.com/th-otto/pc_help) -- Reconstructed source code of the original help compiler and decompiler by ThorstenOtto
- [Atari-Forum discussion](https://www.atari-forum.com/viewtopic.php?t=39505) -- Community thread on Pure C help files
