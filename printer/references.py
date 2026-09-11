"""Sources, and the Chicago notes a document cites them with.

A reference file is json, keyed by the key a document writes: `marx1954`.
Each entry says what kind of thing it is and carries the fields that kind
needs. What is written out is Chicago's notes-and-bibliography form, in its short
note throughout - author, short title, locator - with `Ibid.` when the same
source is cited twice running. The full details of a source are set once, by
the ```references block, rather than in the first note.

    {
      "marx1954": {
        "type": "book",
        "author": ["Karl Marx"],
        "title": "Capital", "volume": "1",
        "place": "London", "publisher": "Penguin", "year": "1954"
      }
    }

A name is either "Karl Marx" or "Marx, Karl": a comma says the surname is
already first, which is the way to write a name the last word is not the
surname of - "Beauvoir, Simone de". Everything else takes the last word.
A name ending in a comma is a body rather than a person - "Laboria
Cuboniks," - and is left whole, never turned around.

The notes come back as markdown, since pandoc sets them: a title is *…* or
“…” and the footnote itself is `^[…]`.
"""

import json
import os
import re

TYPES = ("book", "article", "chapter", "website", "thesis", "report")


class ReferenceError(Exception):
    pass


# --- the file ----------------------------------------------------------------

def load(path):
    """Every source in one file, checked far enough to fail plainly."""
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
    except OSError as e:
        raise ReferenceError(f"cannot read the references at {path}: {e}")
    except ValueError as e:
        raise ReferenceError(f"{os.path.basename(path)} is not readable json: {e}")
    if not isinstance(entries, dict):
        raise ReferenceError(f"{os.path.basename(path)} should be one object, "
                             f"keyed by the key a document cites")
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            raise ReferenceError(f"{key} should be an object of fields")
        kind = entry.get("type")
        if kind not in TYPES:
            raise ReferenceError(f"{key} has type {kind!r}; it takes "
                                 f"{', '.join(TYPES)}")
    return entries


# --- names -------------------------------------------------------------------

def corporate(name):
    """A collective or an institution, written with a trailing comma so it
    is never turned around: `Laboria Cuboniks,`."""
    return name.rstrip().endswith(",")


def surname(name):
    if corporate(name):
        return name.rstrip().rstrip(",")
    if "," in name:
        return name.split(",", 1)[0].strip()
    return name.rsplit(" ", 1)[-1] if " " in name else name


def given_first(name):
    if corporate(name):
        return name.rstrip().rstrip(",")
    if "," not in name:
        return name
    last, _, first = name.partition(",")
    return f"{first.strip()} {last.strip()}".strip()


def surname_first(name):
    if corporate(name):
        return name.rstrip().rstrip(",")
    if "," in name:
        return name
    if " " not in name:
        return name
    first, _, last = name.rpartition(" ")
    return f"{last}, {first}"


def joined(names, last_word="and"):
    names = list(names)
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} {last_word} {names[1]}"
    return ", ".join(names[:-1]) + f", {last_word} {names[-1]}"


def in_note(people):
    """Given-name first, and `et al.` once there are four."""
    if not people:
        return ""
    if len(people) > 3:
        return f"{given_first(people[0])} et al."
    return joined(given_first(p) for p in people)


def in_bibliography(people):
    """The first surname first, so the list sorts; the rest as they read.

    Two names take a comma before the `and` here, where a note does not:
    the first name has been turned around and already holds one, so
    "Deleuze, Gilles, and Félix Guattari".
    """
    if not people:
        return ""
    rest = [given_first(p) for p in people[1:]]
    names = [surname_first(people[0])] + rest
    if len(names) == 2:
        return f"{names[0]}, and {names[1]}"
    return joined(names)


# --- fields ------------------------------------------------------------------

def escape(text):
    """A field as markdown text: the characters that would otherwise end the
    footnote, or start an emphasis that was never asked for."""
    return re.sub(r"([\[\]*_\\])", r"\\\1", str(text))


def emph(text):
    return f"*{escape(text)}*"


def quoted(text):
    return f"“{escape(text)}”"


def pages(text):
    """A range with an en dash, which is what a range is set with."""
    return re.sub(r"(\d)\s*-\s*(\d)", "\\1–\\2", escape(text))


def sentence(parts, end="."):
    """The parts that are there, comma-separated, closed off."""
    body = ", ".join(p for p in parts if p)
    if not body:
        return ""
    return punctuate(body if body.endswith(end) else body + end)


def punctuate(text):
    """American practice, which Chicago follows: a comma or a period that
    falls against a closing quotation mark goes inside it."""
    return text.replace("”,", ",”").replace("”.", ".”")


def before(head, parenthetical):
    """A parenthesis follows what it belongs to with a space, not a comma."""
    return f"{head} {parenthetical}" if parenthetical else head


def published(entry):
    """(Place: Publisher, Year), the parenthesis a note puts them in."""
    place, publisher = entry.get("place"), entry.get("publisher")
    year = entry.get("year", "")
    where = ": ".join(p for p in (place, publisher) if p)
    inside = ", ".join(p for p in (where, year) if p)
    return f"({inside})" if inside else ""


def helpers(entry):
    """The pieces more than one shape wants, in the order Chicago sets
    them: which edition, which volume, who edited it, who translated it."""
    bits = []
    if entry.get("edition"):
        bits.append(f"{escape(entry['edition'])} ed.")
    if entry.get("volume"):
        bits.append(f"vol. {escape(entry['volume'])}")
    if entry.get("editor"):
        bits.append("ed. " + in_note(entry["editor"]))
    if entry.get("translator"):
        bits.append("trans. " + in_note(entry["translator"]))
    return bits


# --- the notes ---------------------------------------------------------------

def short_note(entry, locator):
    """Author, short title, locator - what Chicago repeats a source as."""
    who = entry.get("author") or []
    name = surname(who[0]) if who else ""
    if len(who) == 2:
        name = f"{surname(who[0])} and {surname(who[1])}"
    elif len(who) > 2:
        name = f"{surname(who[0])} et al."
    title = entry.get("short-title") or entry.get("title", "")
    setting = emph if entry["type"] in ("book", "report") else quoted
    return sentence([name, setting(title), pages(locator) if locator else ""])


# --- the bibliography --------------------------------------------------------

def bibliography_entry(entry):
    kind = entry["type"]
    who = in_bibliography(entry.get("author") or [])
    title = entry.get("title", "")

    if kind in ("book", "report"):
        parts = [f"{who}." if who else "", f"{emph(title)}."]
        if entry.get("volume"):
            parts.append(f"Vol. {escape(entry['volume'])}.")
        if entry.get("editor"):
            parts.append("Edited by " + in_note(entry["editor"]) + ".")
        if entry.get("translator"):
            parts.append("Translated by " + in_note(entry["translator"]) + ".")
        where = ": ".join(p for p in (entry.get("place"), entry.get("publisher")) if p)
        parts.append(", ".join(p for p in (where, entry.get("year", "")) if p) + ".")
        return punctuate(" ".join(p for p in parts if p and p != "."))

    if kind == "article":
        number = ", ".join(p for p in (
            escape(entry.get("volume", "")),
            f"no. {escape(entry['issue'])}" if entry.get("issue") else "") if p)
        year = f"({entry['year']})" if entry.get("year") else ""
        stem = " ".join(p for p in (emph(entry.get("journal", "")), number, year) if p)
        tail = f"{stem}: {pages(entry['pages'])}." if entry.get("pages") else f"{stem}."
        return punctuate(" ".join(p for p in (f"{who}." if who else "",
                                              f"{quoted(title)}.", tail) if p))

    if kind == "chapter":
        editors = ("edited by " + in_note(entry["editor"])) if entry.get("editor") else ""
        inner = ", ".join(p for p in (editors, pages(entry.get("pages", ""))) if p)
        where = ": ".join(p for p in (entry.get("place"), entry.get("publisher")) if p)
        return punctuate(" ".join(p for p in (
            f"{who}." if who else "", f"{quoted(title)}.",
            f"In {emph(entry.get('book', ''))}" + (f", {inner}." if inner else "."),
            ", ".join(p for p in (where, entry.get("year", "")) if p) + ".") if p))

    if kind == "website":
        return punctuate(" ".join(p for p in (
            f"{who}." if who else "", f"{quoted(title)}.",
            f"{escape(entry['site'])}." if entry.get("site") else "",
            f"{escape(entry['date'])}." if entry.get("date") else "",
            f"{entry['url']}." if entry.get("url") else "") if p))

    if kind == "thesis":
        return punctuate(" ".join(p for p in (
            f"{who}." if who else "", f"{quoted(title)}.",
            ", ".join(p for p in (escape(entry.get("kind", "PhD diss.")),
                                  escape(entry.get("school", "")),
                                  escape(entry.get("year", ""))) if p) + ".") if p))

    raise ReferenceError(f"no bibliography shape for type {kind!r}")


# --- what a document does with them ------------------------------------------

class Sources:
    """The sources a document has, and what it has cited so far.

    Every note is the short form (roshni, 2026-09-10); what a note depends
    on having come before it is `Ibid.`, so this is still read in document
    order and remembers the citation just written.
    """

    def __init__(self, entries):
        self.entries = entries
        self.used = []      # every source cited, for the bibliography
        self.last = None    # (key, locator) of the citation just written

    def has(self, key):
        return key in self.entries

    def cite(self, key, locator, remark):
        entry = self.entries[key]
        if self.last and self.last[0] == key:
            same = self.last[1] == locator
            note = "Ibid." if same else sentence(["Ibid.", pages(locator)])
        else:
            note = short_note(entry, locator)
        if key not in self.used:
            self.used.append(key)
        self.last = (key, locator)
        return sentence([note.rstrip("."), escape(remark)]) if remark else note

    def bibliography(self):
        """Every source cited, by surname, as markdown paragraphs."""
        def by_name(key):
            people = self.entries[key].get("author") or []
            return (surname(people[0]).lower() if people else "",
                    self.entries[key].get("title", "").lower())

        return [bibliography_entry(self.entries[k]) for k in sorted(self.used, key=by_name)]
