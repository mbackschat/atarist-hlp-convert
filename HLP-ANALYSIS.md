# Borland Help System 2.0 (.HLP) - File Format Specification

**Format**: Borland Help System Version 2.0  
**Platform**: Atari ST/TT (Motorola 68000, big-endian)  
**Era**: 1989-1992  
**Used by**: Pure C, Turbo C, Pure Pascal (Borland / Application Systems Heidelberg)  
**Reconstructed source**: [github.com/th-otto/pc_help](https://github.com/th-otto/pc_help)

---

## 1. Overall File Layout

```
+---------------------------+  offset 0x00
|  HLPHDR (136 bytes)       |  File header with copyright, magic,
|                           |  offsets, sizes, and char table
+---------------------------+  offset 0x88 (sizeof(HLPHDR))
|  Screen Offset Table      |  Array of uint32_t BE offsets
|  (scr_tab_size bytes)     |  One entry per screen + 1 sentinel
+---------------------------+  offset = str_offset
|  String Table             |  XOR-encrypted (key 0xA3) text
|  (str_size bytes)         |  fragments for decompression
+---------------------------+  offset = caps_offset
|  Case-Sensitive Keyword   |  SRCHKEY_ENTRY[caps_cnt] +
|  Table (caps_size bytes)  |  null-terminated keyword strings
+---------------------------+  offset = sens_offset
|  Case-Insensitive Keyword |  SRCHKEY_ENTRY[sens_cnt] +
|  Table (sens_size bytes)  |  null-terminated keyword strings
+---------------------------+  offset = screen_table[0]
|  Compressed Screen Data   |  Nibble-encoded help page content
|  (to end of file)         |
+---------------------------+  EOF
```

All multi-byte integers are stored in **big-endian** byte order (Motorola 68000 native).

---

## 2. File Header (HLPHDR) - 136 bytes

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 80 | char[80] | `copyright` | ASCII text: `"Help System Version 2.0 (c) 1990 Borland International, Inc.\r\n\r\n"` followed by `0x0C` (form-feed), `0x1A` (CP/M EOF), then zero-padded |
| 0x50 | 8 | char[8] | `magic` | `0xBD` + `"90BH2.0"` (C literal: `"\27590BH2.0"`, octal 275 = 0xBD) |
| 0x58 | 4 | uint32_t | `scr_tab_size` | Size of screen offset table in bytes. Screen count = `(scr_tab_size / 4) - 1` |
| 0x5C | 4 | uint32_t | `str_offset` | Absolute file offset to string table |
| 0x60 | 4 | uint32_t | `str_size` | String table size in bytes |
| 0x64 | 12 | char[12] | `char_table` | 12 most frequent characters for nibble-based compression (nibble indices 0x0..0xB) |
| 0x70 | 4 | uint32_t | `caps_offset` | Absolute file offset to case-sensitive keyword table |
| 0x74 | 4 | uint32_t | `caps_size` | Total size: `(caps_cnt * 6) + keyword_strings_size` |
| 0x78 | 4 | uint32_t | `caps_cnt` | Number of case-sensitive keywords |
| 0x7C | 4 | uint32_t | `sens_offset` | Absolute file offset to case-insensitive keyword table |
| 0x80 | 4 | uint32_t | `sens_size` | Total size of case-insensitive table (0 if unused) |
| 0x84 | 4 | uint32_t | `sens_cnt` | Number of case-insensitive keywords (0 if unused) |

### C struct definition (from hcint.h)

```c
#define HC_MAGIC    "\27590BH2.0"
#define HC_ENCRYPT  0xa3
#define CHAR_DIR    0x0C  /* 12 entries in char_table */

typedef struct {
    char          copyright[80];
    char          magic[8];
    uint32_t      scr_tab_size;
    uint32_t      str_offset;
    uint32_t      str_size;
    unsigned char char_table[CHAR_DIR];
    uint32_t      caps_offset;
    uint32_t      caps_size;
    uint32_t      caps_cnt;
    uint32_t      sens_offset;
    uint32_t      sens_size;
    uint32_t      sens_cnt;
} HLPHDR;
```

### Example values (PC.HLP, 58173 bytes)

| Field | Value | Meaning |
|-------|-------|---------|
| scr_tab_size | 452 | (452/4)-1 = 112 screens |
| str_offset | 0x024C (588) | String table starts at byte 588 |
| str_size | 18264 | ~18 KB of string fragments |
| char_table | `" e-nirtasldo"` | 12 most common characters |
| caps_offset | 0x49A4 | Keyword table at byte 18852 |
| caps_size | 480 | |
| caps_cnt | 42 | 42 searchable keywords |
| sens_offset | 0x4B84 | |
| sens_size | 0 | No case-insensitive table |
| sens_cnt | 0 | |

---

## 3. Screen Offset Table

Located immediately after the header at file offset 0x88.

- Contains `(scr_tab_size / 4)` entries of type `uint32_t` (big-endian)
- This is `screen_count + 1` entries (the extra entry is a sentinel)
- Each entry is an **absolute file offset** to the start of that screen's compressed data
- Screen `i`'s data spans from `screen_table[i]` to `screen_table[i+1] - 1`

### Reserved screen indices

| Index | Purpose |
|-------|---------|
| 0 | Copyright / build date screen |
| 1 | Main index page (alphabetical keyword navigation) |
| 2+ | Help content screens |

---

## 4. String Table

Located at `str_offset`, size `str_size` bytes.

The string table provides a dictionary of reusable text fragments that the compressed screen data references. It has two parts:

### 4.1 Offset Index (beginning of string table)

An array of `uint32_t` (big-endian) values. Each value is an offset **relative to the start of the string table** pointing to where that string fragment begins within the string data area.

### 4.2 String Data (XOR-encrypted)

The actual text bytes follow the offset index. **Every byte is XOR-encrypted** with the constant `HC_ENCRYPT = 0xA3`.

To decrypt: `plain_byte = stored_byte ^ 0xA3`

### Lookup procedure

To retrieve string fragment at index `idx`:
```
base         = string_table_start  (= str_offset in file)
offset       = read_uint32_be(base + idx * 4)
next_offset  = read_uint32_be(base + (idx + 1) * 4)
length       = next_offset - offset
encrypted    = file_data[base + offset .. base + offset + length]
plain_text   = for each byte b in encrypted: b XOR 0xA3
```

---

## 5. Screen Data Compression (Nibble Encoding)

Each screen's content is compressed using a **nibble-based** (4-bit) encoding scheme. The compressed data is read as a stream of nibbles, where each byte yields two nibbles: high nibble first, then low nibble.

### 5.1 Nibble reading

```
State: must_read = true, byte_read = undefined

function get_nibble():
    if must_read:
        byte_read = next_byte_from_stream()
        must_read = false
        return byte_read >> 4        # high nibble
    else:
        must_read = true
        return byte_read & 0x0F      # low nibble

function get_byte():
    return (get_nibble() << 4) | get_nibble()
```

### 5.2 Nibble interpretation

| Nibble | Constant | Action |
|--------|----------|--------|
| 0x0 - 0xB | *(lookup)* | Emit `char_table[nibble]` (one of the 12 most frequent characters) |
| 0xC | `CHAR_DIR` | Read next byte via `get_byte()`, emit it as a literal character |
| 0xD | `STR_TABLE` | Read 12-bit index: `idx = (get_byte() << 4) \| get_nibble()`. Look up string fragment at `idx` in the string table, XOR-decrypt, and emit |
| 0xE | `STR_NEWLINE` | Emit CR (0x0D) + LF (0x0A) |
| 0xF | `CHAR_EMPTY` | **End of screen** - stop decoding |

### 5.3 Decoding pseudocode

```
function decode_screen(screen_index):
    compressed = file[screen_table[i] .. screen_table[i+1]]
    init_nibble_reader(compressed)
    output = []
    
    loop:
        nibble = get_nibble()
        
        if nibble < 0x0C:                       # Character from lookup table
            output.append(char_table[nibble])
        
        else if nibble == 0x0C:                  # Literal byte
            output.append(get_byte())
        
        else if nibble == 0x0D:                  # String table reference
            idx = (get_byte() << 4) | get_nibble()    # 12-bit index
            str_offset  = uint32_be(string_tab + idx * 4)
            str_end     = uint32_be(string_tab + (idx+1) * 4)
            for b in string_tab[str_offset .. str_end]:
                output.append(b XOR 0xA3)
        
        else if nibble == 0x0E:                  # Newline
            output.append(0x0D)
            output.append(0x0A)
        
        else:                                    # 0x0F = End of screen
            break
    
    return output
```

### 5.4 Compression rationale

- **Nibble lookup (0x0-0xB)**: The 12 most frequent characters encode in just 4 bits. When two table characters appear consecutively, both fit in a single byte -- 2:1 compression.
- **Literal bytes (0xC)**: Less frequent characters need 12 bits (1.5 bytes per character).
- **String references (0xD)**: Repeated multi-character phrases are stored once in the string table and referenced with 16 bits (nibble 0xD + 12-bit index). This provides significant compression for recurring phrases like function names, parameter descriptions, and boilerplate text.
- **Newlines (0xE)**: Two bytes (CR+LF) compressed to 4 bits.

---

## 6. Cross-References (Hyperlinks)

After decompression, the plain text may contain embedded cross-reference markers. These use the escape character `0x1D` (`ESC_CHR`):

```
0x1D  <code_hi>  <code_lo>  <display_text...>  0x1D
 ^       ^          ^             ^               ^
 |    high byte  low byte    visible text      end marker
 start marker   of scr_code_t
```

### 6.1 Fields

| Component | Size | Description |
|-----------|------|-------------|
| Start marker | 1 byte | `0x1D` |
| Screen code | 2 bytes | Big-endian `scr_code_t` (see below) |
| Display text | variable | The text shown to the user (terminated by next `0x1D`) |
| End marker | 1 byte | `0x1D` |

### 6.2 Screen code (`scr_code_t`) bit layout

```
  15  14                3  2    0
+----+------------------+------+
| hi |   screen_no      | attr |
+----+------------------+------+
  1       12 bits         3 bits
```

```c
typedef union {
    struct {
        unsigned int hibit: 1;      /* Bit 15: 1 = valid */
        unsigned int screen_no: 12; /* Bits 14-3: target screen index */
        unsigned int attr: 3;       /* Bits 2-0: name attribute */
    } u;
    uint16_t xcode;
} scr_code_t;
```

### 6.3 Attribute values

| Value | Constant | Meaning |
|-------|----------|---------|
| 0 | `SCR_NAME` | Screen/topic name |
| 1 | `CAP_SENS` | Case-sensitive keyword |
| 2 | `SENSITIVE` | Case-insensitive keyword |
| 3 | `LINK` | Link-only name (alias) |

### 6.4 External links

A code of `0xFFFF` (`LINK_EXTERNAL`) indicates a cross-reference to a **different .HLP file**. The display text following the code is the keyword to look up in the external file (resolved at runtime by PC_HELP).

---

## 7. Keyword Search Tables

Two keyword tables enable topic lookup: case-sensitive (`caps_*` fields) and case-insensitive (`sens_*` fields). Both use the same structure.

### 7.1 Table layout

```
+----------------------------------+  offset = caps_offset (or sens_offset)
|  SRCHKEY_ENTRY[0]   (6 bytes)   |
|  SRCHKEY_ENTRY[1]   (6 bytes)   |
|  ...                             |
|  SRCHKEY_ENTRY[cnt-1] (6 bytes) |
+----------------------------------+
|  Keyword strings                 |  Null-terminated, referenced by
|  (variable size)                 |  relative offsets in entries above
+----------------------------------+
```

### 7.2 SRCHKEY_ENTRY (6 bytes)

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0 | 4 | int32_t BE | `pos` | Byte offset from **this entry's file position** to its keyword string |
| 4 | 2 | uint16_t BE | `code` | `scr_code_t` encoding the target screen number and attributes |

To find the keyword string for entry `i`:
```
entry_file_pos = table_offset + (i * 6)
string_pos     = entry_file_pos + read_int32_be(entry_file_pos)
keyword        = read_null_terminated_string(string_pos)
```

### 7.3 Example (PC.HLP)

| # | Keyword | Screen | Code |
|---|---------|--------|------|
| 0 | `#` | 86 | 0x82B0 |
| 1 | `Compileroptionen` | 56 | 0x81C0 |
| 2 | `Editor` | 77 | 0x8268 |
| 3 | `Error` | 62 | 0x81F0 |
| 4 | `Menu` | 3 | 0x8018 |
| 5 | `Options` | 11 | 0x8058 |
| 6 | `Projektdatei` | 83 | 0x8298 |
| 7 | `Warning` | 57 | 0x81C8 |
| 8 | `Warnungen` | 57 | 0x81C8 |

---

## 8. Character Encoding (Atari ST)

Text uses the **Atari ST character set**. This is largely compatible with ASCII for bytes 0x20-0x7E. Higher bytes encode accented characters, box-drawing characters, and symbols. Key mappings for German text:

| Byte | Character | Unicode |
|------|-----------|---------|
| 0x81 | u-umlaut | U+00FC (ü) |
| 0x84 | a-umlaut | U+00E4 (ä) |
| 0x8E | A-umlaut | U+00C4 (Ä) |
| 0x94 | o-umlaut | U+00F6 (ö) |
| 0x99 | O-umlaut | U+00D6 (Ö) |
| 0x9A | U-umlaut | U+00DC (Ü) |
| 0x9E | ss-ligature | U+00DF (ß) |
| 0xE1 | ss (alt) | U+00DF (ß) |

---

## 9. Multi-File Help System

The help system spans multiple .HLP files, each with a reserved file index:

| Index | File | Content |
|-------|------|---------|
| 0 | `PC.HLP` | Pure C compiler (IDE, menus, options) |
| 0 | `PD.HLP` | Pure Debugger (shares index 0, different context) |
| 1 | `C.HLP` | C language reference |
| 2 | `LIB.HLP` | C standard library functions |
| 3 | `PASM.HLP` | Pure Assembler (68000 mnemonics) |
| 4 | `USR.HLP` | User-defined help (optional) |

External cross-references (`code = 0xFFFF`) are resolved at runtime: the viewer searches all loaded .HLP files for the keyword.

---

## 10. Legacy DOS Format (PPH1)

An older format (used by Turbo C on DOS) exists with magic `0x50504831` (`'PPH1'`). It uses a different header structure and LZ77-like chunk compression instead of nibble encoding. The help viewer (`PC_HELP`) supports both formats.

```c
typedef struct {
    uint32_t magic;           /* 0x50504831 = 'PPH1' */
    uint32_t search_tab_size;
    uint32_t str_size;
    uint32_t scr_tab_size;
    uint32_t compr_tab_size;
    uint32_t reserved_20;
    uint32_t reserved_24;
    uint32_t reserved_28;
} PPHDR;
```

This format is not used by the Pure C .HLP files in this archive.

---

## 11. Tools and References

### Original Borland tools
- **HC.TTP** - Help compiler: compiles `.SCR` source files into `.HLP` binary
- **PC_HELP.ACC/PRG** - Help viewer (desk accessory or standalone application)
- **HELPDISC.TTP** - Help decompiler (has known bugs with files > ~160 KB)

### Modern tools
- **hlp_convert.py** - Python 3 converter (this project)  
  Converts `.HLP` files to **HTML** (styled, clickable links), **Markdown**, or **plain text** (LLM-friendly)  
  Usage: `python3 hlp_convert.py --format html|md|txt <input.hlp>`
- **help_rc** by ThorstenOtto - Reconstructed decompiler  
  Source: [github.com/th-otto/pc_help](https://github.com/th-otto/pc_help)  
  Outputs `.scr` (help source), `.txt`, or `.stg` (ST-Guide format)

### PC_HELP Viewer API (GEM AES messages)

Applications can request help via AES messages to the PC_HELP desk accessory:

| Message | Code | Purpose |
|---------|------|---------|
| `AC_HELP` | 1025 | Look up keyword (pointer in msg[3..4]) |
| `AC_REPLY` | 1026 | Reply from accessory |
| `AC_VERSION` | 1027 | Query version number |
| `AC_COPY` | 1028 | Copy help text to GEM clipboard |

```c
/* Example: request help for keyword */
msg_buff[0] = 1025;                        /* AC_HELP */
msg_buff[1] = ap_id;                       /* sender's app ID */
msg_buff[2] = 0;                           /* no extra data */
*(char **)&msg_buff[3] = "printf";         /* keyword pointer */
appl_write(acc_id, 16, msg_buff);          /* send to accessory */
```
