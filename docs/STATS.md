# Real Numbers — is this actually worth it?

Measured on one real installation after ~3 months of daily use across ~10
projects (2–5 sessions/day). Every figure below was measured on the live
system, not estimated. Token counts are `bytes / 4`.

> **Update (2026-07-15): the efficiency pass.** After these numbers were
> published, the flagged waste was actually cut — measured again:
> - **Startup tax: ~26k → ~13.2k tokens/session (−50%)** via a one-line-per-rule
>   lessons index, 1–2 targeted startup searches (with a mandatory wide-pass
>   escalation for past-work questions), 500-char search previews
>   (`full=true` to expand), profile dedupe, and once-per-session nudges.
> - **The store purge happened: 2,813 → 864 chunks.** The 1,670 bulk-import
>   summaries and 279 embedded index-file walls are gone; retrieval quality
>   visibly improved on before/after queries (real decisions now outrank
>   ancient session stubs). Original noise numbers kept below as the cautionary
>   tale they are.

## Headlines

| Metric | Measured |
|---|---|
| Architecture questions, graph vs raw source | **22× cheaper** (96,840 → 4,418 tokens) |
| Semantic search over 3 months of history (~4.8M tokens) | **299 ms**, ~1–2k tokens of results |
| Startup context tax, per session | **~18k tokens** (~20–26k with startup searches) |
| Marginal cost | **$0** — embeddings are local (MiniLM, 384-dim) |

## The system at that point

| Layer | Measured size |
|---|---|
| Auto-memory facts (`MEMORY.md` + fact files) | 67 facts across 5 projects, ~0.6k tok injected |
| Vector store (ChromaDB) | 2,545 chunks, 16.4 MB |
| Session vault (Obsidian) | 2,157 session notes, 18.3 MB |
| Code knowledge graphs | per-repo (e.g. 278 nodes / 268 edges on a mid-size app) |
| Per-repo brain file | ~1.2k tok, auto-refreshed by hooks |

## The tax (what it costs)

Startup context, injected before any work happens:

| Item | Tokens |
|---|---:|
| Global instructions (CLAUDE.md) | 3,550 |
| Lessons file (20 incident-derived rules) | 8,282 |
| Project brain + project instructions | 2,022 |
| Dashboards + user profile | 3,516 |
| Auto-injected memory index | 613 |
| **Total ritual** | **≈ 17,983** |

Add 3–5 semantic searches at session start (~1–2k tokens of results each) →
realistically **20–26k tokens per session**, or **40–130k/day** at 2–5
sessions/day.

Per-edit hook chain (all local compute, zero tokens): code-graph rebuild
400 ms + graph DB update 379 ms + brain refresh 98 ms ≈ **0.9 s per file edit**.
Since then, a fingerprint gate (`scripts/fingerprint_gate.py`) skips both graph
rebuilds when no source file's structure changed — measured **104 ms** for
markdown/comment/formatting edits, an 8.5× cut on the most common edits.
Total storage for everything: ~35 MB.

## The payoff (what it saves)

**Code questions stop costing the codebase.** Answering "how is this app
structured?" on a ~100k-token TypeScript project:

```
read the source .......... 96,840 tokens
read the graph report .....  4,418 tokens   (22x)
```

**History becomes retrievable.** Three months of transcripts ≈ 4.8M tokens —
24× larger than a 200k context window. A semantic query returns the 5 most
relevant memories in 299 ms. Without the store, that history is effectively gone.

**Cold-start questions disappear.** Measured case: a fresh session was asked
about an internal self-hosted tool by its nickname. No memory fact existed →
the session guessed a cloud product and burned an entire exchange failing.
The fix was a 613-token always-injected fact file; every session since answers
instantly. One prevented failure pays for ~30 sessions of that fact's cost.

**Documented-incident math.** Each rule in the lessons file was paid for once:
a ~2-hour wrong-direction debugging session, live credentials nearly shipped in
a client deliverable, a production DB written to by accident. Carrying all 20
lessons costs 8.3k tokens/session; preventing **one** recurrence of the
debugging incident (~100k+ tokens of wasted turns) covers about a week of that.

**Break-even, honestly stated:** the ~20k/session tax pays for itself if it
prevents one wrong-direction exchange or one repeated question per session.
Across the incident log that bar is met on most working days — but it is
genuinely a tax on trivial sessions where none of the context gets used.

## The honest list (what turned out useless)

Four adversarial audits (a separate agent instructed to be brutal) found 32
issues; post-fix scores were 8.5/10 effectiveness, 7/10 practicality. The waste:

- **66% of the vector store was noise** — 1,684 of 2,545 chunks were low-signal
  auto-generated session summaries from a bulk import. The valuable 34% does
  nearly all retrieval work. Curate what you embed; don't bulk-import.
  *(Since purged — see the update at the top. It took three audits flagging it
  before the cleanup beat new feature work onto the schedule.)*
- **Killed: manual per-turn session logging** — an automatic transcript hook
  made it pure double-spend.
- **Killed: re-indexing every session note on every turn** — moved to nightly.
- **Killed: re-embedding the vault on every file edit** — it was also corrupting
  the vector DB via concurrent writes. Nightly now.
- **Killed: a cross-linking script written and never wired to anything.**
  Automation you don't schedule is just documentation.
- **Fixed: a dashboard dedup bug** that silently grew a status file for 73 days
  — at its worst a **~43k token/session** tax. Nobody audits their own
  automation; schedule adversarial audits.
- **Insurance, not recall:** raw transcripts are ~99% write-only. Keep them,
  but as a black-box recorder, not a feature.
- **Joy, not ROI:** the [live 3D graph](VISUALIZER.md). Zero productivity claim.
  Worth it anyway.

## If you're copying this: what's worth it, ranked

| Tier | Layer | Cost | Why |
|---|---|---|---|
| copy first | Auto-memory facts + preferences | <1k tok/session | Highest ROI. Kills repeated questions permanently. |
| copy first | Lessons file (incident → rule) | ~0.4k/rule | Each rule is a failure you only pay for once. |
| if daily use | Per-repo brain file | ~1.2k tok/session | Kills "where were we" on project switches. |
| if daily use | Code knowledge graphs | ~0.9 s/edit | The 22× number. Compounds with codebase size. |
| if multi-project | Vector store (curated) | $0, local | Cross-project recall. Don't bulk-import noise. |
| luxury | Dashboards, rollups, 3D graph | varies | Fun and glanceable. Do these last. |

## Verdict

From the final independent audit: for a solo dev running many parallel projects
with an AI pair, the system "is now unambiguously worth its complexity" — the
injection layers demonstrably prevent repeated real mistakes. The equally real
caveat: roughly a third of everything built was overhead that had to be found
and killed, and it took adversarial audits to find it. **Budget for the pruning,
not just the building.**
