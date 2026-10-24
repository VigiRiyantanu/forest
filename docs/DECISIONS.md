# Architectural and Design Decisions

This document logs all key design choices, assumptions, and architectural decisions made while building **Animal Playground**.

## 1. Zero Network Dependencies Except `src/llm.py`
- **Context:** Hard rule 7 dictates that the agent module has no tools, no browsing, and no file or network access. Acceptance check 6 explicitly requires that a grep test verifies no module besides `src/llm.py` imports any network library.
- **Decision:** All HTTP calls to LLM providers (Anthropic, Gemini, OpenAI) in `src/llm.py` are implemented using Python's standard library `urllib.request`. Zero external networking libraries (such as `requests`, `aiohttp`, `httpx`) are imported anywhere in the codebase. The default provider is `mock`, requiring zero network access and zero API keys during build and local testing.

## 2. Deterministic Cast Rotation & Slot Assignment
- **Context:** Section 2 and 5 define 6 animals and 3 turns per day across Day A and Day B.
- **Decision:** The active animal is always `cast[counter % 6]`. The time slot is always `["pagi", "siang", "malam"][counter % 3]`. Day type is `"A"` if `(counter // 3) % 2 == 0` else `"B"`. This is strictly derived from `counter` and never from the host system wall clock, preserving determinism across test mode, cron delays, and manual triggers.

## 3. Cycle & Quota Management
- **Context:** Each cycle consists of 6 turns (`counter // 6`). An animal can interact at most `interactions_per_cycle` (default 1) times per cycle.
- **Decision:** `state["cycle"]["id"]` tracks the cycle ID (`counter // 6`). When `counter // 6` advances, `interactions_used` in `state["cycle"]` is reset to `{}`. The validator checks if `interactions_used[slug] >= interactions_per_cycle` before approving an interaction.

## 4. Interaction Target Eligibility
- **Context:** Hard rule 4 states an animal cannot interact with itself, and can only target an animal that has already spoken at least once.
- **Decision:** Target eligibility is determined by scanning the previous chat history (`chat.log`). An animal is eligible if it has authored at least one prior entry. Turn 0 cannot be an interaction turn because no target has spoken yet.

## 5. Anti-Greeting & Message Quality Checks
- **Context:** Section 9 requires rejecting greetings in any language variant (e.g., `halo`, `hai`, `hi`, `hey`, `hello`, `selamat pagi/siang/malam`, `apa kabar`, `salam`), repetition exceeding similarity threshold 0.6, markdown formatting, code fences, URLs, and persona confusion.
- **Decision:** Regex and normalized substring matching are used. For similarity, `difflib.SequenceMatcher` compares the message against the last 10 messages from `chat.log`. The validator returns structured, human-readable error messages so the agent retry loop can feed the exact failure back to the LLM.

## 6. Marker-Based README Rendering
- **Context:** `README.md` contains manual zones that must never be altered, and generated zones delimited by HTML markers (`<!-- CHAT:START -->`, `<!-- ROSTER:START -->`, `<!-- KNOWLEDGE:START -->`).
- **Decision:** `src/render_readme.py` parses `README.md` and replaces exclusively the text strictly between each `<!-- <ZONE>:START -->` and `<!-- <ZONE>:END -->` pair. Slices before the first marker and after the last marker, as well as between markers, remain strictly byte-identical.

## 7. Chat Log Format and Console Block Rendering
- **Context:** Section 10 requires a console-styled chat tail in `README.md` and an append-only `chat.log`.
- **Decision:** Each turn entry is formatted with timestamp in `timezone` (`Asia/Jakarta`), animal emoji, slug, slot, personality snippet, indented wrapped message lines (`  > ...`), and optional metadata brackets for learning/discovering and interactions. Plain note turns omit the bracket line. `README.md` displays the last `readme_chat_tail` (default 20) entries inside a ```console fence ending with `playground@desa-hewan:~$ █`.

## 8. Playground Notes
- **Context:** Section 3 references `playground/<turn>-<slug>.md` (≤ `max_words_free` words).
- **Decision:** When an animal completes a turn, a markdown note capturing its thoughts/message is optionally generated in `playground/{counter}-{slug}.md`. It is staged and committed alongside the turn.

## 9. Git Operations & Safe Push
- **Context:** Commits must be made with per-animal identities (`<name> <slug@playground.local>`), only staging specific files. Push should be conditional.
- **Decision:** `src/gitops.py` runs git commands with local subprocess environment variables (`GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL`) without altering global git configuration. Push is performed only if `config["push"]` is true, not dry-run, and a git remote exists.

## 10. Process Concurrency Locking
- **Context:** Section 12 requires acquiring `.tick.lock` to prevent overlapping runs.
- **Decision:** A file-based lock `.tick.lock` records the active PID and timestamp. If the lock is held and the process is still running, `tick.py` exits 0 quietly without corrupting state. Stale locks from terminated processes are safely overridden.
