"""Onboarding orchestration: turn loop, selections, and confirm gating.

Moved out of api/onboarding.py. Holds the business order of a confirm (gate,
then persist) and the state-shaped response builder. The LLM turn loop runs in
app/onboarding/agent.py. O-12 keeps fixed values on a deterministic server path
so extraction cannot desynchronise a beat.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.features.knowledge import service as knowledge_service
from app.features.onboarding import service
from app.features.tenants.slug import suggested_slug, validate_slug
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.onboarding import beats
from app.onboarding.agent import (
    OnboardingRecord,
    prepare_turn,
    prepare_url_turn,
    progress,
    run_turn,
    selection_reply,
    stream_reply,
)
from app.onboarding.flow import ProfileDraft
from app.onboarding.tools import request_finalize
from app.shared.limits import DEFAULT_LLM_TIMEOUT_S, TimeLimitedProvider

logger = logging.getLogger("app.onboarding.controller")

# O-7: three shapes of link, in the order an owner is likely to paste one. A
# bare host only counts when a path follows it or it starts with "www.", and
# its last label must be alphabetic - that is what keeps "$16.50 a plate" and
# "16.50/plate" out while letting "ubereats.com/store/x" in. Before O-7 only
# the first branch matched, so a pasted bare domain was never even attempted.
_URL_RE = re.compile(
    r"""
    (?:
        https?://[^\s"'<>]+                                  # an explicit URL
      | www\.[^\s"'<>]+                                      # a www host, scheme omitted
      | (?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}       # host, alphabetic TLD
        /[^\s"'<>]*                                          # ... only with a path
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# O-3: knowledge is never a blocking beat. A page we cannot read offers the two
# other ways in and then lets the interview move on - the owner can fill this in
# whenever, from the Knowledge screen.
#
# O-7: the line now names the situation instead of implying the owner mistyped
# something. Marketplace and social pages (Uber Eats, Instagram, Facebook) build
# themselves in the browser and turn readers away at the door, so the honest
# answer is that this page cannot be read, not that the link was wrong.
_URL_SCRAPE_FAILED = (
    "I couldn't read that page - some sites don't let anything but a browser in. "
    "Tell me in a sentence what you do, or send me a file instead. Either way you "
    "can add your services, pricing and the rest any time from Settings > Knowledge."
)


def _find_url(text: str) -> str | None:
    """The first link in the message, trailing punctuation stripped, or None.

    A match without a scheme is returned with ``https://`` prepended, because
    that is what the owner meant and what ``fetch_page`` will accept.
    """
    match = _URL_RE.search(text)
    if match is None:
        return None
    url = match.group(0).rstrip(".,;:!?)")
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def _state_event(record: OnboardingRecord) -> dict[str, object]:
    record_data = record.to_jsonb()
    stage, input_, can_confirm = progress(record)
    return {
        "type": "state",
        "stage": stage,
        "draft": record_data.get("draft", {}),
        "completed": record_data.get("completed", False),
        "input": input_.model_dump() if input_ else None,
        "can_confirm": can_confirm,
        "suggested_slug": suggested_slug(
            str(record_data.get("draft", {}).get("business_name", ""))
        ),
    }


async def _scrape_and_ingest(*, tenant_id: UUID, url: str, embedder: Embedder) -> tuple[str, str]:
    """Scrape a URL and ingest it as a 'website' document (O-3). Returns
    ``(page_text, title)``; a scrape failure raises ``ValueError``."""
    document_id = uuid4()
    page_text, title = await knowledge_service.scrape_url(url=url)
    await knowledge_service.ingest_website(
        tenant_id=tenant_id,
        document_id=document_id,
        url=url,
        text=page_text,
        title=title,
        embedder=embedder,
    )
    return page_text, title


def response_from_record(record_data: dict[str, Any]) -> dict[str, Any]:
    onboarding = OnboardingRecord.from_jsonb(record_data)
    draft = onboarding.draft
    completed = onboarding.completed
    stage, input_, can_confirm = progress(onboarding)
    prompt = ""
    for msg in reversed(onboarding.history):
        if msg.get("role") == "assistant":
            prompt = msg.get("content", "")
            break
    if not prompt:
        prompt = (
            "Hi! I'm your Agencx setup assistant. I'll help you get your business "
            "ready. What's your name?"
        )
    return {
        "stage": stage,
        "prompt": prompt,
        "draft": draft,
        "completed": completed,
        "history": onboarding.history,
        "input": input_.model_dump() if input_ else None,
        "can_confirm": can_confirm,
        "suggested_slug": suggested_slug(str(draft.get("business_name", ""))) or None,
    }


async def load_record_state(*, tenant_id: UUID) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    return response_from_record(record)


async def run_message(
    *, tenant_id: UUID, text: str, provider: LLMProvider, embedder: Embedder
) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    url = _find_url(text)
    if url is not None:
        return await _run_url_message(
            tenant_id=tenant_id,
            url=url,
            onboarding=onboarding,
            provider=provider,
            embedder=embedder,
        )
    # ponytail: use the platform default timeout rather than resolving the
    # tenant's per-tenant llm_timeout_s; resolve TenantLimits like
    # features/chat/controller.py if onboarding ever needs per-tenant overrides.
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    updated, _reply, persist = await run_turn(
        admin_message=text, record=onboarding, provider=bounded
    )
    record_data = updated.to_jsonb()
    if persist:
        await service.save_record(tenant_id=tenant_id, record=record_data)
    return record_data


async def run_selection(*, tenant_id: UUID, beat_key: str, values: list[str]) -> dict[str, Any]:
    """Apply the current beat's fixed answer without an LLM call."""
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    current = beats.next_beat(onboarding.draft)
    if current is None or current.key != beat_key:
        stage = current.key if current is not None else "confirm"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"stale selection - current beat is {stage}",
        )
    try:
        user_message = beats.apply_selection(onboarding.draft, beat_key, values)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    reply = selection_reply(onboarding)
    onboarding.history.append({"role": "user", "content": user_message})
    onboarding.history.append({"role": "assistant", "content": reply})
    record_data = onboarding.to_jsonb()
    await service.save_record(tenant_id=tenant_id, record=record_data)
    return record_data


async def _run_url_message(
    *,
    tenant_id: UUID,
    url: str,
    onboarding: OnboardingRecord,
    provider: LLMProvider,
    embedder: Embedder,
) -> dict[str, Any]:
    """Non-streamed URL turn: scrape + ingest, extract, return the read-back
    state. A failed scrape degrades to a calm ask-to-describe."""
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    try:
        page_text, _title = await _scrape_and_ingest(
            tenant_id=tenant_id, url=url, embedder=embedder
        )
    except ValueError as exc:
        # O-7: the owner gets one calm line either way, but the reason is not
        # thrown away. A 403, a page that renders itself in the browser, and a
        # dead host all read the same on screen and must not read the same here.
        logger.info("url scrape failed url=%s reason=%s", url, exc)
        onboarding.history.append({"role": "user", "content": url})
        onboarding.history.append({"role": "assistant", "content": _URL_SCRAPE_FAILED})
        await service.save_record(tenant_id=tenant_id, record=onboarding.to_jsonb())
        return onboarding.to_jsonb()

    plan = await prepare_url_turn(url=url, page_text=page_text, record=onboarding, provider=bounded)
    plan.record.history.append({"role": "assistant", "content": plan.summary or ""})
    await service.save_record(tenant_id=tenant_id, record=plan.record.to_jsonb())
    return plan.record.to_jsonb()


async def run_message_stream(
    *, tenant_id: UUID, text: str, provider: LLMProvider, embedder: Embedder
) -> AsyncIterator[dict[str, object]]:
    """Streams one text turn as SSE-shaped events.

    Event order: ``progress`` -> ``token``* -> [``redraft``] -> ``token``* ->
    ``reply`` -> ``state`` -> ``done``. Two short DB writes per turn: the draft
    plus the user message persist before the stream starts (so a refresh
    mid-conversation survives), the assistant reply persists after the stream.
    A URL in the message routes to the site-as-shortcut turn (O-3).
    """
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    url = _find_url(text)
    if url is not None:
        async for event in _stream_url_turn(
            tenant_id=tenant_id,
            url=url,
            onboarding=onboarding,
            provider=provider,
            embedder=embedder,
        ):
            yield event
        return
    # ponytail: platform default timeout (see run_message above).
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    plan = await prepare_turn(admin_message=text, record=onboarding, provider=bounded)
    if plan.persist:
        await service.save_record(tenant_id=tenant_id, record=plan.record.to_jsonb())

    yield {"type": "progress", "stage": "processing"}

    full = ""
    async for kind, payload in stream_reply(plan=plan, provider=bounded):
        if kind == "redraft":
            full = ""
            yield {"type": "redraft", "reason": payload}
        else:
            full += payload
            yield {"type": "token", "text": payload}
    # Kept for the old client; the new client reassembles ``token`` events.
    yield {"type": "reply", "text": full}

    if plan.persist:
        plan.record.history.append({"role": "assistant", "content": full})
        await service.save_record(tenant_id=tenant_id, record=plan.record.to_jsonb())

    yield _state_event(plan.record)
    yield {"type": "done"}


async def _stream_url_turn(
    *,
    tenant_id: UUID,
    url: str,
    onboarding: OnboardingRecord,
    provider: LLMProvider,
    embedder: Embedder,
) -> AsyncIterator[dict[str, object]]:
    """Streams the site-as-shortcut turn (O-3): scrape + ingest, then extract
    the profile fields from the page and reply with a read-back for the owner
    to confirm or correct. A failed scrape degrades to a calm ask-to-describe,
    never a hang or an error chrome."""
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    # The stamp leads: it is what the owner reads while the fetch, the ingest and
    # the extract run, so it has to be on the wire before any of them start.
    yield {"type": "progress", "stage": "reading_site"}
    try:
        page_text, _title = await _scrape_and_ingest(
            tenant_id=tenant_id, url=url, embedder=embedder
        )
    except ValueError as exc:
        logger.info("url scrape failed url=%s reason=%s", url, exc)
        onboarding.history.append({"role": "user", "content": url})
        await service.save_record(tenant_id=tenant_id, record=onboarding.to_jsonb())
        yield {"type": "token", "text": _URL_SCRAPE_FAILED}
        yield {"type": "reply", "text": _URL_SCRAPE_FAILED}
        onboarding.history.append({"role": "assistant", "content": _URL_SCRAPE_FAILED})
        await service.save_record(tenant_id=tenant_id, record=onboarding.to_jsonb())
        yield _state_event(onboarding)
        yield {"type": "done"}
        return

    plan = await prepare_url_turn(url=url, page_text=page_text, record=onboarding, provider=bounded)
    await service.save_record(tenant_id=tenant_id, record=plan.record.to_jsonb())

    full = ""
    async for kind, payload in stream_reply(plan=plan, provider=bounded):
        if kind == "redraft":
            full = ""
            yield {"type": "redraft", "reason": payload}
        else:
            full += payload
            yield {"type": "token", "text": payload}
    yield {"type": "reply", "text": full}

    plan.record.history.append({"role": "assistant", "content": full})
    await service.save_record(tenant_id=tenant_id, record=plan.record.to_jsonb())

    yield _state_event(plan.record)
    yield {"type": "done"}


async def confirm(
    *, tenant_id: UUID, slug: str | None = None, embedder: Embedder | None = None
) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already confirmed",
        )
    draft = onboarding.draft
    gate = request_finalize(draft)
    if not gate.ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"incomplete - missing: {'; '.join(gate.missing)}",
        )
    # The gate above guarantees all seven fields; extra keys (a pre-O-1 draft's
    # orphan sections) are ignored rather than rejected.
    profile = ProfileDraft.model_validate(draft)
    public_slug = validate_slug(slug or suggested_slug(profile.business_name))
    # business_type is the owner's own free text, so it gets its own sentence
    # rather than an apposition - "Bytefix Repairs, phone repair shop" and
    # "Northgate Family Dental, A three-chair practice..." both read badly.
    system_prompt = (
        f"You are the assistant for {profile.business_name}. "
        f"About the business: {profile.business_type.rstrip('.')}. "
        "Answer only from the business's own material; when the answer isn't "
        "there, say so and offer to have the owner follow up."
    )
    onboarding.completed = True
    try:
        await service.apply_confirmation(
            tenant_id=tenant_id,
            system_prompt=system_prompt,
            business_name=profile.business_name,
            slug=public_slug,
            profile=profile.model_dump(),
            completed_record=onboarding.to_jsonb(),
            offering_candidates=onboarding.offering_candidates,
            embedder=embedder,
        )
    except service.PublicSlugTakenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That page address is already taken. Choose another.",
        ) from exc
    return {"tenant_id": tenant_id, "slug": public_slug}
