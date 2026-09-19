"""Onboarding orchestration: turn loop, selections, and confirm gating.

Moved out of api/onboarding.py. Holds the business order of a confirm (gate,
then persist) and the state-shaped response builder. The LLM turn loop runs in
app/onboarding/agent.py. O-12 keeps fixed values on a deterministic server path
so extraction cannot desynchronise a beat.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, status

from app.features.business.offering_candidates import normalize_name
from app.features.knowledge import service as knowledge_service
from app.features.onboarding import service
from app.features.tenants.slug import suggested_slug, validate_slug
from app.llm.embedder import Embedder
from app.llm.provider import LLMProvider
from app.onboarding import beats
from app.onboarding.agent import (
    OnboardingRecord,
    confirm_pending_name,
    decline_knowledge,
    is_affirmative,
    prepare_turn,
    prepare_url_turn,
    progress,
    propose_name_replacement,
    resume_paused_beat,
    run_turn,
    selection_reply,
    stream_reply,
)
from app.onboarding.flow import (
    FieldCorrection,
    PendingOffering,
    ProfileDraft,
    customer_voice_for,
    merge_offerings,
)
from app.onboarding.tools import request_finalize, save_profile
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


def _url_failure_code(exc: ValueError) -> str:
    """Map fetcher's deliberately safe diagnostics to stable log categories."""
    message = str(exc)
    if message.startswith("could not read this URL (HTTP"):
        return "upstream_http"
    for prefix, code in (
        ("URL resolves to a blocked", "blocked_address"),
        ("URL credentials", "credentials_rejected"),
        ("URL port", "port_rejected"),
        ("unsupported URL", "scheme_rejected"),
        ("redirect", "redirect_rejected"),
        ("too many redirects", "redirect_limit"),
        ("URL did not return HTML", "media_type_rejected"),
        ("page body exceeds", "body_limit"),
        ("network peer", "peer_mismatch"),
    ):
        if message.startswith(prefix):
            return code
    return "fetch_failed"


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
        # W-7: null until a business name exists, matching response_from_record.
        # suggested_slug("") is the reserved-name fallback "business-page", and
        # emitting it on early turns let the client lock it before the real name
        # was captured, so the go-live address showed "business-page" not the
        # business's own slug.
        "suggested_slug": suggested_slug(business_name)
        if (business_name := str(record_data.get("draft", {}).get("business_name", "")))
        else None,
        "offering_candidates": record_data.get("offering_candidates", []),
        "paused_beat": record.paused_beat,
        "pending_confirmation": record.pending_name,
        "skipped": record.skipped,
        "revision": record.revision,
    }


async def _scrape_and_draft(
    *, tenant_id: UUID, url: str, provider: LLMProvider
) -> tuple[str, str, dict[str, Any] | None]:
    """Fetch a URL once, then save the fetched source as an unread draft."""
    document_id = uuid4()
    page_text, title = await knowledge_service.scrape_url(url=url)
    record = await knowledge_service.draft_from_url_text(
        tenant_id=tenant_id,
        document_id=document_id,
        url=url,
        text=page_text,
        title=title,
        provider=provider,
    )
    return page_text, title, record


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
        # The opening ends with the first beat's own ask rather than a
        # paraphrase of it - same seam W-2 closes for every later question. W-9
        # fixes the wording; the composition is unchanged, so the question is
        # still written once, by the beat.
        prompt = (
            "Hi, I'm the Agencx setup assistant. I'll help set up your business. "
            f"{beats.BEAT_ORDER[0].ask}"
        )
    return {
        "stage": stage,
        "prompt": prompt,
        "draft": draft,
        "completed": completed,
        "history": onboarding.history,
        "input": input_.model_dump() if input_ else None,
        "can_confirm": can_confirm,
        # W-7: null until a business name exists. suggested_slug("") is the
        # reserved-name fallback "business-page" (truthy), so `or None` never
        # nulled it - the initial load then locked "business-page" into the
        # client's address field before the real name was ever captured.
        "suggested_slug": (
            suggested_slug(name) if (name := str(draft.get("business_name", ""))) else None
        ),
        "offering_candidates": onboarding.to_jsonb().get("offering_candidates", []),
        "paused_beat": onboarding.paused_beat,
        "pending_confirmation": onboarding.pending_name,
        "skipped": onboarding.skipped,
        "revision": onboarding.revision,
    }


def _fingerprint(kind: str, value: object) -> str:
    payload = json.dumps([kind, value], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _already_applied(record: OnboardingRecord, *, key: str | None, fingerprint: str) -> bool:
    return bool(
        (key and record.last_action_key == key)
        or (not key and record.last_action_fingerprint == fingerprint)
    )


def _mark_action(record: OnboardingRecord, *, key: str | None, fingerprint: str) -> None:
    record.last_action_key = key
    record.last_action_fingerprint = fingerprint


_CONFLICT_DETAIL = "Your setup moved on in another tab. Reload to pick it up there."


async def _checkpoint(tenant_id: UUID, record: OnboardingRecord) -> dict[str, Any]:
    """Persist one checkpoint and carry the new revision back onto the record.

    ``service.save_record`` compare-and-swaps on the stored revision and bumps
    it on the dict it writes. A turn that saves the same in-memory record twice
    (every streamed turn does) therefore has to carry that bump back, and doing
    it by hand at each call site meant one missed line was one 500. The read
    back from the written dict is the same value the row now holds.
    """
    record_data = record.to_jsonb()
    try:
        await service.save_record(tenant_id=tenant_id, record=record_data)
    except service.RevisionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_CONFLICT_DETAIL,
        ) from exc
    record.revision = int(record_data["revision"])
    return record_data


def _merge_document_candidates(record: OnboardingRecord, raw: Any) -> None:
    merged = {normalize_name(item.name): item for item in record.offering_candidates}
    for item in raw if isinstance(raw, list) else []:
        try:
            document = PendingOffering.model_validate(item)
        except (TypeError, ValueError):
            continue
        document = document.model_copy(update={"sources": ["document"]})
        key = normalize_name(document.name)
        existing = merged.get(key)
        # W-7: the document's price and description win an overlap.
        merged[key] = document if existing is None else merge_offerings(existing, document)
    record.offering_candidates = list(merged.values())


async def load_record_state(*, tenant_id: UUID) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    response = response_from_record(record)
    documents = await knowledge_service.list_records(tenant_id=tenant_id)
    if any(document["status"] == "draft" for document in documents):
        response["can_confirm"] = False
    return response


async def load_offering_suggestions(*, tenant_id: UUID) -> dict[str, Any]:
    """Return only private candidates still waiting for owner review."""
    record = OnboardingRecord.from_jsonb(await service.load_record(tenant_id=tenant_id))
    candidates = [item for item in record.offering_candidates if item.review_status == "pending"]
    return {"count": len(candidates), "candidates": candidates}


async def save_offering_suggestions(
    *, tenant_id: UUID, candidates: list[PendingOffering], embedder: Embedder
) -> dict[str, Any]:
    """Save review decisions and publish newly approved suggestions when live."""
    record = OnboardingRecord.from_jsonb(await service.load_record(tenant_id=tenant_id))
    existing = {item.candidate_id: item for item in record.offering_candidates}
    for candidate in candidates:
        if candidate.candidate_id not in existing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="suggestion is no longer available",
            )

    updated: list[PendingOffering] = []
    submitted = {candidate.candidate_id: candidate for candidate in candidates}
    for current in record.offering_candidates:
        replacement = submitted.get(current.candidate_id)
        if replacement is not None:
            updated.append(replacement)
        elif current.review_status == "pending":
            updated.append(current.model_copy(update={"review_status": "rejected"}))
        else:
            updated.append(current)
    record.offering_candidates = updated
    await _checkpoint(tenant_id, record)

    if record.completed:
        await service.publish_reviewed_offerings(
            tenant_id=tenant_id,
            offerings=[item for item in candidates if item.review_status == "approved"],
            embedder=embedder,
        )
    return await load_offering_suggestions(tenant_id=tenant_id)


async def run_message(
    *,
    tenant_id: UUID,
    text: str,
    provider: LLMProvider,
    embedder: Embedder,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    fingerprint = _fingerprint("text", text)
    if _already_applied(onboarding, key=idempotency_key, fingerprint=fingerprint):
        return onboarding.to_jsonb()
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    if onboarding.paused_beat:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="finish the paused field before sending another answer",
        )
    if onboarding.pending_name and is_affirmative(text):
        bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
        updated, _reply = await run_turn(admin_message=text, record=onboarding, provider=bounded)
        _mark_action(updated, key=idempotency_key, fingerprint=fingerprint)
        return await _checkpoint(tenant_id, updated)
    if onboarding.pending_name:
        bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
        _accepted, reply = await propose_name_replacement(
            record=onboarding, value=text, provider=bounded
        )
        onboarding.history.append({"role": "user", "content": text})
        onboarding.history.append({"role": "assistant", "content": reply})
        _mark_action(onboarding, key=idempotency_key, fingerprint=fingerprint)
        return await _checkpoint(tenant_id, onboarding)
    url = _find_url(text)
    if url is not None:
        return await _run_url_message(
            tenant_id=tenant_id,
            url=url,
            onboarding=onboarding,
            provider=provider,
            embedder=embedder,
            idempotency_key=idempotency_key,
            action_fingerprint=fingerprint,
        )
    # ponytail: use the platform default timeout rather than resolving the
    # tenant's per-tenant llm_timeout_s; resolve TenantLimits like
    # features/chat/controller.py if onboarding ever needs per-tenant overrides.
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    updated, _reply = await run_turn(admin_message=text, record=onboarding, provider=bounded)
    _mark_action(updated, key=idempotency_key, fingerprint=fingerprint)
    return await _checkpoint(tenant_id, updated)


async def run_selection(
    *,
    tenant_id: UUID,
    beat_key: str,
    values: list[str],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Apply the current beat's fixed answer without an LLM call."""
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    fingerprint = _fingerprint("selection", {"beat": beat_key, "values": values})
    if _already_applied(onboarding, key=idempotency_key, fingerprint=fingerprint):
        return onboarding.to_jsonb()
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    if onboarding.paused_beat:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="finish the paused field before selecting an answer",
        )
    # 20: the knowledge ask is not a beat - it sits past the last one, holding
    # `knowledge_pending` - so its Skip chip is answered before any beat cursor
    # is consulted. `decline_knowledge` is the same door the typed "skip" takes
    # through the extractor, minus the model call.
    if beat_key == "knowledge":
        if values != ["skip"] or not onboarding.knowledge_pending:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="there is no knowledge ask waiting to be answered",
            )
        reply = decline_knowledge(onboarding)
        onboarding.history.append({"role": "user", "content": "Skip for now"})
        onboarding.history.append({"role": "assistant", "content": reply})
        _mark_action(onboarding, key=idempotency_key, fingerprint=fingerprint)
        return await _checkpoint(tenant_id, onboarding)
    current = beats.next_beat(onboarding.draft, onboarding.skipped, onboarding.deferred)
    # A name waiting to be confirmed holds the interview on its own beat, which
    # is not always the one `next_beat` would ask next - a correction can leave
    # an earlier beat still open. `progress` emits the same key to the client.
    stage = (
        onboarding.pending_name["target"]
        if onboarding.pending_name
        else (current.key if current is not None else "confirm")
    )
    if stage != beat_key and beat_key in onboarding.draft and values == ["yes"]:
        return onboarding.to_jsonb()
    if stage != beat_key:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"stale selection - current beat is {stage}",
        )
    # W-9 US-1: while a name waits on the owner's yes, the beat's own chips are
    # replaced by the confirmation chip, so this is the one selection
    # `apply_selection` does not own - it cannot see the proposal, and the
    # import direction (beats knows nothing of the record) is deliberate.
    pending = onboarding.pending_name
    if pending is not None and beat_key == pending["target"]:
        if values != ["yes"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="select one valid answer"
            )
        user_message = "Yes"
        ack = f"Saved as {confirm_pending_name(onboarding)}."
    else:
        try:
            user_message = beats.apply_selection(onboarding.draft, beat_key, values)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        ack = "Got it."
    reply = selection_reply(onboarding, ack)
    onboarding.history.append({"role": "user", "content": user_message})
    onboarding.history.append({"role": "assistant", "content": reply})
    _mark_action(onboarding, key=idempotency_key, fingerprint=fingerprint)
    return await _checkpoint(tenant_id, onboarding)


async def run_correction(
    *,
    tenant_id: UUID,
    correction: FieldCorrection,
    provider: LLMProvider,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Apply a typed correction without re-running the onboarding extractor."""
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    fingerprint = _fingerprint("correction", correction.model_dump())
    if _already_applied(onboarding, key=idempotency_key, fingerprint=fingerprint):
        return onboarding.to_jsonb()
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="onboarding already confirmed"
        )
    target = correction.field
    value = correction.value.strip()
    if target == "unresolved_name":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="choose whether this is your name or the business name",
        )
    beat = beats.BEATS.get(target)
    if beat is None or target in {"customer_voice_preset", "customer_voice_custom_style"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="field cannot be corrected",
        )
    if beat.valid is not None and not beat.valid(value):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=beat.reject)

    if target in {"owner_display_name", "business_name"}:
        accepted, reply = await propose_name_replacement(
            record=onboarding,
            value=value,
            provider=TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S),
            target=target,
        )
        if not accepted:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=reply)
    else:
        onboarding.draft = save_profile(
            onboarding.draft, ProfileDraft.model_validate({target: value})
        )
        reply = f"Updated {beat.label}."

    onboarding.history.append({"role": "user", "content": correction.raw or correction.value})
    onboarding.history.append({"role": "assistant", "content": reply})
    _mark_action(onboarding, key=idempotency_key, fingerprint=fingerprint)
    return await _checkpoint(tenant_id, onboarding)


async def run_resume(*, tenant_id: UUID, idempotency_key: str | None = None) -> dict[str, Any]:
    """Resume a required field paused after both interview passes."""
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    fingerprint = _fingerprint("resume", True)
    if _already_applied(onboarding, key=idempotency_key, fingerprint=fingerprint):
        return onboarding.to_jsonb()
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="onboarding already confirmed"
        )
    try:
        reply = resume_paused_beat(onboarding)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    onboarding.history.append({"role": "assistant", "content": reply})
    _mark_action(onboarding, key=idempotency_key, fingerprint=fingerprint)
    return await _checkpoint(tenant_id, onboarding)


async def _run_url_message(
    *,
    tenant_id: UUID,
    url: str,
    onboarding: OnboardingRecord,
    provider: LLMProvider,
    embedder: Embedder,
    idempotency_key: str | None,
    action_fingerprint: str,
) -> dict[str, Any]:
    """Non-streamed URL turn: scrape + ingest, extract, return the read-back
    state. A failed scrape degrades to a calm ask-to-describe."""
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    try:
        page_text, _title, document = await _scrape_and_draft(
            tenant_id=tenant_id, url=url, provider=bounded
        )
    except ValueError as exc:
        # O-7: the owner gets one calm line either way, but the reason is not
        # thrown away. A 403, a page that renders itself in the browser, and a
        # dead host all read the same on screen and must not read the same here.
        logger.info("url scrape failed reason=%s", _url_failure_code(exc))
        onboarding.history.append({"role": "user", "content": url})
        onboarding.history.append({"role": "assistant", "content": _URL_SCRAPE_FAILED})
        _mark_action(onboarding, key=idempotency_key, fingerprint=action_fingerprint)
        return await _checkpoint(tenant_id, onboarding)

    if document:
        _merge_document_candidates(onboarding, document.get("offering_candidates", []))
    plan = await prepare_url_turn(url=url, page_text=page_text, record=onboarding, provider=bounded)
    plan.record.history.append({"role": "assistant", "content": plan.summary or ""})
    _mark_action(plan.record, key=idempotency_key, fingerprint=action_fingerprint)
    return await _checkpoint(tenant_id, plan.record)


async def run_message_stream(
    *,
    tenant_id: UUID,
    text: str,
    provider: LLMProvider,
    embedder: Embedder,
    idempotency_key: str | None = None,
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
    fingerprint = _fingerprint("text", text)
    if _already_applied(onboarding, key=idempotency_key, fingerprint=fingerprint):
        yield _state_event(onboarding)
        yield {"type": "done"}
        return
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="onboarding already confirmed",
        )
    if onboarding.paused_beat:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="finish the paused field before sending another answer",
        )
    if onboarding.pending_name and not is_affirmative(text):
        _accepted, reply = await propose_name_replacement(
            record=onboarding,
            value=text,
            provider=TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S),
        )
        onboarding.history.append({"role": "user", "content": text})
        onboarding.history.append({"role": "assistant", "content": reply})
        _mark_action(onboarding, key=idempotency_key, fingerprint=fingerprint)
        await _checkpoint(tenant_id, onboarding)
        yield {"type": "progress", "stage": "processing"}
        yield {"type": "token", "text": reply}
        yield {"type": "reply", "text": reply}
        yield _state_event(onboarding)
        yield {"type": "done"}
        return
    url = _find_url(text)
    if url is not None:
        async for event in _stream_url_turn(
            tenant_id=tenant_id,
            url=url,
            onboarding=onboarding,
            provider=provider,
            embedder=embedder,
            idempotency_key=idempotency_key,
            action_fingerprint=fingerprint,
        ):
            yield event
        return
    # ponytail: platform default timeout (see run_message above).
    bounded = TimeLimitedProvider(provider, DEFAULT_LLM_TIMEOUT_S)
    plan = await prepare_turn(admin_message=text, record=onboarding, provider=bounded)
    _mark_action(plan.record, key=idempotency_key, fingerprint=fingerprint)
    await _checkpoint(tenant_id, plan.record)

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

    plan.record.history.append({"role": "assistant", "content": full})
    await _checkpoint(tenant_id, plan.record)

    yield _state_event(plan.record)
    yield {"type": "done"}


async def _stream_url_turn(
    *,
    tenant_id: UUID,
    url: str,
    onboarding: OnboardingRecord,
    provider: LLMProvider,
    embedder: Embedder,
    idempotency_key: str | None,
    action_fingerprint: str,
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
        page_text, _title, document = await _scrape_and_draft(
            tenant_id=tenant_id, url=url, provider=bounded
        )
    except ValueError as exc:
        logger.info("url scrape failed reason=%s", _url_failure_code(exc))
        onboarding.history.append({"role": "user", "content": url})
        _mark_action(onboarding, key=idempotency_key, fingerprint=action_fingerprint)
        await _checkpoint(tenant_id, onboarding)
        yield {"type": "token", "text": _URL_SCRAPE_FAILED}
        yield {"type": "reply", "text": _URL_SCRAPE_FAILED}
        onboarding.history.append({"role": "assistant", "content": _URL_SCRAPE_FAILED})
        await _checkpoint(tenant_id, onboarding)
        yield _state_event(onboarding)
        yield {"type": "done"}
        return

    if document:
        _merge_document_candidates(onboarding, document.get("offering_candidates", []))
    plan = await prepare_url_turn(url=url, page_text=page_text, record=onboarding, provider=bounded)
    _mark_action(plan.record, key=idempotency_key, fingerprint=action_fingerprint)
    await _checkpoint(tenant_id, plan.record)

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
    await _checkpoint(tenant_id, plan.record)

    yield _state_event(plan.record)
    yield {"type": "done"}


async def save_onboarding_knowledge(
    *,
    tenant_id: UUID,
    document_id: UUID,
    sections: list[dict[str, str]],
    offerings: list[PendingOffering],
    embedder: Embedder,
) -> tuple[dict[str, Any], list[PendingOffering]]:
    """Publish one reviewed source and retain its catalog decisions in onboarding."""
    keys: set[str] = set()
    for offering in offerings:
        key = normalize_name(offering.name)
        if not key or key in keys:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="offering names must be unique",
            )
        keys.add(key)

    record = await knowledge_service.publish_record(
        tenant_id=tenant_id,
        document_id=document_id,
        sections=sections,
        offerings=[item.model_dump() for item in offerings],
        embedder=embedder,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document not found")

    onboarding = OnboardingRecord.from_jsonb(await service.load_record(tenant_id=tenant_id))
    onboarding.offering_candidates = [
        item.model_copy(update={"review_status": "approved"}) for item in offerings
    ]
    await _checkpoint(tenant_id, onboarding)
    return record, offerings


async def save_onboarding_knowledge_batch(
    *,
    tenant_id: UUID,
    documents: list[tuple[UUID, list[dict[str, str]]]],
    offerings: list[PendingOffering],
    accept_price_changes: bool,
    embedder: Embedder,
) -> tuple[list[UUID], list[tuple[UUID, str]], list[PendingOffering]]:
    """Publish every reviewed document in one call; a document's own failure
    (not found, a price conflict, or a processing failure surfaced at publish
    time) never aborts the rest.

    W-11a: the offering-name-uniqueness check stays request-level (a malformed
    request is a 422), but everything past it is per-document data in the
    response - see ``OnboardingKnowledgeBatchResponse``.
    """
    keys: set[str] = set()
    for offering in offerings:
        key = normalize_name(offering.name)
        if not key or key in keys:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="offering names must be unique",
            )
        keys.add(key)

    batch_document_ids = {document_id for document_id, _ in documents}
    document_sections = dict(documents)
    failed: list[tuple[UUID, str]] = []
    # Only a hard failure - not found, or publish_record itself reporting
    # status='failed' - withholds an offering below. A price conflict must
    # never count here: the owner needs the conflicted offering to still be in
    # offering_candidates so they can resubmit with accept_price_changes=True.
    hard_failure_ids: set[UUID] = set()

    # A document can support more than one conflicting offering; collect every
    # conflict's message per document rather than keeping only the first.
    price_conflict_messages: dict[UUID, list[str]] = {}
    if not accept_price_changes:
        for offering in offerings:
            if len(offering.price_options) <= 1:
                continue
            message = (
                f"{offering.name}: multiple prices found "
                f"({', '.join(f'{cents} cents' for cents in offering.price_options)}) "
                "- resolve before publishing"
            )
            for document_id in offering.supporting_document_ids:
                if document_id in batch_document_ids:
                    price_conflict_messages.setdefault(document_id, []).append(message)

    price_conflict_ids = set(price_conflict_messages)
    for document_id, messages in price_conflict_messages.items():
        # The document is skipped below, never reaching publish_record, so its
        # submitted edits would otherwise be silently lost.
        try:
            await knowledge_service.save_draft_sections(
                tenant_id=tenant_id,
                document_id=document_id,
                sections=document_sections[document_id],
            )
        except knowledge_service.DocumentNotReviewable as exc:
            failed.append((document_id, str(exc)))
            hard_failure_ids.add(document_id)
        else:
            failed.append((document_id, "; ".join(messages)))

    published: list[UUID] = []
    for document_id, sections in documents:
        if document_id in price_conflict_ids:
            continue
        try:
            record = await knowledge_service.publish_record(
                tenant_id=tenant_id,
                document_id=document_id,
                sections=sections,
                offerings=None,
                reviewable_only=True,
                embedder=embedder,
            )
        except knowledge_service.OfferingPriceConflict as exc:
            failed.append((document_id, str(exc)))
            continue
        except knowledge_service.DocumentNotReviewable as exc:
            failed.append((document_id, str(exc)))
            hard_failure_ids.add(document_id)
            continue
        except (OSError, httpx.HTTPError):
            await knowledge_service.save_draft_sections(
                tenant_id=tenant_id,
                document_id=document_id,
                sections=sections,
            )
            failed.append((document_id, "We could not save this document. Please retry."))
            hard_failure_ids.add(document_id)
            continue
        if record is None:
            failed.append((document_id, "document not found"))
            hard_failure_ids.add(document_id)
            continue
        if record.get("status") == "failed":
            failed.append(
                (document_id, str(record.get("error") or "document could not be published"))
            )
            hard_failure_ids.add(document_id)
            continue
        published.append(document_id)

    offering_candidates = [
        offering
        for offering in offerings
        if not offering.supporting_document_ids
        or not set(offering.supporting_document_ids) <= hard_failure_ids
    ]

    # Unlike an interview turn, this checkpoint carries nothing computed from the
    # record it read: the candidates come from the request. A turn that lands
    # between the read and the write therefore costs nothing but a re-read, so
    # overlapping batches settle last-writer-wins on the candidate list instead
    # of telling the owner their setup moved on.
    approved = [
        item.model_copy(update={"review_status": "approved"}) for item in offering_candidates
    ]
    for _ in range(3):
        onboarding = OnboardingRecord.from_jsonb(await service.load_record(tenant_id=tenant_id))
        onboarding.offering_candidates = approved
        try:
            await service.save_record(tenant_id=tenant_id, record=onboarding.to_jsonb())
        except service.RevisionConflictError:
            continue
        return published, failed, offering_candidates
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_CONFLICT_DETAIL)


async def confirm(
    *,
    tenant_id: UUID,
    slug: str | None = None,
    embedder: Embedder | None = None,
) -> dict[str, Any]:
    record = await service.load_record(tenant_id=tenant_id)
    onboarding = OnboardingRecord.from_jsonb(record)
    if onboarding.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="already confirmed",
        )
    if onboarding.paused_beat:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="finish the paused field before going live",
        )
    documents = await knowledge_service.list_records(tenant_id=tenant_id)
    if any(document["status"] == "draft" for document in documents):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="review or discard every knowledge draft before going live",
        )
    draft = onboarding.draft
    gate = request_finalize(draft, onboarding.skipped)
    if not gate.ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"incomplete - missing: {'; '.join(gate.missing)}",
        )
    # The gate above guarantees all seven fields; extra keys (a pre-O-1 draft's
    # orphan sections) are ignored rather than rejected.
    profile = ProfileDraft.model_validate(draft)
    public_slug = validate_slug(slug or suggested_slug(profile.business_name))
    onboarding.completed = True
    try:
        await service.apply_confirmation(
            tenant_id=tenant_id,
            business_name=profile.business_name,
            slug=public_slug,
            profile=profile.model_dump(),
            # W-9: the voice the owner picked, in the structured shape the
            # customer assistant reads. Expression only - it never carries a
            # fact, a price, or an escalation rule.
            customer_voice=customer_voice_for(profile),
            completed_record=onboarding.to_jsonb(),
            offering_candidates=[
                item for item in onboarding.offering_candidates if item.review_status == "approved"
            ],
            embedder=embedder,
        )
    except service.PublicSlugTakenError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That page address is already taken. Choose another.",
        ) from exc
    return {"tenant_id": tenant_id, "slug": public_slug}
