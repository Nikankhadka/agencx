"""O-1: lean onboarding turn-loop unit tests.

Tests the agent turn loop (structured extraction + one ``save_profile`` merge),
the completeness gate over the seven lean beats, off-topic handling, the price
echo check, and record migration to v3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.llm.provider import ChatMessage, SchemaT
from app.onboarding import beats
from app.onboarding.agent import (
    Directive,
    OnboardingRecord,
    _echo,
    prepare_turn,
    prepare_url_turn,
    run_turn,
    stream_reply,
)
from app.onboarding.flow import ProfileDraft
from app.onboarding.tools import request_finalize, save_profile
from tests.fakes import BaseFakeProvider

# --- fake providers ------------------------------------------------------------


class _ExtractFake(BaseFakeProvider):
    """Returns a sequence of DraftUpdate dicts, then a text-only chat reply.

    Records the extract() inputs and chat() messages so tests can assert what
    the agent loop feeds back to the model (stateful extraction context and the
    composed directive).
    """

    def __init__(
        self,
        updates: list[dict[str, Any]] | None = None,
        replies: list[str] | None = None,
    ):
        self._updates = list(updates or [])
        self._replies = replies or ["Got it."]
        self._update_idx = 0
        self._reply_idx = 0
        self.extract_inputs: list[str] = []
        self.chat_messages: list[list[ChatMessage]] = []
        self.stream_calls: list[list[ChatMessage]] = []

    async def extract(
        self, *, system_prompt: str, user_input: str, schema: type[SchemaT]
    ) -> SchemaT:
        self.extract_inputs.append(user_input)
        if self._update_idx < len(self._updates):
            data = self._updates[self._update_idx]
            self._update_idx += 1
            return schema.model_validate(data)
        return schema.model_validate({})

    async def chat(self, messages: list[ChatMessage]) -> str:
        self.chat_messages.append(messages)
        r = self._replies[self._reply_idx % len(self._replies)]
        self._reply_idx += 1
        return r

    async def chat_stream(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        self.stream_calls.append(messages)
        r = self._replies[self._reply_idx % len(self._replies)]
        self._reply_idx += 1
        mid = max(1, len(r) // 2)
        yield r[:mid]
        yield r[mid:]


# --- tool execution ------------------------------------------------------------


def test_save_profile_merges_only_non_empty_fields() -> None:
    draft: dict[str, Any] = {"name": "Sam", "business_name": "Bytefix Repairs"}
    result = save_profile(draft, ProfileDraft(business_type="phone repair shop"))

    assert result["business_type"] == "phone repair shop"
    # An empty field must not blank out what an earlier turn captured.
    assert result["name"] == "Sam"
    assert result["business_name"] == "Bytefix Repairs"


def test_save_profile_accumulates_across_turns() -> None:
    """US-1: the loop saves a partial profile per turn and merges them."""
    draft: dict[str, Any] = {}
    save_profile(draft, ProfileDraft(name="Sam", business_name="Bytefix Repairs"))
    save_profile(draft, ProfileDraft(hours="Mon-Fri 9-6", contact="555-0100"))

    assert draft == {
        "name": "Sam",
        "business_name": "Bytefix Repairs",
        "hours": "Mon-Fri 9-6",
        "contact": "555-0100",
    }


def test_save_profile_overwrites_a_corrected_field() -> None:
    draft: dict[str, Any] = {"business_name": "Bytefix"}
    save_profile(draft, ProfileDraft(business_name="Bytefix Repairs"))

    assert draft["business_name"] == "Bytefix Repairs"


# --- completeness gate ---------------------------------------------------------


def _complete_draft() -> dict[str, Any]:
    return {
        "name": "Sam",
        "business_name": "Bytefix Repairs",
        "business_type": "phone repair shop",
        "headcount": "just me",
        "hours": "Mon-Fri 9-6",
        "services": "screen repairs, battery replacements",
        "contact": "555-0100",
        "abn": "51 824 753 556",
        "gst": "yes",
    }


def test_gst_is_not_asked_of_a_business_without_an_abn() -> None:
    """O-6: the prototype's `handleAbn()` "no" branch goes straight past GST -
    a registration you cannot hold is not a question. Expressed in the beat's
    own predicate, so the gate and the interview cannot disagree about it."""
    without = _complete_draft() | {"abn": beats.NO_ABN, "gst": ""}
    assert beats.next_beat(without) is None
    assert request_finalize(without).ok

    # ...but a business that gave an ABN is still asked.
    with_abn = _complete_draft() | {"abn": "51 824 753 556", "gst": ""}
    nxt = beats.next_beat(with_abn)
    assert nxt is not None and nxt.key == "gst"
    assert "GST registration" in request_finalize(with_abn).missing


def test_no_beat_branches_on_the_business_type() -> None:
    """I8: the question set is the same for every vertical. ABN and GST are
    conditional on a previous *answer*, never on what the business does."""
    asked = []
    for business_type in ("dental clinic", "butcher", "online store"):
        draft = {"business_type": business_type}
        keys = []
        while (nxt := beats.next_beat(draft)) is not None:
            keys.append(nxt.key)
            draft[nxt.key] = "x"
        asked.append(keys)
    assert asked[0] == asked[1] == asked[2]


def test_completeness_gate_passes_when_every_field_present() -> None:
    result = request_finalize(_complete_draft())
    assert result.ok
    assert result.missing == []


def test_completeness_gate_fails_when_fields_missing() -> None:
    result = request_finalize({"name": "Sam"})
    assert not result.ok
    assert any("business name" in m for m in result.missing)
    assert any("contact details" in m for m in result.missing)


@pytest.mark.parametrize(
    ("field", "label"),
    [
        ("name", "your name"),
        ("business_name", "business name"),
        ("business_type", "business type"),
        ("headcount", "team size"),
        ("hours", "opening hours"),
        ("services", "what you offer"),
        ("contact", "contact details"),
    ],
)
def test_completeness_gate_enumerates_each_missing_field(field: str, label: str) -> None:
    """US-2: every lean field is required, and the gate names the one missing."""
    draft = _complete_draft()
    del draft[field]

    result = request_finalize(draft)

    assert not result.ok
    assert result.missing == [label]


def test_completeness_gate_is_the_same_for_every_business_type() -> None:
    """I8: the question set never branches on the vertical."""
    clinic = _complete_draft() | {"business_type": "dental clinic"}
    store = _complete_draft() | {"business_type": "online store"}
    del clinic["hours"]
    del store["hours"]

    assert request_finalize(clinic).missing == request_finalize(store).missing


# --- price echo check ----------------------------------------------------------


def test_reply_with_any_price_is_flagged() -> None:
    """The lean profile captures no prices, so any figure is model-authored (I1)."""
    assert _echo("Screen repair costs $89.50.", _complete_draft())
    assert _echo("It's $30.", _complete_draft())


def test_reply_with_no_prices_is_not_flagged() -> None:
    assert not _echo("We offer screen repair.", _complete_draft())


# --- record migration ----------------------------------------------------------


def test_from_jsonb_drops_a_pre_o1_nested_draft() -> None:
    """A v2 draft shares no key with the lean profile, so the interview restarts."""
    v2 = {"version": 2, "draft": {"identity": {"description": "old shop"}}, "completed": False}
    record = OnboardingRecord.from_jsonb(v2)

    assert record.version == 3
    assert record.draft == {}
    assert not record.completed


def test_from_jsonb_keeps_a_completed_legacy_tenant_live() -> None:
    """A tenant that already went live must never be re-interviewed."""
    v2 = {"version": 2, "draft": {"identity": {"description": "old shop"}}, "completed": True}
    record = OnboardingRecord.from_jsonb(v2)

    assert record.completed
    assert record.draft == {}


def test_from_jsonb_migrates_the_oldest_format() -> None:
    legacy = {"state": {"draft": {"identity": {"description": "old shop"}}}, "completed": False}
    record = OnboardingRecord.from_jsonb(legacy)

    assert record.version == 3
    assert record.draft == {}


def test_from_jsonb_reads_v3_format() -> None:
    v3 = {"version": 3, "draft": {"business_name": "Bytefix Repairs"}, "completed": True}
    record = OnboardingRecord.from_jsonb(v3)

    assert record.draft["business_name"] == "Bytefix Repairs"
    assert record.completed


def test_to_jsonb_roundtrips() -> None:
    record = OnboardingRecord(draft={"business_name": "Bytefix Repairs"}, completed=False)
    restored = OnboardingRecord.from_jsonb(record.to_jsonb())

    assert restored.draft == record.draft
    assert restored.completed == record.completed


def test_resume_replays_persisted_history() -> None:
    """US-4: a returning owner picks up from the persisted thread, nothing re-asked."""
    record = OnboardingRecord(
        draft={"name": "Sam", "business_name": "Bytefix Repairs"},
        history=[
            {"role": "user", "content": "I'm Sam, we're Bytefix Repairs"},
            {"role": "assistant", "content": "Got it. What kind of business is it?"},
        ],
    )
    restored = OnboardingRecord.from_jsonb(record.to_jsonb())

    assert restored.history == record.history
    assert restored.draft["business_name"] == "Bytefix Repairs"


# --- agent turn loop -----------------------------------------------------------


@pytest.mark.asyncio
async def test_run_turn_extracts_from_a_complex_message() -> None:
    """A free-form answer must be captured on the first try, not dropped
    because the model replied in prose."""
    provider = _ExtractFake(
        updates=[
            {
                "profile": {
                    "business_type": "mobile phone business",
                    "services": "phone cases and accessories",
                }
            },
        ],
        replies=["Got it - a mobile phone business! What are your opening hours?"],
    )
    record = OnboardingRecord()
    updated, reply, persist = await run_turn(
        admin_message=(
            "this is a mobile phone business mostly selling phone cases and everything else"
        ),
        record=record,
        provider=provider,
    )

    assert updated.draft["business_type"] == "mobile phone business"
    assert updated.draft["services"] == "phone cases and accessories"
    assert "mobile phone" in reply
    assert persist is True
    assert len(updated.history) >= 2


@pytest.mark.asyncio
async def test_run_turn_extracts_business_name() -> None:
    provider = _ExtractFake(
        updates=[{"profile": {"business_name": "Bytefix Repairs"}}],
        replies=["Got it - Bytefix Repairs!"],
    )
    record = OnboardingRecord()
    updated, reply, persist = await run_turn(
        admin_message="we are called Bytefix Repairs", record=record, provider=provider
    )

    assert updated.draft["business_name"] == "Bytefix Repairs"
    assert "Bytefix Repairs" in reply
    assert persist is True


@pytest.mark.asyncio
async def test_run_turn_acknowledges_every_field_it_captured() -> None:
    provider = _ExtractFake(
        updates=[{"profile": {"hours": "Mon-Fri 9-6", "contact": "555-0100"}}],
        replies=["Noted."],
    )
    record = OnboardingRecord(draft={"name": "Sam"})
    _updated, _reply, _persist = await run_turn(
        admin_message="we're open Mon-Fri 9-6, call 555-0100", record=record, provider=provider
    )

    system_prompts = [m["content"] for m in provider.chat_messages[0] if m["role"] == "system"]
    assert any("opening hours" in p and "contact details" in p for p in system_prompts)


@pytest.mark.asyncio
async def test_run_turn_uses_next_question() -> None:
    provider = _ExtractFake(
        updates=[{"next_question": "What do you sell or offer?"}],
        replies=["What do you sell or offer?"],
    )
    record = OnboardingRecord(draft={"name": "Sam"})
    _updated, reply, _persist = await run_turn(
        admin_message="ok go on", record=record, provider=provider
    )

    assert reply == "What do you sell or offer?"
    system_prompts = [m["content"] for m in provider.chat_messages[0] if m["role"] == "system"]
    assert any("What do you sell or offer?" in p for p in system_prompts)


@pytest.mark.asyncio
async def test_run_turn_extraction_is_stateful() -> None:
    """The extract call sees the already-captured draft so it can fill what is
    still missing instead of re-asking for what it has."""
    provider = _ExtractFake(updates=[{"profile": {"headcount": "just me"}}], replies=["Noted."])
    record = OnboardingRecord(draft={"business_name": "Bytefix Repairs"})
    _updated, _reply, _persist = await run_turn(
        admin_message="it's just me", record=record, provider=provider
    )

    assert "Bytefix Repairs" in provider.extract_inputs[0]


@pytest.mark.asyncio
async def test_run_turn_handles_completed_record() -> None:
    provider = _ExtractFake(updates=[], replies=[])
    record = OnboardingRecord(completed=True)
    updated, reply, persist = await run_turn(
        admin_message="anything", record=record, provider=provider
    )
    assert "already complete" in reply
    assert updated.completed
    assert persist is False


@pytest.mark.asyncio
async def test_run_turn_off_topic_answers_gently() -> None:
    """US-3: one-line answer plus a redirect, and no firmness escalation."""
    provider = _ExtractFake(
        updates=[
            {
                "off_topic": True,
                "meta_reply": "I'm here to help you set up your business.",
                "next_question": "What is your business called?",
            },
        ],
        replies=["I'm here to help you set up your business. What is your business called?"],
    )
    record = OnboardingRecord(draft={"name": "Sam"})
    updated, reply, persist = await run_turn(
        admin_message="who are you", record=record, provider=provider
    )

    assert persist is False
    assert updated.off_topic_count == 0
    assert updated.history == []
    assert "set up your business" in reply
    system_prompts = [m["content"] for m in provider.chat_messages[0] if m["role"] == "system"]
    assert any("Briefly answer" in p for p in system_prompts)


@pytest.mark.asyncio
async def test_run_turn_off_topic_keeps_prior_history() -> None:
    """A no-op off-topic turn must not append to or drop existing history."""
    provider = _ExtractFake(
        updates=[
            {
                "off_topic": True,
                "meta_reply": "I'm here to help.",
                "next_question": "What is your business called?",
            }
        ],
        replies=["I'm here to help. What is your business called?"],
    )
    record = OnboardingRecord(
        draft={"name": "Sam"},
        history=[
            {"role": "user", "content": "I'm Sam"},
            {"role": "assistant", "content": "Got it."},
        ],
    )
    updated, _reply, persist = await run_turn(admin_message="hi", record=record, provider=provider)

    assert persist is False
    assert len(updated.history) == 2
    assert updated.draft["name"] == "Sam"


@pytest.mark.asyncio
async def test_run_turn_price_echo_triggers_redraft() -> None:
    """When the model authors a price, the reply is redrafted without it."""
    provider = _ExtractFake(
        updates=[{"profile": {"business_type": "phone repair shop"}}],
        replies=[
            "Screen repair is $199.",  # model-authored price - triggers redraft
            "Got it, I've captured what you do.",
        ],
    )
    record = OnboardingRecord()
    updated, reply, _persist = await run_turn(
        admin_message="we fix phones", record=record, provider=provider
    )

    assert updated.draft["business_type"] == "phone repair shop"
    assert "captured" in reply.lower()
    assert "$199" not in reply


# --- streaming split (prepare_turn / stream_reply) -----------------------------


@pytest.mark.asyncio
async def test_prepare_turn_sets_summary_once_the_profile_is_complete() -> None:
    provider = _ExtractFake(updates=[{"profile": {"contact": "555-0100"}}], replies=[])
    draft = _complete_draft()
    del draft["contact"]
    record = OnboardingRecord(draft=draft)

    plan = await prepare_turn(admin_message="call us on 555-0100", record=record, provider=provider)

    assert plan.persist is True
    assert plan.summary is not None
    assert "Bytefix Repairs" in plan.summary
    assert "ready to go live" in plan.summary
    assert plan.reply_msgs is None
    # The user message is already on the record; the assistant reply is not.
    assert plan.record.history[-1]["role"] == "user"


@pytest.mark.asyncio
async def test_stream_reply_yields_summary_without_llm() -> None:
    provider = _ExtractFake(updates=[{"profile": {"contact": "555-0100"}}], replies=[])
    draft = _complete_draft()
    del draft["contact"]
    record = OnboardingRecord(draft=draft)
    plan = await prepare_turn(admin_message="call us on 555-0100", record=record, provider=provider)

    events = [event async for event in stream_reply(plan=plan, provider=provider)]

    assert plan.summary is not None
    assert events == [("token", plan.summary)]
    assert provider.stream_calls == []


@pytest.mark.asyncio
async def test_stream_reply_price_echo_redrafts() -> None:
    provider = _ExtractFake(
        updates=[{"profile": {"business_type": "phone repair shop"}}],
        replies=[
            "Screen repair is $199.",  # model-authored price - triggers redraft
            "Got it, I've captured what you do.",
        ],
    )
    record = OnboardingRecord()
    plan = await prepare_turn(admin_message="we fix phones", record=record, provider=provider)

    events = [event async for event in stream_reply(plan=plan, provider=provider)]
    kinds = [kind for kind, _ in events]
    assert "redraft" in kinds
    redraft_idx = kinds.index("redraft")
    assert events[redraft_idx] == ("redraft", "price_echo")

    before = "".join(payload for kind, payload in events[:redraft_idx] if kind == "token")
    assert "$199" in before
    after = "".join(payload for kind, payload in events[redraft_idx + 1 :] if kind == "token")
    assert "captured" in after
    assert len(provider.stream_calls) == 2


# --- URL turn (O-3 site-as-shortcut) -------------------------------------------


@pytest.mark.asyncio
async def test_prepare_url_turn_extracts_from_page_and_reads_back() -> None:
    provider = _ExtractFake(
        updates=[
            {
                "profile": {
                    "business_type": "phone repair shop",
                    "services": "screen repairs, battery replacements",
                    "hours": "Mon-Fri 9-6",
                }
            },
        ],
    )
    record = OnboardingRecord()
    plan = await prepare_url_turn(
        url="https://bytefix.example.com",
        page_text=(
            "Bytefix Repairs fixes phones. Screen repairs and battery "
            "replacements. Open weekdays 9 to 6."
        ),
        record=record,
        provider=provider,
    )

    assert plan.persist is True
    assert plan.summary is not None
    assert "Here's what I've got from your site" in plan.summary
    assert "phone repair shop" in plan.summary
    assert "screen repairs" in plan.summary
    assert "Mon-Fri 9-6" in plan.summary
    assert plan.reply_msgs is None
    assert record.draft["business_type"] == "phone repair shop"


@pytest.mark.asyncio
async def test_prepare_url_turn_records_url_not_page_text() -> None:
    provider = _ExtractFake(updates=[{"profile": {"services": "screen repairs"}}])
    record = OnboardingRecord()
    plan = await prepare_url_turn(
        url="https://bytefix.example.com",
        page_text="a very long page that should never land in history",
        record=record,
        provider=provider,
    )

    user_messages = [m["content"] for m in plan.record.history if m["role"] == "user"]
    assert user_messages == ["https://bytefix.example.com"]
    assert "a very long page" not in plan.record.to_jsonb().__repr__()


@pytest.mark.asyncio
async def test_prepare_url_turn_reads_back_nothing_when_page_has_no_fields() -> None:
    provider = _ExtractFake(updates=[{"profile": None}])
    record = OnboardingRecord()
    plan = await prepare_url_turn(
        url="https://empty.example.com",
        page_text="welcome to my site",
        record=record,
        provider=provider,
    )

    assert plan.summary is not None
    assert "couldn't pin down" in plan.summary


# --- directive shape -----------------------------------------------------------
def test_directive_as_prompt_with_acknowledged() -> None:
    d = Directive(acknowledged=["business name"], ask_for="opening hours")
    prompt = d.as_prompt()
    assert "business name" in prompt
    assert "opening hours" in prompt


def test_directive_meta_answer() -> None:
    d = Directive(meta_answer="I'm here to help.", ask_for="business name")
    prompt = d.as_prompt()
    assert "Briefly answer" in prompt
    assert "business name" in prompt


def test_directive_all_captured() -> None:
    d = Directive()
    assert "All info captured." in d.as_prompt()
