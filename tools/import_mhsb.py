"""Import the permitted MHSB material from a checkout of MHSBai/platform-plugins.

Only these fields are copied, and nothing else: trigger phrases and command names (from
catalog/manifest.yaml and evals/routing/phrases.yaml on cloud/pp8-skills-evals), and the
intake questions, deadline categories (id, name, kind) and attorney-review flags of each
pack fragment (plugins/mhsb-pack-*/fragment/fragment.yaml on cloud/pp9-pack-fragments).
Every capitalised word in a routing phrase that may be a name is replaced with an invented
surname, so that no name can pass. Kept are a short allowlist, acronyms (two or more
capitals), and a sentence-initial word that is a common opener or occurs in lower case in
the imported phrases; see scrub.

Usage: python tools/import_mhsb.py /path/to/platform-plugins
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sources" / "mhsb"
SKILLS_REF = "origin/cloud/pp8-skills-evals"
FRAGMENTS_REF = "origin/cloud/pp9-pack-fragments"

# Words that may stay capitalised. Every other capitalised word is treated as a name and
# replaced, in order of first appearance, with an invented surname from INVENTED.
ALLOWED_CAPITALS = {
    "I",
    "I'm",
    "AI",
    "MHSB",
    "Claude",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
    "Mrs",
    "Mr",
    "Ms",
}
INVENTED = [
    "Wexford",
    "Halvorsen",
    "Nakamura",
    "Brennan",
    "Haddad",
    "Petrov",
    "Achebe",
    "Moreau",
    "Kowalski",
    "Tanaka",
]
_assigned: dict[str, str] = {}
HEADER = (
    "# Imported by tools/import_mhsb.py from MHSBai/platform-plugins. Permitted fields only.\n"
    "# Regenerate with the tool; do not edit by hand.\n"
)


def show(repo: Path, ref: str, path: str) -> Any:
    text = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return yaml.safe_load(text)


# Words that commonly open a request. A capitalised word at the start of a sentence is kept
# when it is one of these, or when the same word occurs in lower case in the imported
# phrases (vocabulary); any other sentence-initial capitalised word is treated as a name.
COMMON_OPENERS = {
    "a", "an", "are", "ask", "can", "check", "could", "create", "do", "does", "draft",
    "explain", "find", "get", "give", "help", "how", "i", "is", "let", "list", "make",
    "my", "need", "our", "please", "prepare", "review", "run", "send", "set", "show",
    "start", "summarise", "summarize", "tell", "the", "turn", "update", "we", "what",
    "when", "where", "which", "who", "why", "will", "would", "write",
}  # fmt: skip
HONORIFICS = {"Mr", "Mrs", "Ms", "Dr", "Mx"}
_WORD = re.compile(r"[A-Z][A-Za-z']*")
_ACRONYM = re.compile(r"[A-Z]{2,}s?")


def vocabulary(phrases: list[str]) -> frozenset[str]:
    """Words that occur in lower case anywhere in the phrases."""
    return frozenset(w for p in phrases for w in re.findall(r"\b[a-z][a-z']*\b", p))


def _sentence_initial(phrase: str, start: int) -> bool:
    """True at the start of the phrase or after a sentence end (., ! or ?), except after an
    honorific such as "Mrs.", where a name follows."""
    before = phrase[:start].rstrip()
    if not before:
        return True
    if before[-1] not in ".!?":
        return False
    words = re.findall(r"[A-Za-z]+", before)
    return not (before[-1] == "." and words and words[-1] in HONORIFICS)


def scrub(phrase: str, known: frozenset[str] = frozenset()) -> str:
    """Replace every capitalised word that may be a name with an invented surname.

    Kept: words in ALLOWED_CAPITALS; all-capital tokens of two or more letters (acronyms
    such as NDA, LLC or PI); and a sentence-initial word whose lower-case form is a common
    opener or occurs in lower case in the imported phrases (known). Every other capitalised
    word, sentence-initial or not, is replaced.
    """

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        if word in ALLOWED_CAPITALS or _ACRONYM.fullmatch(word):
            return word
        lower = word.lower()
        if _sentence_initial(phrase, match.start()) and (lower in COMMON_OPENERS or lower in known):
            return word
        if word not in _assigned:
            if len(_assigned) == len(INVENTED):
                sys.exit("import stopped: more names than invented replacements")
            _assigned[word] = INVENTED[len(_assigned)]
        return _assigned[word]

    return _WORD.sub(replace, phrase)


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(obj, sort_keys=False, allow_unicode=False, width=100)
    path.write_text(HEADER + body, encoding="utf-8")


def import_routing(repo: Path) -> None:
    manifest = show(repo, SKILLS_REF, "catalog/manifest.yaml")
    suite = show(repo, SKILLS_REF, "evals/routing/phrases.yaml")
    raw = [str(p["phrase"]) for p in suite["phrases"]]
    for plugin in manifest["plugins"]:
        for cmd in plugin.get("commands") or []:
            raw += [str(t) for t in cmd.get("triggers", [])]
    known = vocabulary(raw)
    commands: list[dict[str, Any]] = []
    for plugin in manifest["plugins"]:
        for cmd in plugin.get("commands") or []:
            commands.append(
                {
                    "command": cmd["name"],
                    "triggers": [scrub(t, known) for t in cmd.get("triggers", [])],
                }
            )
    for ref in (SKILLS_REF, FRAGMENTS_REF):
        for word in INVENTED:
            found = subprocess.run(
                ["git", "-C", str(repo), "grep", "-qw", word, ref], check=False, capture_output=True
            )
            if found.returncode == 0:
                sys.exit("import stopped: an invented replacement name occurs upstream")
    phrases = [
        {"id": p["id"], "phrase": scrub(p["phrase"], known), "command": p["intended"]}
        for p in suite["phrases"]
    ]
    names = {c["command"] for c in commands}
    unknown = sorted({p["command"] for p in phrases} - names)
    if unknown:
        sys.exit(f"import stopped: phrases name unknown commands {unknown}")
    dump(OUT / "routing.yaml", {"schema_version": 1, "commands": commands, "phrases": phrases})


def import_fragments(repo: Path) -> None:
    listing = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", FRAGMENTS_REF],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    paths = sorted(p for p in listing.split() if p.endswith("fragment/fragment.yaml"))
    for path in paths:
        pack = path.split("/")[1]
        frag = show(repo, FRAGMENTS_REF, path)
        questions = []
        for q in frag["intake_questions"]:
            item: dict[str, Any] = {
                "id": q["id"],
                "prompt": q["prompt"],
                "answer_type": q["answer_type"],
            }
            if q.get("choices"):
                item["choices"] = list(q["choices"])
            item["sensitive"] = q.get("sensitive_tag") is not None
            questions.append(item)
        out = {
            "schema_version": 1,
            "pack": pack,
            "practice_area": frag["practice_area"],
            "intake_questions": questions,
            "deadline_categories": [
                {"id": c["id"], "name": c["name"], "kind": c["kind"]}
                for c in frag["deadline_categories"]
            ],
            "attorney_review_flags": list(frag["attorney_review_flags"]),
        }
        dump(OUT / "fragments" / f"{pack}.yaml", out)
    print(f"imported {len(paths)} fragments")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    repo = Path(sys.argv[1]).resolve()
    import_routing(repo)
    import_fragments(repo)


if __name__ == "__main__":
    main()
