"""Load the YAML files under config/ with no third-party dependency.

PyYAML is used when it is installed. Otherwise a small reader for the YAML
subset used by this repo takes over:

  - block mappings          key: value
  - block sequences         - item  /  - key: value (mapping items)
  - flow sequences          [a, b, c]  (scalars only)
  - flow mappings           {k: v, k2: v2}  (scalar values only)
  - scalars                 int, float, true/false, null, 'single' and
                            "double" quoted strings, bare strings
  - comments                # ...

Multi-line scalars, anchors, tags and nested flow collections are not
supported; keep the config files inside this subset so both loaders agree.
Note that PyYAML turns unquoted dates (2026-08-14) into datetime.date while
the fallback keeps them as strings; callers normalise with str().
"""

import os
import re

try:  # optional
    import yaml as _yaml
except ImportError:  # pragma: no cover - depends on the environment
    _yaml = None

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT_DIR, "config")

_KEY_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*:(?:\s+|$)")


class ConfigError(ValueError):
    pass


def load_yaml(path):
    """Parse a YAML file and return Python data (dict / list / scalars)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if _yaml is not None:
        return _yaml.safe_load(text)
    return parse_yaml(text)


def load_config(name):
    """Load config/<name> (e.g. 'experiments.yaml')."""
    return load_yaml(os.path.join(CONFIG_DIR, name))


# ---------------------------------------------------------------------------
# Minimal parser
# ---------------------------------------------------------------------------

def parse_yaml(text):
    lines = _strip(text)
    if not lines:
        return None
    value, idx = _parse_block(lines, 0, lines[0][0])
    if idx != len(lines):
        raise ConfigError("Unparsed content at line %d: %r" % (lines[idx][2], lines[idx][1]))
    return value


def _strip(text):
    """Return [(indent, content, lineno)] without comments and blank lines."""
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        content = _drop_comment(line).rstrip()
        if not content.strip():
            continue
        indent = len(content) - len(content.lstrip(" "))
        out.append([indent, content.strip(), n])
    return out


def _drop_comment(line):
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _parse_block(lines, idx, indent):
    content = lines[idx][1]
    if content.startswith("- ") or content == "-":
        return _parse_sequence(lines, idx, indent)
    return _parse_mapping(lines, idx, indent)


def _parse_sequence(lines, idx, indent):
    items = []
    while idx < len(lines) and lines[idx][0] == indent and (
        lines[idx][1].startswith("- ") or lines[idx][1] == "-"
    ):
        body = lines[idx][1][1:].strip()
        if not body:
            idx += 1
            if idx < len(lines) and lines[idx][0] > indent:
                value, idx = _parse_block(lines, idx, lines[idx][0])
            else:
                value = None
            items.append(value)
            continue
        if _KEY_RE.match(body) and not _is_quoted(body):
            # "- key: value" starts a mapping whose keys sit at indent + 2
            lines[idx] = [indent + 2, body, lines[idx][2]]
            value, idx = _parse_mapping(lines, idx, indent + 2)
        else:
            value = _scalar(body)
            idx += 1
        items.append(value)
    return items, idx


def _parse_mapping(lines, idx, indent):
    result = {}
    while idx < len(lines) and lines[idx][0] == indent:
        content, lineno = lines[idx][1], lines[idx][2]
        m = _KEY_RE.match(content)
        if not m or content.startswith("- "):
            break
        key = m.group(1)
        rest = content[m.end():].strip()
        idx += 1
        if rest:
            result[key] = _scalar(rest)
        elif idx < len(lines) and lines[idx][0] > indent:
            result[key], idx = _parse_block(lines, idx, lines[idx][0])
        elif idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("- "):
            # sequence written at the same indent as its key
            result[key], idx = _parse_sequence(lines, idx, indent)
        else:
            result[key] = None
        if idx < len(lines) and lines[idx][0] > indent:
            raise ConfigError("Unexpected indentation at line %d" % lines[idx][2])
    return result, idx


def _is_quoted(s):
    return s[:1] in ("'", '"')


def _scalar(s):
    s = s.strip()
    if s[:1] == "'" and s[-1:] == "'" and len(s) >= 2:
        return s[1:-1].replace("''", "'")
    if s[:1] == '"' and s[-1:] == '"' and len(s) >= 2:
        return _unescape(s[1:-1])
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(p) for p in _split_flow(inner)] if inner else []
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for part in _split_flow(s[1:-1].strip()):
            if ":" not in part:
                raise ConfigError("Bad flow mapping entry: %r" % part)
            k, v = part.split(":", 1)
            out[k.strip()] = _scalar(v)
        return out
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d+\.\d*$", s) or re.match(r"^-?\d*\.\d+$", s):
        return float(s)
    return s


def _unescape(s):
    return (
        s.replace("\\\\", "\x00")
        .replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\x00", "\\")
    )


def _split_flow(inner):
    parts, buf, quote = [], "", None
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            buf += ch
        elif ch == ",":
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return parts
