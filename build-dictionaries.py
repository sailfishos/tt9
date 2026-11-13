#!/usr/bin/env python3
# Copyright (c) 2026 Jolla Mobile Ltd.
"""
  python3 build-dictionaries.py --output out --from-list languages.list \\
      --dictionaries dictionaries.list
"""

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
DEFINITIONS = HERE / "tt9" / "app" / "languages" / "definitions"
DICTIONARIES = HERE / "tt9" / "app" / "languages" / "dictionaries"
READMES = HERE / "tt9" / "docs" / "dictionaries"
HUNSPELL = HERE / "libreoffice-dictionaries"

# Locales whose word list is a LibreOffice hunspell dictionary instead of the
# CSV named in the layout. The Traditional T9 CSVs for these languages carry a
# non-commercial licence and must not be used.
# directory: folder in the LibreOffice dictionaries checkout.
# notice: files under that folder, joined into the full notice.
# license: file with the license text, or None to cut it out of the first
#   notice file, the readme.
# clitic_flags: affix flags that mix plain endings with pronoun-attached forms.
#   Only their rules adding a plain ending (PLAIN_ENDINGS) are used.
HUNSPELL_SOURCES = {
    "it-IT": {
        "directory": "it_IT",
        "notice": ("README_it_IT.txt", "legacy/it_IT_license.txt"),
        "license": None,
        # Verb forms with attached pronouns, e.g. "identificatecela".
        "clitic_flags": set("IDEKLhMbjmcvla"),
    },
    "pt-PT": {
        "directory": "pt_PT",
        "notice": ("README_pt_PT.txt", "LICENSES.txt"),
        "license": "LICENSES.txt",
        "clitic_flags": set(),
    },
}

# What a clitic flag may still add: the plain gender and number endings.
PLAIN_ENDINGS = {"", "a", "e", "i", "o", "he", "hi"}

# A hunspell dictionary expands to far more forms than people type. Stop the
# build if a list ever grows past this, so a wrong flag set is noticed.
HUNSPELL_MAX_WORDS = 1500000

# A package build must produce these even when the list grows.
REQUIRED_LOCALES = ("en", "de-DE", "fi-FI")

# Word-list readmes are not named after the locale. None means upstream
# shipped the dictionary without a notice.
README_ALIASES = {
    "be-narmawka": "benarmawka",
    "da": None,
    "gr": None,
    "ja-romaji": "ja",
    "ph": "fil",
    "pt-BR": "pt",
    "pt-PT": "pt",
    "srl": "sr",
    "tamazight": "zgh",
    "tamazight-latin": "zgh",
    "zh-bopomofo": "bopomofo",
    "zh-simplified-pinyin": "pinyin",
    "zh-traditional-pinyin": "pinyin",
}

# The same groups Traditional T9 substitutes for the placeholders in a layout.
SPECIAL = list("@_#%[]{}§|^<>\\/=*+")
PUNCTUATION = {
    "PUNCTUATION": list(',.-()&~`;:\'"!?' ),
    "PUNCTUATION_AR": list("،.-()&~`'\"\u061b:!؟"),
    "PUNCTUATION_BP": list("，、。1—～゠（）.「」『』•《》〈〉'“”；：！？"),
    "PUNCTUATION_ZH": list("，、。—～゠（）.「」『』•《》〈〉'“”；：！？"),
    "PUNCTUATION_FA": list("،.-\u200c()&~`'\"\u061b:!؟"),
    "PUNCTUATION_FR": list(',.-«»()&`~;:\'"!?' ),
    "PUNCTUATION_DE": list(',.-„“()&~`\'";:!?' ),
    "PUNCTUATION_GR": list(',.-«»()&~`\'"·:!;'),
    "PUNCTUATION_IE": list(',.-()&⁊~`;:\'"!?' ),
    "PUNCTUATION_IN": list(",.-()\u200d\u200c।॰॥&~`;:'\"!?"),
    "PUNCTUATION_KR": list(",.~1()&-`;:'\"!?"),
}


def expand_token(token):
    if token == "SPECIAL":
        # Space and newline stay first, as on the printed 0 key.
        return [" ", "\n"] + SPECIAL
    if token in PUNCTUATION:
        return PUNCTUATION[token]
    return list(token)


def parse_list_body(line):
    body = line[line.find("[") + 1 : line.rfind("]")]
    return [token.strip() for token in body.split(",") if token.strip()]


def parse_definition(path):
    locale = ""
    dictionary = ""
    keys = {}
    sounds = {}
    section = ""
    order = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("locale:"):
            locale = line.split(":", 1)[1].strip()
            section = ""
        elif line.startswith("dictionaryFile:"):
            dictionary = line.split(":", 1)[1].strip()
            section = ""
        elif line.startswith("layout:"):
            section = "layout"
            order = 0
        elif line.startswith("sounds:"):
            section = "sounds"
        elif line.endswith(":") and not line.startswith("-"):
            section = ""
        elif section == "layout" and line.startswith("- ["):
            comment = raw.split("#", 1)[1].strip() if "#" in raw else ""
            try:
                index = int(comment.split()[0])
            except (ValueError, IndexError):
                index = order
            order += 1
            chars = []
            for token in parse_list_body(line):
                chars.extend(expand_token(token))
            if 0 <= index <= 9 and chars:
                keys[str(index)] = "".join(chars)
        elif section == "sounds" and line.startswith("- ["):
            # [sound, digits]. The longer sound has to win later, so "Ng" is
            # not read as "N" plus a leftover.
            parts = parse_list_body(line)
            if len(parts) >= 2:
                sounds[parts[0]] = parts[1]
    return locale, dictionary, keys, sounds


def load_mapping(keys):
    mapping = {}
    for digit, chars in keys.items():
        for char in chars:
            mapping[char.lower()] = digit
    return mapping


def digit_sequence(word, mapping):
    sequence = []
    for char in word.lower():
        digit = mapping.get(char)
        if digit is None:
            return None
        sequence.append(digit)
    return "".join(sequence) if sequence else None


def sound_sequence(transcription, sounds, ordered):
    position = 0
    digits = []
    while position < len(transcription):
        matched = None
        for sound in ordered:
            if transcription.startswith(sound, position):
                matched = sound
                break
        if matched is None:
            return None
        digits.append(sounds[matched])
        position += len(matched)
    return "".join(digits) if digits else None


def parse_frequency(text):
    try:
        frequency = int(text)
    except ValueError:
        return 0
    return frequency if frequency >= 0 else 0


def collect_words(csv_path, mapping, sounds):
    # Longest phonetic name first, so "Yu" is not consumed as "Y".
    ordered = sorted(sounds, key=len, reverse=True)
    best = {}
    skipped = 0
    with csv_path.open(encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if not parts or not parts[0]:
                continue
            word = parts[0]
            if sounds:
                # word, phonetic, optional frequency. The letters of the word
                # itself are not on the digit keys.
                if len(parts) < 2 or not parts[1]:
                    skipped += 1
                    continue
                frequency = parse_frequency(parts[2]) if len(parts) > 2 else 0
                sequence = sound_sequence(parts[1], sounds, ordered)
            else:
                frequency = parse_frequency(parts[-1]) if len(parts) > 1 else 0
                sequence = digit_sequence(word, mapping)
            if sequence is None:
                skipped += 1
                continue
            key = (sequence, word)
            previous = best.get(key)
            if previous is None or frequency > previous:
                best[key] = frequency
    return best, skipped


def read_hunspell_text(path):
    # The Portuguese files are not all UTF-8.
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def read_affixes(path, clitic_flags):
    # kind -> flag -> (cross product, [(strip, add, condition regex)])
    affixes = {"PFX": {}, "SFX": {}}
    for raw in read_hunspell_text(path).splitlines():
        parts = raw.split("#", 1)[0].split()
        if len(parts) < 4 or parts[0] not in affixes:
            continue
        kind, flag = parts[0], parts[1]
        if parts[2] in ("Y", "N") and len(parts) == 4:
            affixes[kind][flag] = (parts[2] == "Y", [])
            continue
        if flag not in affixes[kind] or len(parts) < 5:
            continue
        strip = "" if parts[2] == "0" else parts[2]
        add = "" if parts[3] == "0" else parts[3].split("/", 1)[0]
        # Apostrophes and hyphens build elisions and pronoun forms, which are
        # typed as separate words on the keypad.
        if "'" in add or "-" in add:
            continue
        if flag in clitic_flags and add not in PLAIN_ENDINGS:
            continue
        condition = parts[4]
        if condition == ".":
            pattern = ""
        else:
            pattern = "^" + condition if kind == "PFX" else condition + "$"
        try:
            matcher = re.compile(pattern)
        except re.error:
            continue
        affixes[kind][flag][1].append((strip, add, matcher))
    return affixes


def apply_affix(kind, word, strip, add, matcher):
    if matcher.pattern and not matcher.search(word):
        return None
    if kind == "SFX":
        if strip and not word.endswith(strip):
            return None
        return word[: len(word) - len(strip)] + add
    if strip and not word.startswith(strip):
        return None
    return add + word[len(strip):]


def expand_hunspell(directory, clitic_flags):
    # Stems with the flags from the .dic, plus the forms those flags allow.
    # Forms an affix flag adds again (continuation flags) are not followed.
    name = directory.name
    affixes = read_affixes(directory / ("%s.aff" % name), clitic_flags)
    forms = set()
    lines = read_hunspell_text(directory / ("%s.dic" % name)).splitlines()
    for raw in lines[1:]:
        if not raw or raw[0] in "#/\t ":
            continue
        entry = raw.split("\t", 1)[0].split(" ", 1)[0]
        word, _sep, flags = entry.partition("/")
        if not any(char.isalpha() for char in word) or "'" in word or "-" in word:
            continue
        forms.add(word)
        cross_prefixes = []
        cross_suffixes = []
        for flag in flags:
            for kind in ("PFX", "SFX"):
                if flag not in affixes[kind]:
                    continue
                cross, rules = affixes[kind][flag]
                for strip, add, matcher in rules:
                    form = apply_affix(kind, word, strip, add, matcher)
                    if not form:
                        continue
                    forms.add(form)
                    if cross and kind == "SFX":
                        cross_suffixes.append(form)
                    elif cross:
                        cross_prefixes.append((strip, add, matcher))
        # Cross product: each prefix also goes onto each suffixed form.
        for suffix_form in cross_suffixes:
            for strip, add, matcher in cross_prefixes:
                form = apply_affix("PFX", suffix_form, strip, add, matcher)
                if form:
                    forms.add(form)
    return forms


def collect_hunspell_words(locale, mapping):
    source = HUNSPELL_SOURCES[locale]
    forms = expand_hunspell(HUNSPELL / source["directory"], source["clitic_flags"])
    best = {}
    skipped = 0
    for word in sorted(forms):
        sequence = digit_sequence(word, mapping)
        if sequence is None:
            skipped += 1
            continue
        # No usage counts here. Ordinary lowercase words go before names and
        # acronyms, which would otherwise sort first as capitals.
        best[(sequence, word)] = 0 if any(char.isupper() for char in word) else 1
    if len(best) > HUNSPELL_MAX_WORDS:
        raise SystemExit("%s: %d words from the hunspell dictionary, more than %d" % (locale, len(best), HUNSPELL_MAX_WORDS))
    return best, skipped


def escape_layout(chars):
    # One line per key. Newline and backslash are written escaped and undone
    # by T9Dictionary when it reads the file.
    return chars.replace("\\", "\\\\").replace("\n", "\\n")


def write_layout(path, keys):
    lines = ["# Generated from Traditional T9. digit=characters.", ""]
    for digit in "0123456789":
        if digit in keys:
            lines.append("%s=%s" % (digit, escape_layout(keys[digit])))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_database(path, words):
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("PRAGMA journal_mode = OFF")
        connection.execute("PRAGMA synchronous = OFF")
        connection.execute(
            "CREATE TABLE words ("
            "sequence TEXT NOT NULL, "
            "word TEXT NOT NULL, "
            "frequency INTEGER NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO words(sequence, word, frequency) VALUES (?, ?, ?)",
            ((sequence, word, frequency) for (sequence, word), frequency in words.items()),
        )
        connection.execute("CREATE INDEX idx_words_sequence ON words(sequence)")
        connection.commit()
        connection.execute("VACUUM")
    finally:
        connection.close()


def dictionary_key(dictionary_name):
    stem = Path(dictionary_name).stem
    if stem.endswith("-utf8"):
        stem = stem[: -len("-utf8")]
    return stem


def find_readme(dictionary_name):
    key = dictionary_key(dictionary_name)
    if key in README_ALIASES:
        key = README_ALIASES[key]
        if key is None:
            return None
    else:
        key = key.lower()
    if not READMES.is_dir():
        return None
    for path in READMES.iterdir():
        if not path.is_file():
            continue
        base = path.name
        cut = base.lower().find("wordlistreadme.txt")
        if cut <= 0:
            continue
        if base[:cut].lower() == key:
            return path
    return None


_LICENSE_HEADING = re.compile(
    r"^(COPYRIGHT\b|GNU GENERAL PUBLIC LICENSE|Apache License|MIT License|"
    r"Permission is hereby granted|THE SOFTWARE IS PROVIDED)",
    re.M,
)
_LICENSE_HINT = re.compile(
    r"licen[cs]e|copyright|public domain|creative commons|"
    r"\bGPL\b|\bLGPL\b|\bMIT\b|\bMPL\b|\bBSD\b|\bApache\b",
    re.I,
)


def extract_license(text):
    # A readme that carries the license itself: keep that text, not the word-list essay.
    heading = _LICENSE_HEADING.search(text)
    if heading and heading.start() > 0:
        return text[heading.start():].strip() + "\n"
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chosen = [paragraph for paragraph in paragraphs if _LICENSE_HINT.search(paragraph)]
    if chosen:
        return "\n\n".join(chosen).strip() + "\n"
    return text.strip() + "\n"


def write_hunspell_notice(notices, locale):
    source = HUNSPELL_SOURCES[locale]
    directory = HUNSPELL / source["directory"]
    texts = []
    for name in source["notice"]:
        text = read_hunspell_text(directory / name)
        texts.append(text if text.endswith("\n") else text + "\n")
    license_name = source["license"]
    if license_name:
        license_text = read_hunspell_text(directory / license_name)
    else:
        license_text = extract_license(texts[0])
    doc = notices / ("%s.txt" % locale)
    license_path = notices / ("%s.license" % locale)
    doc.write_text("\n".join(texts), encoding="utf-8")
    license_path.write_text(license_text if license_text.endswith("\n") else license_text + "\n", encoding="utf-8")
    return doc.name, license_path.name


def write_notice(notices, locale, dictionary):
    if locale in HUNSPELL_SOURCES:
        return write_hunspell_notice(notices, locale)
    readme = find_readme(dictionary)
    if readme is None:
        print("notice %s: no word-list readme for %s" % (locale, dictionary), file=sys.stderr)
        return None
    text = readme.read_text(encoding="utf-8", errors="replace")
    doc = notices / ("%s.txt" % locale)
    license_path = notices / ("%s.license" % locale)
    doc.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    license_path.write_text(extract_license(text), encoding="utf-8")
    return doc.name, license_path.name


def build_layout(definition, output):
    locale, dictionary, keys, sounds = parse_definition(definition)
    if not locale or "2" not in keys:
        print("skip %s: no locale or letter keys" % definition.name, file=sys.stderr)
        return None
    write_layout(output / ("%s.layout" % locale), keys)
    return locale, dictionary, keys, sounds


def build_word_list(locale, dictionary, keys, sounds, output):
    mapping = load_mapping(keys)
    if locale in HUNSPELL_SOURCES:
        source_dir = HUNSPELL / HUNSPELL_SOURCES[locale]["directory"]
        if not source_dir.is_dir():
            print("skip %s dictionary: missing %s" % (locale, source_dir), file=sys.stderr)
            return False
        words, skipped = collect_hunspell_words(locale, mapping)
    else:
        if not dictionary:
            print("skip %s dictionary: no dictionary file" % locale, file=sys.stderr)
            return False
        csv_path = DICTIONARIES / dictionary
        if not csv_path.is_file():
            print("skip %s dictionary: missing %s" % (locale, csv_path), file=sys.stderr)
            return False
        words, skipped = collect_words(csv_path, mapping, sounds)
    if not words:
        print("skip %s dictionary: no words mapped" % locale, file=sys.stderr)
        return False
    write_database(output / ("%s.sqlite" % locale), words)
    print("%s: %d words, %d skipped" % (locale, len(words), skipped))
    return True


def reset_dir(path):
    # A previous run may have written languages that are no longer requested.
    # %install copies this directory as-is, so those leftovers would ship.
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def read_locale_list(path):
    locales = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            locales.append(line)
    return locales


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", action="append", default=[], help="layout locale to build; repeatable")
    parser.add_argument("--from-list", type=Path, help="layout locales to build, one per line")
    parser.add_argument("--dictionaries", type=Path, help="locales that also get a word list, one per line")
    parser.add_argument("--notices", type=Path, help="where to write per-language doc and license files")
    args = parser.parse_args()
    reset_dir(args.output)
    listed = read_locale_list(args.from_list) if args.from_list else []
    if args.from_list:
        missing = [locale for locale in REQUIRED_LOCALES if locale not in listed]
        if missing:
            raise SystemExit("language list must include %s" % ", ".join(missing))
    wanted = set(args.only) | set(listed)
    dictionaries = set(read_locale_list(args.dictionaries)) if args.dictionaries else set()
    if args.dictionaries:
        missing = [locale for locale in REQUIRED_LOCALES if locale not in dictionaries]
        if missing:
            raise SystemExit("dictionary list must include %s" % ", ".join(missing))
        outside = sorted(dictionaries - wanted) if wanted else []
        if outside:
            raise SystemExit("dictionary locales missing from the layout list: %s" % ", ".join(outside))
    if args.notices:
        reset_dir(args.notices)
    built = []
    built_dictionaries = []
    notice_lines = []
    for definition in sorted(DEFINITIONS.glob("*.yml")):
        locale, _dictionary, _keys, _sounds = parse_definition(definition)
        if wanted and locale not in wanted:
            continue
        prepared = build_layout(definition, args.output)
        if prepared is None:
            continue
        locale, dictionary, keys, sounds = prepared
        built.append(locale)
        if locale not in dictionaries:
            print("%s: layout" % locale)
            continue
        if not build_word_list(locale, dictionary, keys, sounds, args.output):
            continue
        built_dictionaries.append(locale)
        if args.notices and dictionary:
            written = write_notice(args.notices, locale, dictionary)
            if written:
                # %% so the percent signs survive the format operation.
                # Both the full notice and the license text are %%license, so other
                # packages can read them from the license directory.
                notice_lines.append("%%license %s" % (args.notices / written[0]))
                notice_lines.append("%%license %s" % (args.notices / written[1]))
    if not built:
        raise SystemExit("no languages built")
    if args.from_list:
        missing = [locale for locale in listed if locale not in built]
        if missing:
            raise SystemExit("layouts were not built: %s" % ", ".join(missing))
    if args.dictionaries:
        missing = [locale for locale in dictionaries if locale not in built_dictionaries]
        if missing:
            raise SystemExit("dictionaries were not built: %s" % ", ".join(missing))
    if args.notices:
        (args.notices / "files.list").write_text("\n".join(notice_lines) + "\n", encoding="utf-8")
    print("built %d layouts and %d dictionaries into %s" % (len(built), len(built_dictionaries), args.output))


if __name__ == "__main__":
    main()
