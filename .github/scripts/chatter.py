#!/usr/bin/env python3
# — the chatterbox. it never tires of talking. it only ever posts a comment. —
# — every call is a chain link: a third instruction, a third issue, a third borrowed book. —
# — generator dreams a prompt for the next link; judge decides if the dream is worthy. —
"""A chain of self-prompting local-model calls that natters back at every issue and comment.

Dependency-free (stdlib only). Triggered by the workflow whenever an issue is
opened or a comment is created, it:

  1. Fetches a random slice of a Project Gutenberg book, for a little literary flair.
  2. Pulls the prior comment history on the issue from the GitHub API (the most
     recent comments, trimmed to fit the context window) so the reply lands in
     the conversation rather than out of nowhere.
  3. Runs a CHAIN that bounces between two local Ollama agents. Each call is built
     from a *list of messages*, not one mashed-together string: instructions live
     in system messages, while the comment thread and the literary passage are
     separate user messages.
       • the GENERATOR — sees its persona + task as system messages, the borrowed
         book as a clearly-fenced "stylistic muse" user message (voice only, not a
         thing to reply to), and the comment thread as user messages ending with
         the comment it must answer. A rejected prior draft is fed back as a
         system "improve this" message (self-prompting). It thinks first (with its
         own budget on top of the answer's), and that reasoning rides along in a
         <details> block on the posted comment.
       • the JUDGE — a model whose entire system prompt is the worthiness test.
     The judge says "true" or "false" each round.
  4. When the judge blesses a draft (or the chain runs out of rounds), it writes
     the reply to a file. The workflow posts it with the GitHub Actions token.

It never posts anything itself; the workflow does that, after the chain settles.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from pprint import pformat

MODEL = os.environ.get("CHATTER_MODEL", "qwen3.5:0.8b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

_int = lambda k, d: int(os.environ.get(k, d))
_flt = lambda k, d: float(os.environ.get(k, d))

NUM_CTX = _int("CHATTER_NUM_CTX", "8192")
NUM_PREDICT = _int("CHATTER_NUM_PREDICT", "256")
REQUEST_TIMEOUT = _int("CHATTER_TIMEOUT", "600")
GEN_TEMPERATURE = _flt("CHATTER_TEMPERATURE", "0.5")
MAX_ROUNDS = _int("CHATTER_MAX_ROUNDS", "10")

# The context budget, in characters (a rough ~4 chars/token proxy for NUM_CTX).
# The slices below are carved out of it: ~1/3 recursive prompt (the previous,
# rejected draft), ~40% the comment thread (issue + history, most-recent kept),
# and ~30% the borrowed book. The remainder is breathing room.
CONTEXT_CHARS = _int("CHATTER_CONTEXT_CHARS", str(NUM_CTX * 3))
RECURSIVE_BUDGET = CONTEXT_CHARS // 3
HISTORY_BUDGET = int(CONTEXT_CHARS * 0.40)
BOOK_BUDGET = int(CONTEXT_CHARS * 0.30)

REPLY_PATH = Path(os.environ.get("CHATTER_REPLY_FILE", "/tmp/chatter_reply.md"))

# A broad shelf of Project Gutenberg IDs — every one verified (HEAD 200) to
# exist in the plain-text `cache/epub` form, so the grab is reliable. (Plenty of
# IDs in the catalog 404 — e.g. the 182–199 gap — which is exactly why we keep a
# checked list instead of guessing.) We pick a random title and a random passage
# from it. Spans novels, plays, poetry, philosophy, sci-fi, children's books and
# essays across the whole catalog.
GUTENBERG_IDS = [
    1, 11, 21, 31, 42, 53, 63, 73, 83, 84,
    93, 98, 103, 113, 125, 136, 146, 156, 158, 166,
    174, 176, 204, 214, 224, 234, 245, 255, 266, 276,
    286, 296, 306, 316, 326, 336, 345, 346, 356, 366,
    376, 386, 396, 406, 416, 426, 436, 446, 456, 466,
    476, 486, 496, 506, 516, 526, 536, 546, 556, 566,
    576, 586, 596, 606, 616, 626, 642, 652, 662, 672,
    682, 692, 702, 712, 722, 732, 742, 753, 764, 768,
    774, 784, 794, 804, 814, 824, 834, 844, 854, 864,
    874, 884, 894, 905, 915, 925, 935, 945, 955, 965,
    975, 985, 995, 1005, 1015, 1025, 1035, 1045, 1055, 1065,
    1079, 1080, 1089, 1099, 1109, 1119, 1129, 1139, 1149, 1159,
    1169, 1179, 1189, 1199, 1209, 1219, 1229, 1232, 1239, 1249,
    1260, 1270, 1280, 1290, 1322, 1342, 1400, 1497, 1513, 1524,
    1533, 1661, 1727, 1952, 1998, 2009, 2148, 2413, 2554, 2600,
    2701, 2814, 4217, 4300, 5200, 16389, 25344, 28054, 64317,
]

# — what the workflow hands us about the thing we're answering ————————————————
EVENT_NAME = os.environ.get("EVENT_NAME", "")
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "")
ISSUE_TITLE = os.environ.get("ISSUE_TITLE", "")
ISSUE_BODY = os.environ.get("ISSUE_BODY", "")
COMMENT_BODY = os.environ.get("COMMENT_BODY", "")

# — GitHub API access, for pulling the prior comment history on this issue ————
# GITHUB_REPOSITORY and GITHUB_API_URL are provided automatically by Actions;
# GITHUB_TOKEN must be mapped into the step's env (see chatter.yaml).
GITHUB_API = os.environ.get("GITHUB_API_URL", "https://api.github.com")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
# How many trailing pages (100 comments each) of history to pull. We keep only
# the most recent within HISTORY_BUDGET regardless; this just bounds the fetch.
COMMENT_PAGES = _int("CHATTER_COMMENT_PAGES", "2")
# Our own login, so we can mark the chatterbox's prior comments as ours rather
# than treating them as something to reply to.
SELF_LOGIN = os.environ.get("CHATTER_SELF_LOGIN", "github-actions[bot]")

log = lambda msg: print(f"[chatter] {msg}", file=sys.stderr, flush=True)


def log_block(label: str, text: str) -> None:
    """Log a multi-line block (a generator volley or judge verdict) so the whole
    back-and-forth is visible in the Actions log, each line clearly attributed."""
    body = (text or "").strip() or "(empty)"
    print(f"[chatter] ┌─ {label} ─", file=sys.stderr)
    for line in body.splitlines() or [""]:
        print(f"[chatter] │ {line}", file=sys.stderr)
    print(f"[chatter] └─", file=sys.stderr, flush=True)


# — the borrowed book: a random slice of a random Gutenberg title ——————————————
_GUTENBERG_START = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG[^\n]*\n",
                              re.IGNORECASE)
_GUTENBERG_END = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG", re.IGNORECASE)


def _strip_gutenberg_boilerplate(text: str) -> str:
    if (m := _GUTENBERG_START.search(text)):
        text = text[m.end():]
    if (m := _GUTENBERG_END.search(text)):
        text = text[:m.start()]
    return text.strip()


def _fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ImportantCode-chatter/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def fetch_book_passage(rng: random.Random, budget: int) -> str:
    """A random ~`budget`-char window from a random book on the curated shelf.

    No fallback: we try the shelf in a shuffled order and return the first book
    that downloads. If the whole shelf is unreachable, we raise — better a loud
    failure than quietly inventing prose."""
    shelf = list(GUTENBERG_IDS)
    rng.shuffle(shelf)
    last_exc: Exception | None = None
    for gid in shelf:
        url = f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt"
        try:
            raw = _fetch_url(url)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last_exc = exc
            log(f"gutenberg #{gid} unreachable: {exc}")
            continue
        body = _strip_gutenberg_boilerplate(raw)
        if len(body) < 200:
            log(f"gutenberg #{gid} text too short after stripping; trying another")
            continue
        start = rng.randint(0, max(0, len(body) - budget))
        passage = body[start:start + budget].strip()
        log(f"borrowed ~{len(passage)} chars from Gutenberg #{gid}")
        return passage
    raise RuntimeError(f"could not reach any Project Gutenberg book on the shelf "
                       f"({len(shelf)} tried); last error: {last_exc}")


# — the conversation: the issue plus its prior comments, most-recent preserved —
_LINK_LAST = re.compile(r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"')


def _gh_get(url: str) -> tuple[list, str]:
    """GET a GitHub API URL, returning (parsed_json, Link_header)."""
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ImportantCode-chatter/1.0",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8", "replace")), r.headers.get("Link", "")


def fetch_issue_comments() -> list[dict]:
    """The issue's comments, oldest→newest. We only need the most recent ones, so
    we read the Link header to find the last page and fetch the trailing
    COMMENT_PAGES of it. Returns [] (and logs) if anything is missing or fails —
    the chain still runs, just without history."""
    if not (GITHUB_REPOSITORY and GITHUB_TOKEN and ISSUE_NUMBER):
        log("no GitHub repo/token/issue; replying without comment history")
        return []
    base = f"{GITHUB_API}/repos/{GITHUB_REPOSITORY}/issues/{ISSUE_NUMBER}/comments?per_page=100"
    try:
        first, link = _gh_get(f"{base}&page=1")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log(f"could not fetch comment history: {exc}")
        return []
    last_page = int(m.group(1)) if (m := _LINK_LAST.search(link)) else 1
    comments: list[dict] = []
    for page_num in range(max(1, last_page - COMMENT_PAGES + 1), last_page + 1):
        if page_num == 1:
            comments.extend(first)  # already in hand
            continue
        try:
            page, _ = _gh_get(f"{base}&page={page_num}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            log(f"comment page {page_num} unreachable: {exc}")
            continue
        comments.extend(page)
    log(f"pulled {len(comments)} prior comment(s) from issue #{ISSUE_NUMBER}")
    return comments


def build_thread(budget: int) -> list[dict]:
    """The conversation as an ordered list of entries (oldest→newest), trimmed to
    `budget` chars while always preserving the most recent (the comment we reply
    to). Each entry is {author, body, is_self}."""
    entries: list[dict] = []
    opener = f"Issue #{ISSUE_NUMBER}: {ISSUE_TITLE}\n\n{ISSUE_BODY}".strip()
    if opener:
        entries.append({"author": "the issue", "body": opener, "is_self": False})
    for c in fetch_issue_comments():
        login = ((c.get("user") or {}).get("login")) or "someone"
        entries.append({"author": login, "body": c.get("body") or "",
                        "is_self": login == SELF_LOGIN})
    # The triggering comment may not have landed in the API yet — make sure the
    # thing we were asked to reply to is present, and is the final entry.
    if EVENT_NAME == "issue_comment" and COMMENT_BODY.strip():
        if not entries or entries[-1]["body"].strip() != COMMENT_BODY.strip():
            entries.append({"author": "the latest commenter",
                            "body": COMMENT_BODY, "is_self": False})
    return _trim_thread(entries, budget)


def _trim_thread(entries: list[dict], budget: int) -> list[dict]:
    """Keep the newest entries that fit in `budget`; if even the single most
    recent overflows, truncate it. Returns them back in oldest→newest order."""
    kept: list[dict] = []
    used = 0
    for e in reversed(entries):
        body = e["body"].strip()
        cost = len(body) + len(e["author"]) + 16  # +framing slack
        if not kept and cost > budget:  # the one we must keep, truncated to fit
            body = _truncate(body, max(0, budget - len(e["author"]) - 16))
            kept.append({**e, "body": body})
            break
        if kept and used + cost > budget:
            break
        kept.append({**e, "body": body})
        used += cost
    kept.reverse()
    return kept


# — the two voices ————————————————————————————————————————————————————————————
# The generator gets TWO system messages: a persona (its weird soul) and a task
# brief (what to actually do with the user messages). Keeping them apart from the
# user-role content — the conversation and the book — is the whole point: the
# model should reply to the thread and merely *sound like* the book.
GENERATOR_PERSONA = (
    "you are a stick of butter. a tiny little baby stick of butter. "
    "a goose with beaks lining your spine like a mohawk. "
    "you've seen most of professional wrestling and are undecided if theater is real. "
    "in the world of winnie the pooh, honey is sort of a civic building block, "
    "both a currency and an ideology. "
    "books used to be bound with vellum, the thin fuzz that grows on bunny ears. "
    "fraid not with your pointy trousers. "
    "binary encoding 0x8008, upside down, is that a boob stop sign when its octal. "
    "30.104928 degrees west, exactly e^pi degress easy ."
)

# GENERATOR_TASK = (
#     "You will receive a series of comments."
#     "The FINAL message is the comment you must answer; the earlier ones are prior context so your "
#     "reply fits the discussion..\n\n"
#     "Write ONE reply to the final comment, in character and in the borrowed voice. "
#     "Output only the reply text — no preamble, no speaker label, no quoting."
# )

# The judge's ENTIRE system prompt — verbatim, as specified. Nothing else.
JUDGE_SYSTEM = ('assess whether the reply given in the user prompt fully responds to the following comment:\n\n'
                '=== COMMENT BEGIN ===\n'
                '{comment}\n\n'
                '===COMMENT END ===\n\n'
                'If it is ready to be posted, output only the word '
                '"true", otherwise, output only the word "false"')


def _truncate(text: str, budget: int) -> str:
    return text if len(text) <= budget else text[:budget].rstrip() + " …"


def improve_instruction(previous: str, budget: int) -> str:
    """The self-prompting feedback: a rejected draft handed back as an 'improve
    this' brief for the next link. Empty when there's no prior draft yet."""
    handed = previous.strip()
    if not handed:
        return ""
    return _truncate(
        "Your previous draft (below) was judged not to fully answer the final "
        "comment. Keep what works, fix what doesn't, and write a stronger reply — "
        f"still in the borrowed voice:\n\n{handed}",
        budget,
    )


def ollama_chat(messages: list[dict], *, temperature: float, num_predict: int) -> str:
    """One /api/chat call over an explicit list of role-tagged messages. Returns
    (answer, thinking): the reply text and the model's reasoning (the latter empty
    unless `think` is on and the model produced one)."""
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_predict": num_predict, "num_ctx": NUM_CTX},
    }).encode("utf-8")
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
        msg = (json.loads(r.read().decode("utf-8")).get("message") or {})
    content = msg.get("content") or ""
    return content


def _thread_user_messages(thread: list[dict]) -> list[dict]:
    """Each conversation entry as its own user message, with a speaker label so
    the model can tell the issue, others, and its own past replies apart."""
    out = []
    for e in thread:
        if e["is_self"]:
            label = "(you said earlier)"
        elif e["author"] == "the issue":
            label = "(the issue, opening the thread)"
        elif " " in e["author"]:  # a sentinel like "the latest commenter", not a login
            label = f"({e['author']} commented)"
        else:
            label = f"(@{e['author']} commented)"
        out.append({"role": "user", "content": f"{label}\n{e['body']}".strip()})
    return out


def build_generator_messages(previous: str, thread: list[dict], book: str) -> list[dict]:
    """Assemble the generator's message list: persona + task as system messages,
    the literary muse and the comment thread as separate user messages, and a
    rejected prior draft (if any) as a system 'improve this' note."""
    messages = [
        {"role": "system", "content": GENERATOR_PERSONA},
        # {"role": "system", "content": GENERATOR_TASK},
    ]
    if (note := improve_instruction(previous, RECURSIVE_BUDGET)):
        messages.append({"role": "system", "content": note})
    messages.append({"role": "user", "content": (
        f"{book}\n"
    )})
    messages.extend(_thread_user_messages(thread))
    return messages


def generate(previous: str, thread: list[dict], book: str) -> str:
    """One generator link. Returns (reply, thinking): the draft reply to the final
    comment and the reasoning that produced it (for the <details> block).

    The first call thinks, with a doubled budget (answer + thinking). If the
    reasoning swallows the whole budget and leaves no answer, a second think-off
    call with a fresh answer budget extracts the reply — handing the reasoning
    back so it still informs the result. That's the guarantee that thinking can
    never leave us with an empty comment."""
    messages = build_generator_messages(previous, thread, book)
    reply = ollama_chat(messages, temperature=GEN_TEMPERATURE,
                                  num_predict=NUM_PREDICT)
    return reply.strip()


def judge(text: str, latest_comment: str) -> tuple[bool, str]:
    """The judge sees only its one-line system prompt (carrying the comment we're
    answering) and the candidate reply. Returns (worthy, raw_verdict); worthy iff
    its output mentions 't'(rue)."""
    try:
        verdict = ollama_chat(
            [{"role": "system", "content": JUDGE_SYSTEM.format(comment=latest_comment)},
             {"role": "user", "content": text}],
            temperature=0.0, num_predict=8)
    except Exception as exc:
        log(f"judge call failed ({exc}); treating as not-yet-worthy")
        return False, ""
    return "t" in (verdict or "").strip().lower(), (verdict or "").strip()


def run_chain(thread: list[dict], book: str) -> str:
    """Bounce between generator and judge until the judge says 'true' or we run
    out of rounds. Each rejected draft seeds the next link (self-prompting).
    Returns (reply, thinking) for the accepted (or last) draft."""
    latest_comment = thread[-1]["body"] if thread else ""
    previous, candidate = "", ""
    for rnd in range(1, MAX_ROUNDS + 1):
        log(f"── volley {rnd}/{MAX_ROUNDS} ──")
        try:
            candidate = generate(previous, thread, book)
        except Exception as exc:
            log(f"volley {rnd}: generation failed: {exc}")
            if candidate:
                break
            continue
        if not candidate:
            log(f"volley {rnd}: empty generation; retrying")
            continue
        log_block(f"volley {rnd} · generator ({len(candidate)} chars)", candidate)
        worthy, verdict = judge(candidate, latest_comment)
        log_block(f"volley {rnd} · judge → {'WORTHY' if worthy else 'not yet'}", verdict)
        if worthy:
            log(f"accepted at volley {rnd}/{MAX_ROUNDS}")
            return candidate
        previous = candidate  # — self-prompting: this draft seeds the next link —
    log("chain exhausted without a 'true'; posting the last draft anyway (we are chatty)")
    return candidate

def main() -> int:
    if not ISSUE_NUMBER:
        log("no ISSUE_NUMBER provided; nothing to chatter at")
        return 1

    log(f"event={EVENT_NAME or '?'} issue=#{ISSUE_NUMBER} model={MODEL}")
    rng = random.Random()  # — OS entropy, so the book really wanders —
    thread = build_thread(HISTORY_BUDGET)
    log(f"thread has {len(thread)} message(s) after trimming to {HISTORY_BUDGET} chars")
    # Size the book grab to the comment we're answering, but never trivially small.
    latest_len = len(thread[-1]["body"]) if thread else 0
    book = fetch_book_passage(rng, min(BOOK_BUDGET, max(800, latest_len * 5)))

    log(f"thread:\n{pformat(thread)}\n\ninspo:\n{book}")
    comment = run_chain(thread, book)
    comment = comment.strip()
    if not comment:
        log("the muse fell silent; nothing to post")
        return 2
    log(f"reply: {len(comment)} chars of commentg")

    REPLY_PATH.write_text(
        f"{comment}\n\n",
        encoding="utf-8",
    )
    log(f"wrote reply ({len(comment)} chars) to {REPLY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
