from __future__ import annotations

from typing import Any

from app.features.business import service


class CategoryProvider:
    def __init__(self) -> None:
        self.system_prompt = ""
        self.user_input = ""

    async def extract(self, *, system_prompt: str, user_input: str, schema: Any) -> Any:
        self.system_prompt = system_prompt
        self.user_input = user_input
        return schema(category="Screen repairs")


async def test_category_suggestion_uses_no_price_and_prefers_existing_categories() -> None:
    provider = CategoryProvider()

    result = await service._suggest_category(
        name="iPhone 12 screen replacement",
        description="OEM display replacement",
        preferred=["Screen repairs", "Accessories"],
        provider=provider,  # type: ignore[arg-type]
    )

    assert result == "Screen repairs"
    assert "Screen repairs" in provider.system_prompt
    assert "Accessories" in provider.system_prompt
    assert "iPhone 12 screen replacement" in provider.user_input
    assert "OEM display replacement" in provider.user_input
    assert "$" not in provider.user_input
    assert "price" not in provider.user_input.lower()
