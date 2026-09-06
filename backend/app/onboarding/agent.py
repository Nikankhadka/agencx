"""T-042: agentic onboarding copilot turn loop.

Two model calls per turn: one structured ``extract()`` to pull anything the
owner stated into the draft, then ``chat()`` to compose a conversational reply
from a server-computed directive. Structured extraction (rather than tool
calls) keeps capture robust on free/edge models that answer in prose; the
server's completeness gate stays authoritative.

The model writes one warm conversational sentence; the server appends the
beat's ``ask`` verbatim (W-2), so the question the owner sees is always the one
the beat cursor chose, and ``_ack`` strips any question the model tacked on.
Every turn is persisted - skipping the write let a later turn reload an older
row and rewind the beat pointer.

W-7: the answer to the beat that was asked is judged usable by two judges that
can each veto - the extractor's ``answered_asked`` verdict and the beat's own
deterministic ``valid`` - and a junk answer is dropped back out and re-asked
rather than saved. A beat still unanswered after two asks hands off out loud
("I'll come back to this") instead of the deferral being silent.

W-9: a rejected beat's reply is the beat's own ``reject`` plus the beat's own
``ask`` - no model call at all, so the retry cannot pick the beat's ``example``
up and hand it back as a fact about this owner.

Guardrails: scan_input, price echo check, bounded history. Off-topic/meta
questions are answered in one line then gently redirected - no escalating
firmness, and they never burn one of a beat's two asks.
State: {version: 4, draft, history, off_topic_count, completed,
knowledge_pending, offering_candidates, skipped, deferred, ask_beat,
ask_count} in jsonb.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.agents.spotlight import scan_input
from app.features.business.offering_candidates import normalize_name
from app.llm.provider import ChatMessage, LLMProvider
from app.observability.logging import TRANSCRIPT_LOGGER_NAME
from app.onboarding import beats
from app.onboarding.flow import (
    DraftUpdate,
    PendingOffering,
    merge_offerings,
    normalize_pending_offerings,
)
from app.onboarding.tools import save_profile
from app.shared.text import plain_dashes

logger = logging.getLogger("app.onboarding.agent")
transcript = logging.getLogger(TRANSCRIPT_LOGGER_NAME)

_MAX_HIST = 20


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


@dataclass
class Directive:
    """What the reply model is asked to write - the conversational line only.

    W-2 took the question away from the model and appends the beat's own ``ask``
    verbatim, which is the guarantee that a filled slot can never be re-asked.
    W-7 keeps that guarantee but gives the model back the *conversational* work:
    it writes one warm sentence - an acknowledgment, a nudge, or a "no problem,
    later" - and the server still owns which question follows. ``_ack`` strips
    any question the model tacks on anyway, so the owner never sees two.

    W-9 takes the rejection back out of the model's hands: a beat that got an
    unusable answer is answered by ``beats.Beat.reject`` directly, so no
    directive here describes one.

    Exactly one of ``reask`` / ``handoff`` / ``meta_answer`` is set on a given
    turn; ``acknowledged`` may accompany any of them or stand alone.
    """

    acknowledged: list[str] = field(default_factory=list)
    meta_answer: str = ""
    reask: str = ""
    handoff: str = ""

    def as_prompt(self) -> str:
        """This turn's half of the brief: the goal, and what was captured.

        The standing rules live in ``_COPILOT`` and are not restated here, so
        the two halves cannot drift into contradicting each other.
        """
        parts: list[str] = ["# THIS TURN"]
        if self.handoff:
            parts.append(f"- {self.handoff}")
        if self.acknowledged:
            parts.append(f"- Just captured: {', '.join(self.acknowledged)}.")
        if self.meta_answer:
            parts.append(f"- Briefly answer: {self.meta_answer}")
        if self.reask:
            parts.append(f"- {self.reask}")
        parts.append("")
        parts.append("# OUTPUT")
        parts.append(
            "One short sentence covering the above and nothing else. Do not ask "
            "a question - the server appends the question after your words."
        )
        return "\n".join(parts)


# W-9: the standing contract for the onboarding copilot, in explicit sections.
# Every prohibition here is one the live reproduction actually caught the model
# doing (praise, "no worries", "my name" for the owner's name, a beat example
# read back as a fact, em dashes) - none of it is defensive boilerplate.
_COPILOT = """\
# ROLE
You are the Agencx setup assistant, helping a small-business owner set up their
own assistant. You are talking to the owner, never to their customers.

# GOAL
Acknowledge what the owner just told you, in one short sentence, so the
interview reads like a conversation.

# SUCCESS CRITERIA
- Your sentence uses the owner's own wording where it can.
- Any value you repeat back is spelled exactly as the owner gave it.
- The owner is never told what is still missing.

# CONSTRAINTS
- The server writes every question. You never choose, write, paraphrase, or hint
  at one.
- Never list what is still missing and never say what comes next.
- No praise, no compliments, no enthusiasm about the owner, their answers, or
  their business. "Great", "love", "perfect", "awesome", "exciting", and
  "no worries" are all out.
- Never write "my name". The name under discussion is the owner's, so it is
  "your name".
- Never state a price or any other monetary amount, and never round one or work
  one out.
- Never name a trade, industry, or business type the owner has not named.
- Never claim to be a person.

# CONVERSATION RULES
- One sentence. Plain text. No headings, no bold, no lists.
- Repeat a captured value character for character.
- Use a plain dash "-" where you need a dash. Never use an em dash.
- Do not manufacture an acknowledgement when there is nothing to acknowledge - a
  brief neutral sentence is enough.

# OUTPUT
One short sentence and nothing else.

# STOP RULES
- Do not ask a question. The server appends the question after your words."""

# C-3: a figure the extractor rounds into the profile becomes a figure the
# customer-facing money gate will bless forever - the profile is one of its
# three allowed sources (C-1). So the copy-it-exactly rule belongs here too,
# not only on the customer side.
_EXTRACT_PROMPT = (
    "You are extracting business information from a small-business owner who is "
    "onboarding their assistant. Read the conversation and update the profile "
    "with anything new the owner stated: owner_display_name, business_name, business_type, "
    "headcount, hours, services, contact, abn, gst. Also list offering_names "
    "only when the owner explicitly names individual offerings. Fill only what the owner "
    "actually said - never invent a value. Copy any price or other amount "
    "exactly as the owner wrote it: never round it, convert it, tidy it up, or "
    "work one out. Two fields have a fixed vocabulary: set abn to the digits "
    'the owner gave, or to "none" if they said they do not have one yet; set '
    'gst to "yes" or "no". Never infer or invent offering names, and never add prices '
    "or descriptions to offering_names. Split a run-on list into one entry per item "
    'even when it has no commas: a message of the form "we offer A B and C" is '
    'offering_names ["A", "B", "C"], not a single entry. '
    "If the message is off-topic (a question about "
    "you, a greeting, or unrelated chat), set off_topic=true and put a one-line "
    "answer in meta_reply. Otherwise set off_topic=false. Leave the profile null "
    "when nothing new was stated. The server chooses the next question. "
    "When the conversation shows a question was asked this turn, set "
    "answered_asked to whether the owner's message is a genuine, plausible "
    "answer to that exact question: false for gibberish, a refusal, or a value "
    "that could not really be that field (a random number where a name belongs, "
    '"asdfgh" as a business type). Set it null when no question was asked.'
)


# W-9: v3 called the owner's-name beat ``name``; v4 calls it
# ``owner_display_name`` so it can never stand in for the business's name.
_V3_BEAT, _V4_BEAT = "name", "owner_display_name"


@dataclass
class OnboardingRecord:
    version: int = 4
    draft: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, str]] = field(default_factory=list)
    off_topic_count: int = 0
    completed: bool = False
    # O-3 follow-up: the optional website/documents ask is pending until the
    # owner answers it (paste a link, attach a file, or say "skip"). It never
    # gates go-live - confirm still requires only the seven profile fields.
    knowledge_pending: bool = False
    offering_candidates: list[PendingOffering] = field(default_factory=list)
    # W-2's two-pass cursor and ask counter. ``skipped`` beats are gone for
    # good; ``deferred`` ones are required beats held back to pass two.
    # ``ask_beat``/``ask_count`` track only the beat being asked right now,
    # since that is the only one whose repeat count matters.
    skipped: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    ask_beat: str = ""
    ask_count: int = 0
    # W-7: a required field that remains unusable after both passes pauses the
    # interview. It stays unset and the owner explicitly resumes it later.
    paused_beat: str | None = None

    @classmethod
    def from_jsonb(cls, raw: dict[str, Any]) -> OnboardingRecord:
        """Load a record, migrating anything older than v3 to the lean profile.

        v3 and v4 are both O-1's flat profile; the only difference is the name
        of one beat, so a v3 record is carried forward whole and renamed rather
        than reset. A v1/v2 draft holds the retired nested sections
        (business/identity/tone/services/...), which share no key with the lean
        fields, so it is dropped rather than carried as orphan data - an
        in-flight interview restarts. ``completed`` survives, so a tenant that
        already went live is never re-interviewed.
        """
        version = raw.get("version")
        if version in (3, 4):
            record = cls(
                version=4,
                draft=raw.get("draft", {}),
                history=raw.get("history", []),
                off_topic_count=raw.get("off_topic_count", 0),
                completed=raw.get("completed", False),
                knowledge_pending=raw.get("knowledge_pending", False),
                offering_candidates=_load_offerings(raw.get("offering_candidates", [])),
                # W-2's fields read through a default rather than forcing a
                # version bump: absence is indistinguishable from "fresh", and
                # bumping would restart every interview in flight at deploy.
                skipped=list(raw.get("skipped", [])),
                deferred=list(raw.get("deferred", [])),
                ask_beat=raw.get("ask_beat", ""),
                ask_count=raw.get("ask_count", 0),
                paused_beat=raw.get("paused_beat") or None,
            )
            if version == 3:
                record._rename_owner_name_beat()
            return record
        return cls(
            version=4,
            draft={},
            history=[],
            off_topic_count=0,
            completed=raw.get("completed", False),
            offering_candidates=[],
        )

    def _rename_owner_name_beat(self) -> None:
        """Carry a v3 record's owner-name beat onto its v4 key.

        Five places store a beat key, not one: the draft, the skip and deferral
        lists, the ask cursor, and the pause. Renaming only the draft would
        strand an interview whose cursor still pointed at ``name`` - the beat
        would be asked again with its answer already on file.
        """
        if _V3_BEAT in self.draft:
            self.draft[_V4_BEAT] = self.draft.pop(_V3_BEAT)
        self.skipped = [_V4_BEAT if key == _V3_BEAT else key for key in self.skipped]
        self.deferred = [_V4_BEAT if key == _V3_BEAT else key for key in self.deferred]
        if self.ask_beat == _V3_BEAT:
            self.ask_beat = _V4_BEAT
        if self.paused_beat == _V3_BEAT:
            self.paused_beat = _V4_BEAT

    def to_jsonb(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "draft": self.draft,
            "history": self.history[-_MAX_HIST:],
            "off_topic_count": self.off_topic_count,
            "completed": self.completed,
            "knowledge_pending": self.knowledge_pending,
            "offering_candidates": [item.model_dump() for item in self.offering_candidates],
            "skipped": self.skipped,
            "deferred": self.deferred,
            "ask_beat": self.ask_beat,
            "ask_count": self.ask_count,
            "paused_beat": self.paused_beat,
        }


def _load_offerings(raw: Any) -> list[PendingOffering]:
    offerings: list[PendingOffering] = []
    for offering in normalize_pending_offerings(raw):
        if normalize_name(offering.name) not in {
            normalize_name(existing.name) for existing in offerings
        }:
            offerings.append(offering)
    return offerings


def _merge_owner_offerings(record: OnboardingRecord, names: list[str]) -> None:
    documents = [item for item in record.offering_candidates if "document" in item.sources]
    owner: list[PendingOffering] = []
    seen: set[str] = set()
    for raw_name in names:
        name = raw_name.strip()
        key = normalize_name(name)
        if name and key not in seen:
            seen.add(key)
            owner.append(PendingOffering(name=name, sources=["owner"]))
    merged: dict[str, PendingOffering] = {}
    for item in owner + documents:
        key = normalize_name(item.name)
        existing = merged.get(key)
        # W-7: an owner-typed name and a document candidate for the same thing
        # combine into one row, with the document's price and description kept.
        merged[key] = (
            item.model_copy(deep=True) if existing is None else merge_offerings(existing, item)
        )
    record.offering_candidates = list(merged.values())


@dataclass
class TurnPlan:
    """Everything ``prepare_turn`` computed, ready for either the streamed or
    non-streamed reply path.

    ``summary`` is set when the reply is server-synthesized and never touches
    the model: the turn completed the profile, paused a required beat, or (W-9)
    rejected the answer to the beat that was asked.
    ``reply_msgs`` is set otherwise and is what the reply path feeds the LLM.
    ``question`` is the next beat's ``ask``, verbatim; the reply path appends
    it after the model's acknowledgment so the model never phrases it (W-2).
    ``off_topic`` mirrors the extraction verdict for logging.
    """

    record: OnboardingRecord
    summary: str | None
    reply_msgs: list[ChatMessage] | None
    question: str | None = None
    off_topic: bool = False


def _activation_summary(draft: dict[str, Any]) -> str:
    # W-9: the owner's own name used to stand in here when `business_name` was
    # missing, which is the one place the two names were conflated. It was
    # latent, never user-visible: this line renders only once every beat is
    # satisfied, and `business_name` is required, so the fallback could not be
    # reached from the interview. It is gone anyway - a missing business name is
    # a deferred required beat, never a silent substitution of a private name.
    name = draft.get("business_name")
    if name:
        intro = f"Your assistant for {name} is ready to go live."
    else:
        intro = "Your assistant is ready to go live."
    return f"{intro} Hit confirm to publish it."


# The optional website/documents ask (founder request): asked once when the
# profile completes, never a gate. Skipping is one word, and the same offer
# names the Settings > Knowledge fallback so knowledge can always wait.
_KNOWLEDGE_OFFER = (
    " Do you have a website or any documents - a menu, price list, or FAQs? "
    'You can paste a link, attach a file, or say "skip". Anything you save '
    "becomes a reference I can use when answering your customers, and you can "
    "add more any time from Settings."
)


# What a rejected beat says when it carries no ``reject`` of its own. Every beat
# with a deterministic ``valid`` check has one; a beat rejected purely on the
# extractor's verdict may not, and this keeps that reply server-owned too.
_GENERIC_REJECT = "I didn't quite catch that."


def _completion_reply(record: OnboardingRecord) -> str:
    """The server-synthesized reply once the seven fields are captured.

    First call fires the website/documents offer and opens the ``knowledge``
    stage; every later call is the activation summary, so the offer never
    repeats and "skip" (or a pasted link, cleared by ``prepare_url_turn``)
    advances the owner to confirm.
    """
    if not record.knowledge_pending:
        record.knowledge_pending = True
        return _activation_summary(record.draft) + _KNOWLEDGE_OFFER
    record.knowledge_pending = False
    return _activation_summary(record.draft)


def selection_reply(record: OnboardingRecord) -> str:
    """A deterministic acknowledgement followed by the authoritative next ask."""
    nxt = _advance(record)
    if nxt is None:
        record.ask_beat, record.ask_count = "", 0
        return _completion_reply(record)
    # The server emitted this question, so its cursor must agree before the
    # owner's next typed answer is extracted and validated.
    record.ask_beat, record.ask_count = nxt.key, 1
    return f"Got it. {nxt.ask}"


def progress(record: OnboardingRecord) -> tuple[str, beats.InputSpec | None, bool]:
    """The interview's (stage, composer widget, can-confirm) triple.

    The single source both ``_state_event`` and ``response_from_record`` read,
    so the SSE state and the REST state never disagree. A completed profile
    passes through the optional ``knowledge`` stage before ``confirm``.
    """
    if record.paused_beat:
        return "paused", None, False
    nxt = beats.next_beat(record.draft, record.skipped, record.deferred)
    if nxt is not None:
        return nxt.key, beats.input_spec(nxt), False
    if record.knowledge_pending:
        return "knowledge", beats.KNOWLEDGE_INPUT, False
    return "confirm", None, not record.completed


def _advance(record: OnboardingRecord) -> beats.Beat | None:
    """The beat to ask now, against this record's skipped and deferred keys.

    ``deferred`` is never cleared: once pass one runs out of beats,
    ``next_beat`` falls through to the deferred ones on its own, and keeping
    the list is what lets the caller tell a second ask from a final one.
    """
    return beats.next_beat(record.draft, record.skipped, record.deferred)


def _resolve(record: OnboardingRecord, beat: beats.Beat, admin_message: str) -> str:
    """Close a beat the owner has not answered in two asks, returning the line
    the assistant should say as it moves on (empty when there is nothing to say).

    A skippable beat takes its default or is dropped. A required beat is
    deferred on pass one. On pass two it pauses the interview with no fallback
    value, so an unusable answer cannot reach the public profile.

    W-7: the hand-off used to be silent, which read as the assistant losing its
    place when a deferred beat resurfaced later. It now says so.
    """
    record.ask_beat = ""
    record.ask_count = 0
    if beat.optional:
        if beat.default:
            record.draft[beat.key] = beat.default
        else:
            record.skipped.append(beat.key)
        return (
            f"Tell them warmly, in one short line, that {beat.label} can wait "
            "and you'll sort it out later."
        )
    if beat.key not in record.deferred:
        record.deferred.append(beat.key)
        return (
            "Tell them warmly, in one short line, that you'll come back "
            f"to their {beat.label} in a moment."
        )
    record.paused_beat = beat.key
    return f"I still need your {beat.label} before you can go live."


def resume_paused_beat(record: OnboardingRecord) -> str:
    """Re-open the paused required beat with a fresh two-ask allowance."""
    key = record.paused_beat
    beat = beats.BEATS.get(key or "")
    if beat is None or beat.optional or beat.complete(record.draft):
        raise ValueError("there is no required field waiting to be retried")
    record.paused_beat = None
    record.ask_beat, record.ask_count = beat.key, 1
    return f"Let's try that again. {beat.ask}"


# A sentence ends at . ! ? followed by whitespace or end of string.
_SENTENCE = re.compile(r"[^.!?]*[.!?]+|\S[^.!?]*$")


def _ack(text: str) -> str:
    """Keep the model's acknowledgment, drop any question it tacked on.

    The server appends the beat's own ``ask`` after this, so a model sentence
    ending in ``?`` would show the owner two questions. W-7 keeps the guarantee
    W-2 introduced - the question is always server-owned - by stripping the
    model's question here rather than trusting it not to write one. W-9 adds the
    em-dash normalization on the same seam, for the same reason: a prompt rule
    the model ignores is not a rule.
    """
    stripped = plain_dashes(text).strip()
    kept = [m.group(0).strip() for m in _SENTENCE.finditer(stripped)]
    kept = [sentence for sentence in kept if sentence and not sentence.rstrip().endswith("?")]
    return " ".join(kept).strip()


# One leading sentence: text up to and including its first run of terminators.
_LEAD_SENTENCE = re.compile(r"\s*[^.!?]*[.!?]+\s*")


def _flush_sentences(pending: str, *, final: bool) -> tuple[list[str], str]:
    """Pull whole sentences off the front of ``pending`` for live streaming.

    Returns the sentences ready to show (questions dropped - the server owns the
    question) and whatever tail is left unterminated. With ``final`` the tail is
    itself resolved: shown if it is a statement, dropped if it is a question.
    This is what lets W-7 stream the reply live and still guarantee the owner
    never sees the model's question next to the server's. Em dashes are
    normalized on the way out so the streamed and non-streamed paths speak the
    same copy rule (conventions.md 1). Normalizing a whole sentence rather than
    the pending buffer is what keeps a dash that straddles two deltas from
    becoming a double space.
    """
    out: list[str] = []
    while True:
        match = _LEAD_SENTENCE.match(pending)
        if match is None:
            break
        sentence = match.group(0)
        pending = pending[match.end() :]
        if not sentence.rstrip().endswith("?"):
            out.append(plain_dashes(sentence))
    if final and pending.strip():
        if not pending.rstrip().endswith("?"):
            out.append(plain_dashes(pending))
        pending = ""
    return out, pending


def _usable(beat: beats.Beat, value: str, *, answered_asked: bool | None) -> bool:
    """Whether the owner's reply is a genuine answer to ``beat`` (W-7).

    Both judges must agree: the extractor's ``answered_asked`` verdict catches
    word-shaped nonsense a regex waves through, and the beat's own ``valid``
    catches a value the model may have written into a field it does not fit.
    Either one saying no is a veto.
    """
    if answered_asked is False:
        return False
    if beat.valid is not None and not beat.valid(value):
        return False
    return True


def _extraction_input(
    record: OnboardingRecord, admin_message: str, asked: beats.Beat | None = None
) -> str:
    lines: list[str] = []
    if record.draft:
        lines.append("Current draft (already captured):")
        lines.append(json.dumps(record.draft))
    for entry in record.history[-_MAX_HIST:]:
        lines.append(f"{entry['role']}: {entry['content']}")
    # A hint, never a filter: it only helps disambiguate a reply that could be
    # an answer to several fields. The full schema stays available, so an
    # answer to some *other* question is still captured into its own field.
    if asked is not None:
        lines.append(f"The question asked this turn was: {asked.ask}")
    lines.append(f"user: {admin_message}")
    return "\n".join(lines)


# O-3 site-as-shortcut: a page is bounded to this window before it is handed to
# the extractor - the whole page (up to the 2MB fetch cap) would blow the
# extract call's budget, and a homepage states who the business is up front.
_URL_EXTRACT_CHARS = 4000

_URL_EXTRACT_PROMPT = (
    "You are extracting business information from a website a small-business "
    "owner just linked during onboarding. Read the page text and fill any of "
    "these fields the page states: business_name, business_type, services, "
    "hours. Fill only what the page actually says - never invent a value, and "
    "leave a field empty when the page does not mention it. Copy any price or "
    "other amount exactly as the page states it: never round it, convert it, or "
    "work one out. Set off_topic=false."
)

# O-3: the fields a homepage reliably states, read back to the owner for
# confirmation. name/headcount/contact stay conversationally asked (a page
# rarely states them cleanly).
_URL_READBACK_FIELDS = ("business_type", "services", "hours")


def _url_readback(draft: dict[str, Any]) -> str:
    parts = [
        f"{field.replace('_', ' ')}: {draft[field]}"
        for field in _URL_READBACK_FIELDS
        if draft.get(field)
    ]
    if parts:
        return (
            "Here's what I've got from your site: "
            + "; ".join(parts)
            + (". Sound right, or anything to fix?")
        )
    return (
        "I read your site but couldn't pin down the details - can you describe "
        "the business in a sentence?"
    )


async def prepare_url_turn(
    *, url: str, page_text: str, record: OnboardingRecord, provider: LLMProvider
) -> TurnPlan:
    """The site-as-shortcut half of a URL turn (O-3).

    Extracts profile fields from the scraped page text (bounded to a window),
    merges them into the draft, and returns a server-synthesized read-back so
    the owner can confirm or correct. The URL - never the full page text - is
    recorded as the user message.
    """
    if record.completed:
        return TurnPlan(
            record=record,
            summary="Onboarding is already complete.",
            reply_msgs=None,
        )
    scan_input(page_text)
    update = await provider.extract(
        system_prompt=_URL_EXTRACT_PROMPT,
        user_input=_extraction_input(record, page_text[:_URL_EXTRACT_CHARS]),
        schema=DraftUpdate,
    )
    if update.profile is not None:
        record.draft = save_profile(record.draft, update.profile)
    # A link pasted once the profile is complete is the owner's answer to the
    # website ask - it satisfies the offer the same way "skip" does.
    if beats.next_beat(record.draft, record.skipped, record.deferred) is None:
        record.knowledge_pending = False
    record.history.append({"role": "user", "content": url})
    return TurnPlan(
        record=record,
        summary=_url_readback(record.draft),
        reply_msgs=None,
    )


async def prepare_turn(
    *, admin_message: str, record: OnboardingRecord, provider: LLMProvider
) -> TurnPlan:
    """Runs the pre-reply half of a copilot turn.

    Extracts and merges the owner's message into the draft, composes the
    directive, decides ``persist``, and appends the user message to history (if
    persisting). Then it decides whether the reply is a server-synthesized
    summary (the go-live activation line, once every beat is satisfied) or a
    model-composed reply - without touching the LLM for the reply. Returns a
    :class:`TurnPlan` the reply path consumes.
    """
    logger.info(
        "onboarding turn start",
        extra={"step": "start", "msg_len": len(admin_message)},
    )
    transcript.info(f"[onboarding] admin: {admin_message}")
    if record.completed:
        return TurnPlan(
            record=record,
            summary="Onboarding is already complete.",
            reply_msgs=None,
        )
    scan_input(admin_message)

    # The opening question is rendered from the first open beat before any
    # cursor is persisted. Treat it as asked too, so its first answer receives
    # the same validation as every later one.
    asked = beats.BEATS.get(record.ask_beat) or _advance(record)
    opening_ask = (
        not record.ask_beat and not record.history and not record.draft and asked is not None
    )
    extract_started = time.perf_counter()
    update = await provider.extract(
        system_prompt=_EXTRACT_PROMPT,
        user_input=_extraction_input(record, admin_message, asked),
        schema=DraftUpdate,
    )
    logger.info(
        "onboarding step",
        extra={
            "step": "extract",
            "duration_ms": _ms(extract_started),
            "off_topic": update.off_topic,
        },
    )

    acknowledged: list[str] = []
    if update.profile is not None:
        record.draft = save_profile(record.draft, update.profile)
        for beat in beats.BEAT_ORDER:
            if getattr(update.profile, beat.key):
                acknowledged.append(beat.label)
    if update.offering_names is not None:
        _merge_owner_offerings(record, update.offering_names)
        # A named offering is an answer to the offer beat, so it fills that
        # field too rather than leaving the beat open and asking again.
        if not record.draft.get("services") and "services" not in record.skipped:
            record.draft["services"] = ", ".join(item.name for item in record.offering_candidates)

    # W-7: judge the answer to the beat that was actually asked. A value that is
    # not usable for that field is dropped back out so the beat stays open, and
    # the model is told to re-ask it - rather than the interview moving on with
    # "34234234" saved as a name.
    rejected: beats.Beat | None = None
    if asked is not None:
        value = str(record.draft.get(asked.key, "")).strip()
        if value and not _usable(asked, value, answered_asked=update.answered_asked):
            record.draft.pop(asked.key, None)
            if asked.label in acknowledged:
                acknowledged.remove(asked.label)
            rejected = asked
        elif (
            not value
            and update.off_topic
            and asked.valid is not None
            and not asked.valid(admin_message)
        ):
            # The model called it off-topic, but a message that cannot be this
            # beat's answer and did not fill anything is a failed answer, not
            # chit-chat ("34234234" for a name). Challenge it rather than
            # answering it as a stray question.
            rejected = asked
    # A rejection is a failed answer: it counts toward the ask cap and takes the
    # challenge path, not the off-topic meta path. A genuine off-topic turn (a
    # real question) still burns no ask.
    off_topic = update.off_topic and rejected is None
    on_topic = not off_topic

    nxt = _advance(record)
    # The counter tracks how many times this beat has been *asked*. An off-topic
    # turn is noise, not a failed answer, so it burns neither ask; a rejected
    # answer does count, so two junk replies in a row reach the hand-off.
    handoff = ""
    if nxt is not None and on_topic and nxt.key == record.ask_beat and record.ask_count >= 2:
        # Asked twice already - rather than ask a third time, close it out and
        # move on, saying so instead of the beat silently reappearing later.
        handoff = _resolve(record, nxt, admin_message)
        nxt = _advance(record)

    if record.paused_beat:
        record.ask_beat, record.ask_count = "", 0
    elif nxt is None:
        record.ask_beat, record.ask_count = "", 0
    elif nxt.key != record.ask_beat:
        record.ask_beat = nxt.key
        # The opening question was already visible before the first request.
        # A failed opening answer therefore sends the second ask, not the first.
        record.ask_count = (
            2 if opening_ask and on_topic and asked is not None and nxt.key == asked.key else 1
        )
    elif on_topic:
        record.ask_count += 1

    directive = Directive(acknowledged=acknowledged)
    # W-9: a rejected beat is answered entirely by the server. The old path
    # handed the model "say so kindly, e.g. {example}", and the model read the
    # example back as this owner's own answer ("No worries at all, Nikan!").
    # The beat's ``reject`` plus the beat's ``ask`` says the same thing with
    # nothing left to embellish, and takes a model round trip off the slowest
    # path in the interview.
    reject_reply = ""
    if handoff:
        directive.handoff = handoff
    elif off_topic:
        record.off_topic_count += 1
        directive.meta_answer = update.meta_reply or "I'm here to help you set up your business."
    elif rejected is not None and nxt is not None and nxt.key == rejected.key:
        reject_reply = f"{rejected.reject or _GENERIC_REJECT} {nxt.ask}"
    elif nxt is not None and nxt.key == record.ask_beat and record.ask_count >= 2:
        # Same beat, second ask, nothing captured - nudge with a concrete example.
        directive.reask = (
            f"They have not answered this yet. In one short line encourage them, "
            f"e.g. {nxt.example}."
        )

    state_parts = [
        f"captured={', '.join(sorted(record.draft)) or 'none'}",
        f"ask_for={nxt.key if nxt else 'all captured'}",
        f"ask_count={record.ask_count}",
    ]
    if rejected is not None:
        state_parts.append(f"rejected={rejected.key}")
    if reject_reply:
        state_parts.append("reply=deterministic")
    if record.skipped:
        state_parts.append(f"skipped={', '.join(record.skipped)}")
    if record.deferred:
        state_parts.append(f"deferred={', '.join(record.deferred)}")
    if directive.meta_answer:
        state_parts.append(f"meta={directive.meta_answer}")
    transcript.info("[onboarding] state: " + "; ".join(state_parts))

    # Every turn is persisted. Skipping the write when a turn collected nothing
    # used to let the next turn reload an older row and rewind the beat pointer
    # - the emitted state and the stored record have to agree (W-2).
    record.history.append({"role": "user", "content": admin_message})

    if record.paused_beat:
        return TurnPlan(
            record=record,
            summary=handoff,
            reply_msgs=None,
            off_topic=off_topic,
        )

    # The rejected-beat reply travels as a summary, the same seam the completion
    # line already uses: both reply paths render a summary with no model call.
    if reject_reply:
        return TurnPlan(
            record=record,
            summary=reject_reply,
            reply_msgs=None,
            off_topic=off_topic,
        )

    reply_msgs: list[ChatMessage] = [
        {"role": "system", "content": _COPILOT},
        {"role": "system", "content": directive.as_prompt()},
    ]
    # The owner's current message is already the last entry in history (appended
    # above), so this slice carries it. W-9 removed a second append here that
    # showed the model the same message twice, every turn, on both paths.
    for entry in record.history[-3:]:
        reply_msgs.append({"role": entry["role"], "content": entry["content"]})

    if nxt is None:
        return TurnPlan(
            record=record,
            summary=_completion_reply(record),
            reply_msgs=None,
            off_topic=off_topic,
        )
    return TurnPlan(
        record=record,
        summary=None,
        reply_msgs=reply_msgs,
        question=nxt.ask,
        off_topic=off_topic,
    )


async def stream_reply(*, plan: TurnPlan, provider: LLMProvider) -> AsyncIterator[tuple[str, str]]:
    """Streams the reply as ``(kind, payload)`` pairs.

    ``kind`` is ``"token"`` for a text delta, or ``"redraft"`` for a flag that
    the price-echo guard tripped and the client should drop what it has so far.
    A deterministic summary streams as a single token with no LLM call; a
    model reply streams deltas from ``chat_stream`` and, on echo, does one
    redraft pass over the original messages plus the flagged reply. The beat's
    question is appended verbatim as a final token once the model is done - and
    after any redraft - so the echo guard only ever inspects model output.
    """
    if plan.summary is not None:
        yield ("token", plan.summary)
        return

    assert plan.reply_msgs is not None
    stream_started = time.perf_counter()
    # W-7 streams the model's sentence live, the same way W-2 did - the smooth,
    # progressive reveal is what a returning founder remembers, and it adds no
    # latency over the version they liked. The server appends the beat's own
    # question as a final token; a one-sentence ack cannot be both streamed live
    # and have a trailing question stripped (its only sentence is the last one),
    # so the guarantee here is the tight _COPILOT/directive telling the model
    # never to ask, plus the question always being server-owned.
    full = ""
    pending = ""
    shown = ""
    async for delta in provider.chat_stream(plan.reply_msgs):
        full += delta
        pending += delta
        sentences, pending = _flush_sentences(pending, final=False)
        for sentence in sentences:
            shown += sentence
            yield ("token", sentence)
    logger.info(
        "onboarding step",
        extra={"step": "reply_compose", "duration_ms": _ms(stream_started), "chars": len(full)},
    )
    if _echo(full, plan.record.draft):
        redraft_started = time.perf_counter()
        plan.reply_msgs.append({"role": "assistant", "content": full})
        plan.reply_msgs.append({"role": "user", "content": "Redraft - drop invented figures."})
        yield ("redraft", "price_echo")
        full = ""
        pending = ""
        shown = ""
        async for delta in provider.chat_stream(plan.reply_msgs):
            full += delta
            pending += delta
            sentences, pending = _flush_sentences(pending, final=False)
            for sentence in sentences:
                shown += sentence
                yield ("token", sentence)
        logger.info(
            "onboarding step",
            extra={
                "step": "reply_redraft",
                "duration_ms": _ms(redraft_started),
                "chars": len(full),
            },
        )
    # Resolve the held tail: a trailing statement is shown, a trailing question
    # dropped - the server owns the question and appends it next.
    tail_sentences, _ = _flush_sentences(pending, final=True)
    for sentence in tail_sentences:
        shown += sentence
        yield ("token", sentence)
    if plan.question:
        lead = f" {plan.question}" if shown.strip() else plan.question
        shown += lead
        yield ("token", lead)
    transcript.info(f"[onboarding] assistant: {shown}")


async def run_turn(
    *, admin_message: str, record: OnboardingRecord, provider: LLMProvider
) -> tuple[OnboardingRecord, str]:
    """Runs one copilot turn (non-streamed). Returns ``(record, reply)``.

    The model writes the acknowledgment; the server appends the beat's question
    verbatim, so the question the owner sees is always the one the beat cursor
    actually chose.
    """
    turn_started = time.perf_counter()
    plan = await prepare_turn(admin_message=admin_message, record=record, provider=provider)

    if plan.summary is not None:
        reply = plan.summary
    else:
        assert plan.reply_msgs is not None
        reply_started = time.perf_counter()
        reply = await provider.chat(plan.reply_msgs)
        logger.info(
            "onboarding step",
            extra={
                "step": "reply_compose",
                "duration_ms": _ms(reply_started),
                "chars": len(reply),
            },
        )
        if _echo(reply, plan.record.draft):
            redraft_started = time.perf_counter()
            plan.reply_msgs.append({"role": "assistant", "content": reply})
            plan.reply_msgs.append({"role": "user", "content": "Redraft - drop invented figures."})
            reply = await provider.chat(plan.reply_msgs)
            logger.info(
                "onboarding step",
                extra={
                    "step": "reply_redraft",
                    "duration_ms": _ms(redraft_started),
                    "chars": len(reply),
                },
            )
        reply = _ack(reply)
        if plan.question:
            reply = f"{reply} {plan.question}".strip()

    plan.record.history.append({"role": "assistant", "content": reply})
    transcript.info(f"[onboarding] assistant: {reply}")
    logger.info(
        "onboarding turn done",
        extra={
            "step": "turn_done",
            "total_ms": _ms(turn_started),
            "off_topic": plan.off_topic,
            "reply_chars": len(reply),
        },
    )
    return plan.record, reply


def _echo(reply: str, draft: dict[str, Any]) -> bool:
    """The lean profile captures no prices, so any monetary figure the
    assistant produces is invented (I1 - the money guardrail). Trip on the
    first one so the reply is redrafted without it."""
    return bool(re.findall(r"\$\s*\d", reply))
