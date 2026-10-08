"""Sabbaba 2 catalog summaries, synced from the source Sabbaba menu.

The clone keeps Sabbaba's full 96-item menu, its categories and its prices
byte-identical (both seeds build from ``seeds.sabbaba.menu.MENU`` at import
time). Only the catalog copy changes: each offering's long allergen note is
replaced by one terse line so the whole catalog fits the fast-path prompt
budget (``CATALOG_INLINE_MAX_TOKENS``, see .env.example). The allergen and
dietary detail still ships in ``knowledge.py``'s documents, which read the
full source descriptions.

``SUMMARIES`` is checked against the source menu's names at import: adding,
renaming or removing an item there fails loudly here instead of silently
drifting. Every line is drawn from that item's own source description and
makes no claim the source does not.
"""

from __future__ import annotations

from seeds.sabbaba.menu import MENU as SOURCE_MENU

SUMMARIES: dict[str, str] = {
    # Pita Pockets
    "Sabbaba Pita Pocket": "Village salad, hummus and tahini.",
    "Larnaca Pita Pocket": "Olives, eggplant, hummus, halloumi.",
    "Tunisian Pita Pocket": "Eggplant, chickpeas, sweet potato.",
    "Algerian Pita Pocket": "Chickpeas, eggplant and pickles.",
    "South American Pita Pocket": "Jalapenos, olives and cheese.",
    "Tel Aviv Pita Pocket": "Salad, pickles, hummus and chips.",
    "Koh Samul Pita Pocket": "Salad, sweet chilli and walnuts.",
    "Cancun Pita Pocket": "Guacamole, jalapenos and cheese.",
    "Pita Pocket": "Same as the Sabbaba Pita Pocket.",
    # Plates
    "Falafel Plate": "Falafel with salads, dips and pita.",
    "Chicken Shish Plate": "Grilled chicken, salads and pita.",
    "Chicken Shawarma Plate": "Chicken shawarma, salads and pita.",
    "Grilled Haloumi Plate": "Grilled halloumi, salads and pita.",
    "Grilled Fish Plate": "Grilled barramundi, salads, pita.",
    "Plate": "Four salads, four dips and pita.",
    "Super Plate": "Two proteins, salads and two dips.",
    # Bowls
    "Chicken Shish Bowl": "Grilled chicken, salads and tahini.",
    "Falafel Bowl": "Falafel, salads and tahini.",
    "Grilled Haloumi Bowl": "Halloumi, salads and tahini.",
    "Chicken Shawarma Bowl": "Chicken shawarma, salads, tahini.",
    "Grilled Fish Bowl": "Fish, salads, dips and tahini.",
    "Bowl": "Salads, dips, tahini and pita.",
    # Salads
    "Exotic Salad, small (2 choices)": "Salad box with two choices.",
    "Exotic Salad, medium (3 choices)": "Salad box with three choices.",
    "Exotic Salad, large (3 choices)": "Large salad box, three choices.",
    "Cauliflower and Avocado Salad": "Fried cauliflower and avocado.",
    "Tabouli": "Parsley, tomato, bulgur and lemon.",
    "Red Cabbage Salad": "Red cabbage in sweet dressing.",
    "Pickles": "Sliced fermented pickles.",
    "Crunchy Edamame Salad": "Edamame salad.",
    "Lentil, Quinoa and Haloumi Salad": "Lentil, quinoa and haloumi.",
    # Sides
    "Hot Chips": "Lightly seasoned chips.",
    "Sweet Potato Chips": "Thick cut sweet potato chips.",
    "Falafel, 6 pieces": "Six falafel with tahini dip.",
    "Falafel, 12 pieces": "Twelve falafel with tahini dip.",
    "Corn Chips with Guacamole": "Corn chips with guacamole.",
    "Vine Leaves": "Vine leaves stuffed with rice.",
    "Haloumi Chips with Tzatziki": "Haloumi chips with tzatziki.",
    "Chicken Shawarma (side)": "Thinly sliced chicken shawarma.",
    "Chicken Shish (side)": "Grilled marinated chicken skewers.",
    "Lamb Shish (side)": "Marinated grilled lamb skewers.",
    "Lamb Kofta (side)": "Spiced lamb patties.",
    "Beef Shawarma (side)": "Shawarma beef slices with onion.",
    "Chicken Schnitzel (side)": "Breaded fried chicken cutlet.",
    "Grilled Barramundi (side)": "Barramundi with Sabbaba spices.",
    "Chips and Dips Share Pack": "Chips with two chip dips.",
    # Dips and Extras
    "Hummus": "Chickpea hummus with olive oil.",
    "Tahini": "Tahini with garlic and lemon.",
    "Babaganoush": "Roasted eggplant and tahini dip.",
    "Salsa": "Roasted tomato and capsicum dip.",
    "Red Chilli": "House made red chilli.",
    "Green Chilli": "House made green chilli.",
    "Garlic Dip": "Creamy garlic dip.",
    "Garlic Aioli": "Garlic aioli, gluten free.",
    "Jalapenos": "Sliced jalapenos.",
    "White Pita Bread (4 pieces)": "Four white pita breads.",
    "Brown Pita Bread (4 pieces)": "Four brown pita breads.",
    "Wholemeal Pita Bread": "Soft wholemeal pita.",
    "Zaatar Pita (2 pieces)": "Two pita with zaatar.",
    # Breakfast
    "Ham, Cheese and Tomato Bagel": "Ham, cheese and tomato bagel.",
    "Salami, Cheese and Tomato Bagel": "Salami, cheese and tomato bagel.",
    "Cheese, Tomato and Basil Bagel": "Cheese, tomato and basil bagel.",
    "Salmon and Cream Cheese Bagel": "Salmon and cream cheese bagel.",
    "Bacon, Egg and Cheese Bagel": "Bacon, egg and cheese bagel.",
    "Grilled Haloumi, Chicken and Avocado Bagel": "Haloumi, chicken and avocado bagel.",
    "Grilled Chicken and Avocado Gondola": "Chicken and avocado gondola.",
    "Grilled Haloumi and Eggplant Gondola": "Haloumi and eggplant gondola.",
    "Haloumi and Egg Triangle": "Halloumi and egg triangle.",
    "Spicy Tuna Bagel": "Spicy tuna bagel.",
    "Chicken Wrap": "Chicken wrap.",
    "Tuna Wrap": "Tuna wrap.",
    "Tuna, Cheese and Tender Greens Bagel": "Tuna, cheese and greens bagel.",
    "Chunky Egg and Tender Greens Bagel": "Chunky egg and greens bagel.",
    "Grilled Chicken and Avocado Bagel": "Grilled chicken and avocado bagel.",
    # Coffee and Hot Drinks
    "Coffee: Cappuccino, Flat White, Latte, Mocha, Chai Latte or Tea": "Coffee or chai, any style.",
    "Large Coffee": "Large milk coffee, any style.",
    "Hot Chocolate": "Steamed milk and chocolate.",
    "Long Black, Macchiato or Piccolo": "Long black, macchiato or piccolo.",
    "Espresso": "Single espresso shot.",
    "Babyccino": "Frothed milk for children.",
    # Cold Drinks
    "Soft Drink Can": "Canned soft drink.",
    "Housemade Lemonade": "House made lemonade.",
    "Juice": "Juice, flavour in store.",
    "Sparkling Water": "Sparkling water.",
    "Water": "Still water.",
    # Sweets
    "Baklava": "Layered pastry with nuts.",
    "Chocolate Brownie": "Rich fudgy brownie.",
    "Muffin": "Chocolate or berry muffin.",
    "Banana Bread": "Banana loaf with vanilla.",
    "Cinnamon Scroll": "Cinnamon swirl pastry.",
    "Caramel Slice": "Caramel slice.",
    "FNG Bar (Fig, Nut, Grain)": "Fig, nut and grain bar.",
    "Pistachio Bar": "Coconut and pistachio bar.",
    "Protein Balls": "Protein balls.",
    "Smart Cookie": "Classic cookie.",
    "Caramel Cookie": "Caramel cookie.",
}

_SOURCE_NAMES = [name for items in SOURCE_MENU.values() for name, _, _ in items]

if set(SUMMARIES) != set(_SOURCE_NAMES) or len(SUMMARIES) != len(_SOURCE_NAMES):
    _missing = sorted(set(_SOURCE_NAMES) - set(SUMMARIES))
    _extra = sorted(set(SUMMARIES) - set(_SOURCE_NAMES))
    raise RuntimeError(
        "sababa2 SUMMARIES is out of sync with seeds.sabbaba.menu.MENU: "
        f"missing={_missing} extra={_extra}"
    )
