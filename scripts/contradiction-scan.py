#!/usr/bin/env python3
"""Contradiction scan across the specification.

Fails loudly. Intended to run in CI so the specification cannot drift
the way its own subject matter did.
"""
import glob, os, re, sys, collections

SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "spec")
DOCS = {os.path.basename(p): open(p).read() for p in sorted(glob.glob(os.path.join(SPEC, "*.md")))}
ALL = "\n".join(DOCS.values())
findings = []
def fail(check, msg): findings.append((check, msg))

# ---- A. referential integrity -------------------------------------------
for name, body in DOCS.items():
    for ref in set(re.findall(r'\b(\d{2}_[a-z_-]+\.md)\b', body)):
        if ref not in DOCS:
            fail("A1 file-ref", f"{name} -> missing {ref}")

reg = DOCS["20_decisions.md"]
defined = set(re.findall(r'^### ((?:O|G)\d+)', reg, re.M)) | {"G1"}
defined |= set(re.findall(r'\bS(\d+)\b', reg)) and {f"S{n}" for n in re.findall(r'\|\s*\*?\*?S(\d+)', reg)}
defined |= {m for m in re.findall(r'\b(S\d+)\b', reg)}
defined |= {"ADR-010"}
for name, body in DOCS.items():
    for rid in set(re.findall(r'\b([OG]\d+)\b', body)):
        if rid not in defined:
            fail("A2 decision-id", f"{name} cites undefined {rid}")
    for rid in set(re.findall(r'\b(S\d{1,2})\b', body)):
        if rid not in defined:
            fail("A2 decision-id", f"{name} cites undefined {rid}")

# ---- B. test-name coverage ----------------------------------------------
TESTRE = r'`([a-z][a-z0-9]*\.[a-z0-9][a-z0-9-]*)`'
FILEEXT = ("json","md","sh","py","cjs","tsx","ts","sql","yml","yaml","html","txt","lock")
declared = set()          # tests defined in engine/testing docs
for name, body in DOCS.items():
    if name in ("22_traceability.md", "24_build-tasks.md"):
        continue
    declared |= set(re.findall(TESTRE, body))
for src in ("22_traceability.md", "24_build-tasks.md"):
    for t in sorted(set(re.findall(TESTRE, DOCS[src]))):
        if t.rsplit(".",1)[-1] in FILEEXT: continue
        if t not in declared:
            fail("B1 test-undefined", f"{src} cites `{t}` which no engine document defines")

# ---- C. forbidden status vocabulary -------------------------------------
BANNED = ["'final'", '"final"', "'complete'", "'finished'", "'done'", "'closed'"]
for name, body in DOCS.items():
    for tok in BANNED:
        for m in re.finditer(re.escape(tok), body):
            line = body[:m.start()].count("\n") + 1
            ctx = body.splitlines()[line-1]
            low = ctx.lower()
            # Evidence citations quote the legacy defect; they do not use the vocabulary.
            EVIDENCE = ("compared", "legacy", "sites", "permanently false", "wrote",
                        "no check", "drifted", "not", "never", "banned", "synonym", "~~")
            if any(k in low for k in EVIDENCE):
                continue
            fail("C1 status-vocab", f"{name}:{line} uses banned status {tok} -> {ctx.strip()[:70]}")

# ---- D. decision class agreement ----------------------------------------
cls = {}
for m in re.finditer(r'^### ((?:O|G)\d+)[^\n]*?—\s*([A-Z][A-Z-]+)', reg, re.M):
    cls[m.group(1)] = m.group(2)
for name, body in DOCS.items():
    if name == "20_decisions.md": continue
    for rid, klass in cls.items():
        for m in re.finditer(rf'\b{rid}\b[^\n]{{0,60}}', body):
            seg = m.group(0)
            if klass == "DECIDED" and re.search(r'\b(Board decides|working default|undecided|not decided|still open)\b', seg, re.I):
                line = body[:m.start()].count("\n") + 1
                fail("D1 class-conflict", f"{name}:{line} {rid} is {klass} in register but reads: {seg.strip()[:60]}")

# ---- E. stale blocking language -----------------------------------------
STALE = [r'pending G3', r'cheapest unblock', r'value is missing', r'awaiting GBL',
         r'is undecided', r'until decided', r'Interim behaviour', r'does not choose',
         r'typed empty slot', r'as it is reached', r'only correct source',
         r'nobody has decided', r'-equivalent']
for name, body in DOCS.items():
    for pat in STALE:
        for m in re.finditer(pat, body, re.I):
            line = body[:m.start()].count("\n") + 1
            ctx = body.splitlines()[line-1]
            if "used to" in ctx or "previously" in ctx or "withdrawn" in ctx:
                continue
            fail("E1 stale", f"{name}:{line} {pat!r} -> {ctx.strip()[:70]}")

# ---- F. cross-document value agreement ----------------------------------
VALUES = {
    "forfeit score 20-0":      (r'20-0|\[20, 0\]',            r"\bforfeit"),
    "guardian under 18":       (r'guardian_required_under.{0,12}18|under 18', r"guardian"),
    "tie strategy default":    (r'sub_table_restart',         r"multi.?team|tie"),
    "seed durability durable": (r'`durable`|\bdurable\b',      r"seed|durab"),
    "discrepancy warn":        (r"'warn'|`warn`",              r"mismatch|discrep"),
}
for label, (valpat, ctxpat) in VALUES.items():
    holders = [n for n, b in DOCS.items() if re.search(valpat, b)]
    if len(holders) < 2:
        fail("F1 value-orphan", f"{label}: stated in {holders or 'nowhere'} — expected in the register plus at least one engine doc")

# ---- G. structural claims vs DDL ----------------------------------------
ddl = DOCS["05_database.md"]
m = re.search(r'CREATE TABLE game\b.*?;', ddl, re.S)
if m and re.search(r'\b(home_score|away_score)\b', m.group(0)):
    fail("G1 schema-claim", "05_database CREATE TABLE game contains a score column, which the spec forbids")
for col in ("season_points", "season_rebounds", "wins", "losses"):
    for tm in re.finditer(r'CREATE TABLE (team|player)\b.*?;', ddl, re.S):
        if re.search(rf'\b{col}\b', tm.group(0)):
            fail("G1 schema-claim", f"05_database {tm.group(1)} table stores `{col}` — projections must not be stored")

# ---- H. stated counts ---------------------------------------------------
n_docs = len(DOCS)
for name, body in DOCS.items():
    for m in re.finditer(r'\b(\d{2}) documents\b', body):
        if int(m.group(1)) != n_docs:
            fail("H1 count", f"{name} claims {m.group(1)} documents; actual {n_docs}")
tasks = re.findall(r'^### (T\d+)', DOCS["24_build-tasks.md"], re.M)
hi = max(int(t[1:]) for t in tasks)
if len(tasks) != hi:
    fail("H2 task-gap", f"queue declares {len(tasks)} tasks but highest is T{hi}")
for name, body in DOCS.items():
    for m in re.finditer(r'T1[–-]T(\d+)', body):
        if int(m.group(1)) != hi:
            fail("H2 task-range", f"{name} says T1-T{m.group(1)}; queue ends at T{hi}")

# ---- report -------------------------------------------------------------
print(f"Scanned {n_docs} documents, {len(ALL.split())} words, {len(tasks)} tasks.\n")
if not findings:
    print("CONTRADICTION SCAN: CLEAN — no findings.")
    sys.exit(0)
by = collections.OrderedDict()
for c, msg in findings: by.setdefault(c, []).append(msg)
for c, msgs in by.items():
    print(f"[{c}]  {len(msgs)}")
    for m in msgs: print(f"    {m}")
    print()
print(f"CONTRADICTION SCAN: {len(findings)} finding(s).")
sys.exit(1)
