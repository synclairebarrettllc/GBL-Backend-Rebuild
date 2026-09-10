#!/usr/bin/env python3
"""Generate one self-contained bundle per task, from the specification.

A builder opens exactly one file per task instead of navigating 45,000 words.
These are GENERATED — the specification in docs/spec/ is the source of truth.
Re-run after any spec change; the contradiction scan checks they are current.
"""
import os, re, sys, glob, hashlib

ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC  = os.path.join(ROOT, "docs", "spec")
OUT   = os.path.join(ROOT, "docs", "tasks")
DOCS  = {os.path.basename(p): open(p).read() for p in sorted(glob.glob(os.path.join(SPEC, "*.md")))}
QUEUE = DOCS["24_build-tasks.md"]
REG   = DOCS["20_decisions.md"]
TRACE = DOCS["22_traceability.md"]

RULES = """## Rules — non-negotiable

- **One task = one branch = one PR.** Never commit to `main`.
- **Build the values in "Decisions" below.** If you need one that is not there,
  **stop and ask.** Do not pick something reasonable — that is how the previous
  system acquired rules nobody agreed to.
- **Migrations apply before the code that reads them.** This took the old site
  down twice in one day, the second time during live stat entry.
- **Done means evidence** — the command and its output, asserting the resulting
  state. Not "it ran without errors". Every major defect in the old system ran
  without errors.
- **Three failed fix/verify cycles, then stop** and report a root-cause
  hypothesis. Do not guess a fourth time.
- **Do not delete a constraint** without reading why it exists (below).
"""

def sections(doc, refs):
    """Pull the named §sections out of a source document."""
    body, out = DOCS[doc], []
    for ref in refs:
        if "." in ref:                                  # §4.1 -> ### 4.1
            m = re.search(rf'^### {re.escape(ref)}[^\n]*\n.*?(?=\n### |\n## |\Z)', body, re.S | re.M)
        else:
            m = re.search(rf'^## {ref}\.[^\n]*\n.*?(?=\n## |\Z)', body, re.S | re.M)
        if m:
            out.append(m.group(0).rstrip())
    if not refs:                                        # whole document
        out.append(re.sub(r'\A#[^\n]*\n', '', body).strip())
    return out

def parse_spec_line(line):
    """`10_scheduling.md` §3, §6  ->  [('10_scheduling.md', ['3','6'])]"""
    out, cur = [], None
    for tok in re.finditer(r'`(\d\d_[a-z_-]+\.md)`|§\s*(\d+(?:\.\d+)?)(?:\s*[–-]\s*§?\s*(\d+(?:\.\d+)?))?', line):
        doc, s1, s2 = tok.groups()
        if doc:
            cur = (doc, []); out.append(cur)
        elif cur:
            if s2 and "." not in s1:
                cur[1].extend(str(i) for i in range(int(s1), int(s2) + 1))
            else:
                cur[1].append(s1)
    return out

def decisions_for(text):
    """The register entries this bundle's content actually references."""
    ids = set(re.findall(r'\b([OG]\d+)\b', text)) | set(re.findall(r'\b(S\d{1,2})\b', text))
    blocks = []
    for i in sorted(ids, key=lambda x: (x[0], int(x[1:]))):
        m = re.search(rf'^### {i}\b[^\n]*\n.*?(?=\n### |\n## |\Z)', REG, re.S | re.M)
        if m: blocks.append(m.group(0).rstrip()); continue
        for row in re.findall(rf'^\|\s*\*?\*?{i}\*?\*?\s*\|[^\n]*', REG, re.M):
            blocks.append(row.strip())
    return blocks

def trace_for(docs_used):
    nums = {d[:2] for d in docs_used}
    rows = [r for r in re.findall(r'^\|[^\n]*\|[^\n]*\|[^\n]*\|[^\n]*\|[^\n]*\|$', TRACE, re.M)
            if any(f'`{n}`' in r for n in nums)]
    return rows

# ---- parse the queue -----------------------------------------------------
tasks, stage = [], ""
for block in re.split(r'\n(?=## |### T)', QUEUE):
    m = re.match(r'## (Stage \d[^\n—]*)', block)
    if m: stage = m.group(1).strip()
    m = re.match(r'### (T\d+) — ([^\n\[]+)', block)
    if m:
        tasks.append({"id": m.group(1), "title": m.group(2).strip(),
                      "stage": stage, "body": block.strip()})

os.makedirs(OUT, exist_ok=True)
for f in glob.glob(os.path.join(OUT, "T*.md")): os.remove(f)

index = []
for t in tasks:
    spec_line = re.search(r'^\*\*Spec\.\*\*(.+)$', t["body"], re.M)
    refs = parse_spec_line(spec_line.group(1)) if spec_line else []
    parts = [f"# {t['id']} — {t['title']}", f"*{t['stage']} · generated from `docs/spec/`. "
             f"Do not edit — edit the specification and re-run "
             f"`scripts/build-task-bundles.py`.*", "", "## The task", "", t["body"], "", RULES]
    used = []
    if refs:
        parts += ["## Specification"]
        for doc, ss in refs:
            used.append(doc)
            for sec in sections(doc, ss):
                parts += [f"\n<!-- from {doc} -->\n", sec]
    joined = "\n".join(parts)
    dec = decisions_for(joined)
    if dec:
        parts += ["", "## Decisions — build these values, do not invent any", ""] + dec
    tr = trace_for(used or ["24"])
    if tr:
        parts += ["", "## Why these rules exist", "",
                  "| Evidence (what actually broke) | Failure | Rule | Where | Test |",
                  "|---|---|---|---|---|"] + tr
    text = "\n".join(parts).rstrip() + "\n"
    path = os.path.join(OUT, f"{t['id']}.md")
    open(path, "w").write(text)
    index.append((t["id"], t["title"], t["stage"], len(text.split())))

spec_words = sum(len(b.split()) for b in DOCS.values())
lines = ["# Task bundles", "",
         "**Open one file. Build one task.** Each bundle carries the task, the",
         "specification sections it needs, the decision values it must use, and the",
         "incidents behind its rules — nothing else.", "",
         f"Generated from `docs/spec/` ({spec_words:,} words) by",
         "`scripts/build-task-bundles.py`. **Do not edit these files** — edit the",
         "specification and re-run the generator.", "",
         "| Task | What | Stage | Words |", "|---|---|---|---|"]
for tid, title, stage, w in index:
    lines.append(f"| [{tid}](./{tid}.md) | {title} | {stage} | {w:,} |")
avg = sum(w for *_, w in index) // len(index)
lines += ["", f"**Average bundle: {avg:,} words** against a {spec_words:,}-word specification —",
          f"about {spec_words // avg}x less to read per task.", "",
          "## Not in any bundle", "",
          "- `docs/spec/23_verification-handoff.md` — for whoever *verifies* a task,",
          "  and that must not be the session that built it. It instructs the reader",
          "  to attack the code rather than write it.",
          "- `docs/spec/14_import-migration.md` — Phase 2, deferred (D1).", "",
          "## If a bundle is not enough", "",
          "The full specification is in `docs/spec/`. Start at `00_README.md`. If you",
          "had to go there, say so in your report — it means the bundle was missing",
          "something and the generator should be fixed."]
open(os.path.join(OUT, "README.md"), "w").write("\n".join(lines) + "\n")

h = hashlib.sha256()
for name in sorted(DOCS): h.update(name.encode()); h.update(DOCS[name].encode())
open(os.path.join(OUT, ".spec-hash"), "w").write(h.hexdigest() + "\n")

print(f"{len(tasks)} bundles written to docs/tasks/")
print(f"spec {spec_words:,}w  ->  avg bundle {avg:,}w  ({spec_words//avg}x reduction)")
