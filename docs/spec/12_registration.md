# 12 — Registration

**Direction: BUILD FRESH.** No legacy component exists. S10 places registration
in v1 scope.

**This document handles real personal data about real people, including minors.**
The security posture in `16_security.md` applies here more than anywhere else in
the system.

---

## 1. Scope — S10

**In scope for v1:**

- Waiver with **legally binding e-signature**
- **Age verification**
- **Walk-up mobile registration** — someone registering on a phone, at the gym,
  minutes before playing
- Captured fields: name, waiver, team preference, emergency contact, phone, email

**Explicitly out of scope:**

- **Payment status (S10, S11).** No in-app payments in v1. Zelle/CashApp details
  are posted; Stripe is later. Registration records **no payment state at all** —
  not a boolean, not a "paid" flag. A field that exists gets filled in
  inconsistently and then trusted.

---

## 2. A registration is not a player

**REQUIREMENT.** Submitting the form creates a `registration` row and **nothing
else**. No Person. No Player. No roster membership.

**Why.** A form submission is an assertion by a member of the public. It might be
a duplicate, a test, a typo, or someone who never shows up. Identity in this
system is created by an operator, not by a stranger with a phone.

The registration → Person → Player → RosterMembership chain is completed only at
`assignToTeam` (`06_mutations.md` §4.9), in one transaction.

---

## 3. Lifecycle

```
submitted ──► accepted ──► assigned
     │             │
     ├──► rejected │
     └──► withdrawn
```

Full transition table in `04_state-machines.md`.

### Identity matching at acceptance

**REQUIREMENT — operator-confirmed, never automatic.** The system may **suggest**
that a registrant matches an existing Person. It may **not** act on the
suggestion.

**Evidence (FACT).** Automatic name-based identity matching in the legacy
importer created two records for one human — carrying 4 and 5 stat lines across
that person's 4 games — and invented a third player entirely. Names are not
identity. Two people named Alex is normal; one person is not two players.

Suggestions may be surfaced with their basis (matching email, matching phone,
prior season with the same name) so the operator decides on evidence rather than
on a name string.

---

## 4. Age verification

**REQUIREMENT.** Date of birth is captured and verified against the season's
minimum age at **acceptance**, not at submission.

**REQUIREMENT.** A registrant under the age of majority requires a
**parent/guardian signature** on the waiver. The waiver artefact records who
signed and in what capacity.

```
season.config.eligibility = {
  minimum_age:            <int>,
  guardian_required_under: <int>,
  age_as_of_date:         <date>      // the age check reference date
}
```

**`age_as_of_date` is not optional.** "18 years old" is meaningless without a
date — a player who turns 18 mid-season is either eligible all season or not,
and the league must say which. Computing age against "today" makes eligibility
change silently during the season.

---

## 5. The waiver — O11

**REQUIREMENT (S10).** The waiver is legally binding and its signature is
recorded as a durable artefact.

**UNKNOWN — O11.** The e-signature **vendor** is a separate, later concern:
"ideally connected rather than built fully custom."

**Typed slot:**

```
registration.waiver = {
  document_version: <string>,        // which waiver text was signed
  signed_at:        <timestamp>,
  signer_name:      <string>,
  signer_capacity:  'self' | 'guardian',
  artifact_ref:     <UNKNOWN — O11: vendor reference | stored artifact id>,
  ip_address:       <string | null>
}
```

**REQUIREMENT regardless of vendor.** `document_version` is stored. A waiver that
does not record *which text* was agreed to is not defensible — the league cannot
later show what the person actually signed.

**REQUIREMENT.** Do not build a custom signature-capture flow in v1. The slot
holds a reference; the vendor fills it. A hand-rolled e-signature carries legal
risk the league has not accepted and this specification will not create.

---

## 6. Walk-up registration

**REQUIREMENT (S10, S19).** The flow works on a phone, standing in a gym, on gym
wifi, in under two minutes.

Design consequences:

- Minimum required fields; everything else optional and completable later.
- Every step persists — the same progressive-save discipline as the tracker
  (`07_statistics.md` §5). A dropped connection at the waiver step must not
  discard the name and phone already entered.
- Submission is **idempotent** by `operation_id`. A double-tap on a slow
  connection creates one registration, not two.

**Evidence for why idempotency is called out (FACT).** Duplicate-creation under
retry is not hypothetical in this system's history — the importer's duplicate
players came from exactly this class of problem.

---

## 7. Team assignment

`assignToTeam` (`06_mutations.md` §4.9) is one transaction creating Person,
Player, RosterMembership and the status change.

**Capacity** comes from config:

```
season.config.roster = {
  max_players_per_team: <int | null>,
  roster_lock_date:     <UNKNOWN — O6: date | null>
}
```

**UNKNOWN — O6** governs roster lock dates and whether a player may appear for
two teams in a season. Registration reads that config; it does not decide.

---

## 8. Personal data

**REQUIREMENT.** Registration data is **admin-only**. Emergency contacts, phone
numbers, email addresses and dates of birth are never exposed on a public
endpoint, never included in a public player object, and never returned by the
read-only AI access surface (S12).

**REQUIREMENT.** The public representation of a player is: display name, team,
jersey number, statistics. Nothing from the registration record.

**Evidence (FACT).** This repository already contains real player names in a
tracked seed file, which is why the repository is private. The same care applies
to every field captured here — with the difference that these fields are
contact details and minors' birthdates, which are materially more sensitive than
names.

**REQUIREMENT.** Registration PII is excluded from logs, from error messages, and
from any URL or query string.

---

## 9. What registration never does

| Never | Because |
|---|---|
| Creates a Player on submission | A form submission is not an identity |
| Auto-matches a Person by name | Two records for one human (FACT) |
| Records payment status | S10/S11 — out of scope; a half-maintained field is worse than none |
| Exposes contact details publicly | Real PII, including minors' |
| Verifies age against "today" | Eligibility would change silently mid-season |
| Implements custom e-signature | Legal risk the league has not accepted |
| Stores a waiver without its document version | Unenforceable |

---

## 10. Acceptance tests

| Test | Asserts |
|---|---|
| `registration.submit-creates-only-registration` | No Person, Player or membership is created on submit |
| `registration.no-auto-match` | Identical names produce a suggestion, never a link |
| `registration.assign-atomic` | Injected failure leaves zero of the four rows |
| `registration.idempotent-submit` | Double submission with one `operation_id` creates one row |
| `registration.progressive-save` | Partial data survives an interrupted walk-up flow |
| `registration.age-as-of-date` | Eligibility is computed against the configured date, not now |
| `registration.guardian-required` | A minor without a guardian signature cannot be accepted |
| `registration.waiver-version-recorded` | Acceptance without a waiver version is rejected |
| `registration.no-payment-field` | Schema check: no payment status column exists |
| `registration.pii-not-public` | No public endpoint returns phone, email, DOB or emergency contact |
| `registration.pii-not-logged` | PII appears in no log line and no error payload |
| `registration.capacity-enforced` | Assignment beyond `max_players_per_team` is rejected |
