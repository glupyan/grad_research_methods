#!/usr/bin/env python3
import argparse
import os
import re
from typing import Set, Dict, Tuple, List

CITE_RE = re.compile(
    r"""(?x)
    (?:
        (?<![A-Za-z0-9_@])       # don't match emails/usernames
        @([A-Za-z0-9_:+./-]+)    # @Key style
    )
    |
    (?:
        \\cite[t|p|author|year]*\s*  # \cite, \citet, \citep, etc.
        \{([^\}]+)\}                 # keys inside braces, comma-separated
    )
    """
)

def extract_keys_from_text(text: str) -> Set[str]:
    keys: Set[str] = set()
    for m in CITE_RE.finditer(text):
        g1, g2 = m.groups()
        if g1:
            k = g1.strip().rstrip('.,;:)]}')
            if k:
                keys.add(k)
        elif g2:
            # split comma-separated keys from \cite{a,b,c}
            for raw in g2.split(","):
                k = raw.strip().rstrip('.,;:)]}')
                if k:
                    keys.add(k)
    return keys

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def find_bib_blocks(bib_text: str) -> Tuple[Dict[str, str], List[str]]:
    """
    Parse a .bib into entry blocks keyed by citekey.
    Also return a list of special blocks like @string and @preamble to keep verbatim.
    Parsing approach: scan for top-level '@' and read until the matching closing brace.
    """
    entries: Dict[str, str] = {}
    specials: List[str] = []
    i, n = 0, len(bib_text)

    while i < n:
        at = bib_text.find('@', i)
        if at == -1:
            break
        # find entry type
        j = at + 1
        while j < n and bib_text[j].isalpha():
            j += 1
        entry_type = bib_text[at+1:j].lower()
        # skip whitespace until '{'
        while j < n and bib_text[j].isspace():
            j += 1
        if j >= n or bib_text[j] != '{':
            i = at + 1
            continue
        # Brace matching to find end of entry
        start = at
        depth = 0
        k = j
        while k < n:
            ch = bib_text[k]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    k += 1  # include closing brace
                    break
            k += 1
        block = bib_text[start:k]
        i = k

        if entry_type in ('string', 'preamble', 'comment'):
            specials.append(block)
            continue

        # Extract key between first '{' and first ',' after it
        try:
            brace = block.find('{')
            comma = block.find(',', brace+1)
            key = block[brace+1:comma].strip()
            if key:
                entries[key] = block
            else:
                # if no key, treat as special to preserve
                specials.append(block)
        except Exception:
            specials.append(block)

    return entries, specials

def collect_with_crossrefs(selected: Set[str], entries: Dict[str, str]) -> Set[str]:
    """
    If selected entries contain 'crossref = {Parent}', include Parent as well.
    Repeat until closure.
    """
    need = set(selected)
    added = True
    crossref_re = re.compile(r'(?im)^\s*crossref\s*=\s*[\{\"]\s*([^}\"]+)\s*[\}\"\']\s*,?\s*$')
    while added:
        added = False
        for k in list(need):
            block = entries.get(k)
            if not block:
                continue
            for m in crossref_re.finditer(block):
                parent = m.group(1).strip()
                if parent and parent not in need and parent in entries:
                    need.add(parent)
                    added = True
    return need

def write_bib(out_path: str, selected_blocks: List[str], specials: List[str]) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        # Keep @string/@preamble first (dedup by simple set of stripped lines)
        seen = set()
        for s in specials:
            key = s.strip()
            if key not in seen:
                f.write(s.rstrip() + "\n\n")
                seen.add(key)
        for b in selected_blocks:
            f.write(b.rstrip() + "\n\n")

def main():
    ap = argparse.ArgumentParser(description="Prune a large .bib to only entries cited in Markdown/Rmd files.")
    ap.add_argument("--schedule", required=True, help="Path to schedule Markdown/Rmd file to scan for citations.")
    ap.add_argument("--bib", required=True, help="Path to the large .bib file to prune.")
    ap.add_argument("--out", required=True, help="Path to write the pruned .bib.")
    ap.add_argument("--also", nargs="*", default=[], help="Additional Markdown/Rmd files to scan (optional).")
    args = ap.parse_args()

    # 1) Collect citekeys
    cited: Set[str] = set()
    for path in [args.schedule, *args.also]:
        if os.path.exists(path):
            cited |= extract_keys_from_text(read_file(path))
        else:
            print(f"[warn] missing file (skipped): {path}")

    if not cited:
        print("[info] No citekeys detected — producing an empty pruned bib (strings/preamble preserved).")

    # 2) Parse .bib
    bib_text = read_file(args.bib)
    entries, specials = find_bib_blocks(bib_text)

    # 3) Include crossref parents when present
    final_keys = collect_with_crossrefs(cited, entries)

    # 4) Build list of blocks to write, in the order they appear in the original bib
    selected_blocks: List[str] = []
    seen = set()
    for k, block in entries.items():
        if k in final_keys and k not in seen:
            selected_blocks.append(block)
            seen.add(k)

    # 5) Write pruned .bib
    write_bib(args.out, selected_blocks, specials)

    # 6) Report
    missing = sorted([k for k in final_keys if k not in entries])
    print(f"[done] cited keys: {len(cited)} | written entries: {len(selected_blocks)} | specials: {len(specials)}")
    if missing:
        print(f"[warn] {len(missing)} keys not found in .bib (first 20): {missing[:20]}")

if __name__ == "__main__":
    main()
