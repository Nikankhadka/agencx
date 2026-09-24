from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.features.business.api import OfferingCreate
from app.onboarding.flow import PendingOffering


def test_offering_memberships_require_unique_ids_and_selected_primary() -> None:
    selected = uuid4()
    with pytest.raises(ValidationError, match="category_ids must be unique"):
        OfferingCreate(name="Repair", category_ids=[selected, selected])

    with pytest.raises(ValidationError, match="primary_category_id must be included"):
        OfferingCreate(
            name="Repair",
            category_ids=[selected],
            primary_category_id=uuid4(),
        )


def test_model_category_suggestion_is_not_a_confirmed_membership() -> None:
    candidate = PendingOffering(
        name="Screen replacement",
        proposed_category="Screen care",
        sources=["document"],
    )

    assert candidate.category_ids is None
    assert candidate.primary_category_id is None
