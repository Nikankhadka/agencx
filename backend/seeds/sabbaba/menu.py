"""Sabbaba menu data (Spring St, Bondi Junction), as of 8 October 2026.

Parsed once from the source menu document (sabbaba-ALL-combined); every price,
description and dietary/allergen note below is that document's own text.

``MENU`` maps category -> [(name, description, price_cents | None)], in document
order. ``price_cents`` is ``None`` where the document says "price not
confirmed". Descriptions keep the document's dietary and allergen notes and, for
Uber Eats-sourced prices, its "Price source: Uber Eats." note. A few names are
cleaned: "(general)" / "(base)" qualifiers are dropped, and an alias in
parentheses moves into the description ("Also listed as ...").
"""

from __future__ import annotations

MENU: dict[str, list[tuple[str, str, int | None]]] = {
    "Pita Pockets": [
        (
            "Sabbaba Pita Pocket",
            (
                "Pita pocket with village salad, tabouli, red cabbage, pickles, hummus, "
                "tahini, babaganoush and salsa. Vegetarian and vegan on the menu. "
                "Allergens in the listed ingredients: sesame (tahini, babaganoush), "
                "wheat/gluten (bulgur in tabouli). Probably also: sesame (hummus), "
                "wheat/gluten (pita). Not confirmed by the kitchen. Also listed as "
                "Sabbaba Pita."
            ),
            1490,
        ),
        (
            "Larnaca Pita Pocket",
            (
                "Pita pocket with village salad, tabouli, olives, green chilli, eggplant, "
                "hummus, tahini and shredded halloumi. Vegetarian. Allergens in the "
                "listed ingredients: milk (halloumi), sesame (tahini), wheat/gluten "
                "(bulgur in tabouli). Probably also: sesame (hummus), wheat/gluten "
                "(pita). Not confirmed by the kitchen."
            ),
            1590,
        ),
        (
            "Tunisian Pita Pocket",
            (
                "Pita pocket with Marrakech salad, eggplant, capsicum, chickpeas, green "
                "chilli, sweet potato, tabouli, hummus and babaganoush. Vegetarian and "
                "vegan on the menu. Allergens in the listed ingredients: sesame "
                "(babaganoush contains tahini), wheat/gluten (bulgur in tabouli). "
                "Probably also: sesame (hummus), wheat/gluten (pita). Not confirmed by "
                "the kitchen."
            ),
            1590,
        ),
        (
            "Algerian Pita Pocket",
            (
                "Pita pocket with tabouli, green chilli, red chilli, chickpeas, eggplant, "
                "pickles, tahini and hummus. Vegetarian and vegan on the menu. Allergens "
                "in the listed ingredients: sesame (tahini), wheat/gluten (bulgur in "
                "tabouli). Probably also: sesame (hummus), wheat/gluten (pita). Not "
                "confirmed by the kitchen."
            ),
            1590,
        ),
        (
            "South American Pita Pocket",
            (
                "Pita pocket with village salad, salsa, jalapenos, olives, red chilli, "
                "green chilli and cheese. Vegetarian. Allergens in the listed "
                "ingredients: milk (cheese). Probably also: wheat/gluten (pita). Not "
                "confirmed by the kitchen."
            ),
            1590,
        ),
        (
            "Tel Aviv Pita Pocket",
            (
                "Pita pocket with village salad, pickles, tahini, hummus and hot chips. "
                "Vegetarian and vegan on the menu. Allergens in the listed ingredients: "
                "sesame (tahini). Probably also: sesame (hummus), wheat/gluten (pita). "
                "Not confirmed by the kitchen."
            ),
            1590,
        ),
        (
            "Koh Samul Pita Pocket",
            (
                "Pita pocket with village salad, sour cream, sweet chilli sauce and "
                "crushed walnuts. Vegetarian. Allergens in the listed ingredients: milk "
                "(sour cream), tree nut: walnut. Probably also: wheat/gluten (pita). Not "
                "confirmed by the kitchen."
            ),
            1590,
        ),
        (
            "Cancun Pita Pocket",
            (
                "Pita pocket with village salad, salsa, sour cream, guacamole, jalapenos, "
                "corn chips and cheese. Vegetarian. Allergens in the listed ingredients: "
                "milk (sour cream, cheese). Probably also: wheat/gluten (pita). Not "
                "confirmed by the kitchen."
            ),
            1590,
        ),
        (
            "Pita Pocket",
            (
                "Pita pocket with village salad, tabouli, red cabbage, pickles, hummus, "
                "tahini, babaganoush and salsa. Same fillings as the Sabbaba Pita Pocket. "
                "Allergens in the listed ingredients: sesame (tahini, babaganoush), "
                "wheat/gluten (bulgur in tabouli). Probably also: sesame (hummus), "
                "wheat/gluten (pita). Not confirmed by the kitchen. Price source: Uber "
                "Eats."
            ),
            2000,
        ),
    ],
    "Plates": [
        (
            "Falafel Plate",
            (
                "Falafel (chickpeas, sesame seeds, green herbs) on a plate. Served with "
                "village salad, tabouli, red cabbage, pickles, hummus, tahini, "
                "babaganoush and salsa and one pita. Vegetarian and vegan on the menu. "
                "Allergens in the listed ingredients: sesame (tahini, babaganoush), "
                "wheat/gluten (bulgur in tabouli), sesame (falafel). Probably also: "
                "wheat/gluten (pita). Falafel is fried; shared fryer not known. Not "
                "confirmed by the kitchen."
            ),
            1790,
        ),
        (
            "Chicken Shish Plate",
            (
                "Grilled marinated chicken with Sabbaba spices. Served with village "
                "salad, tabouli, red cabbage, pickles, hummus, tahini, babaganoush and "
                "salsa and one pita. Allergens in the listed ingredients: sesame (tahini, "
                "babaganoush), wheat/gluten (bulgur in tabouli). Probably also: sesame "
                "(hummus), wheat/gluten (pita). Not confirmed by the kitchen."
            ),
            1790,
        ),
        (
            "Chicken Shawarma Plate",
            (
                "Slow cooked seasoned chicken, thinly sliced. Served with village salad, "
                "tabouli, red cabbage, pickles, hummus, tahini, babaganoush and salsa and "
                "one pita. Allergens in the listed ingredients: sesame (tahini, "
                "babaganoush), wheat/gluten (bulgur in tabouli). Probably also: sesame "
                "(hummus), wheat/gluten (pita). Not confirmed by the kitchen."
            ),
            1790,
        ),
        (
            "Grilled Haloumi Plate",
            (
                "Lightly grilled halloumi with olive oil. Served with village salad, "
                "tabouli, red cabbage, pickles, hummus, tahini, babaganoush and salsa and "
                "one pita. Allergens in the listed ingredients: sesame (tahini, "
                "babaganoush), wheat/gluten (bulgur in tabouli), milk (halloumi). "
                "Probably also: sesame (hummus), wheat/gluten (pita). Not confirmed by "
                "the kitchen."
            ),
            1790,
        ),
        (
            "Grilled Fish Plate",
            (
                "Grilled barramundi fillet. Served with village salad, tabouli, red "
                "cabbage, pickles, hummus, tahini, babaganoush and salsa and one pita. "
                "Allergens in the listed ingredients: sesame (tahini, babaganoush), "
                "wheat/gluten (bulgur in tabouli), fish (barramundi). Probably also: "
                "sesame (hummus), wheat/gluten (pita). Not confirmed by the kitchen."
            ),
            1990,
        ),
        (
            "Plate",
            (
                "Four salads (village salad, tabouli, red cabbage, pickles), four dips "
                "(hummus, tahini, babaganoush, salsa) and one pita. A protein choice sets "
                "the plate price, see the plates above. Allergens in the listed "
                "ingredients: sesame (tahini, babaganoush), wheat/gluten (bulgur in "
                "tabouli). Probably also: sesame (hummus), wheat/gluten (pita). Not "
                "confirmed by the kitchen. Price source: Uber Eats."
            ),
            3000,
        ),
        (
            "Super Plate",
            (
                "Choice of two proteins, four seasonal salads and two dips, with pita. "
                "Ingredients are not fully listed, so allergens are not known. Not "
                "confirmed by the kitchen. Price source: Uber Eats."
            ),
            3700,
        ),
    ],
    "Bowls": [
        (
            "Chicken Shish Bowl",
            (
                "Grilled marinated chicken with Sabbaba spices. With village salad, "
                "tabouli, red cabbage, pickles, tahini and one pita in a bowl. Allergens "
                "in the listed ingredients: sesame (tahini), wheat/gluten (bulgur in "
                "tabouli). Probably also: wheat/gluten (pita). Not confirmed by the "
                "kitchen."
            ),
            1690,
        ),
        (
            "Falafel Bowl",
            (
                "Falafel (chickpeas, sesame seeds, green herbs) with chickpeas. With "
                "village salad, tabouli, red cabbage, pickles, tahini and one pita in a "
                "bowl. Allergens in the listed ingredients: sesame (tahini, falafel), "
                "wheat/gluten (bulgur in tabouli). Probably also: wheat/gluten (pita). "
                "Falafel is fried; shared fryer not known. Not confirmed by the kitchen."
            ),
            1690,
        ),
        (
            "Grilled Haloumi Bowl",
            (
                "Halloumi. With village salad, tabouli, red cabbage, pickles, tahini and "
                "one pita in a bowl. Allergens in the listed ingredients: milk "
                "(halloumi), sesame (tahini), wheat/gluten (bulgur in tabouli). Probably "
                "also: wheat/gluten (pita). Not confirmed by the kitchen."
            ),
            1690,
        ),
        (
            "Chicken Shawarma Bowl",
            (
                "Slow cooked seasoned chicken, thinly sliced. With village salad, "
                "tabouli, red cabbage, pickles, tahini and one pita in a bowl. Allergens "
                "in the listed ingredients: sesame (tahini), wheat/gluten (bulgur in "
                "tabouli). Probably also: wheat/gluten (pita). Not confirmed by the "
                "kitchen."
            ),
            1690,
        ),
        (
            "Grilled Fish Bowl",
            (
                "Grilled barramundi fillet with village salad, tabouli, red cabbage, "
                "pickles, hummus, tahini, babaganoush, salsa and one pita in a bowl. "
                "Allergens in the listed ingredients: sesame (tahini, babaganoush), "
                "wheat/gluten (bulgur in tabouli), fish (barramundi). Probably also: "
                "sesame (hummus), wheat/gluten (pita). Not confirmed by the kitchen."
            ),
            1890,
        ),
        (
            "Bowl",
            (
                "Bowl served with tahini and pita on the side instead of wrapped. "
                "Allergens in the listed ingredients: sesame (tahini). Probably also: "
                "wheat/gluten (pita). Not confirmed by the kitchen. Price source: Uber "
                "Eats."
            ),
            2700,
        ),
    ],
    "Salads": [
        (
            "Exotic Salad, small (2 choices)",
            (
                "Small salad box with two salad choices. Ingredients are not fully "
                "listed, so allergens are not known. Not confirmed by the kitchen."
            ),
            990,
        ),
        (
            "Exotic Salad, medium (3 choices)",
            (
                "Medium salad box with three salad choices. Ingredients are not fully "
                "listed, so allergens are not known. Not confirmed by the kitchen."
            ),
            1190,
        ),
        (
            "Exotic Salad, large (3 choices)",
            (
                "Large salad box with three salad choices. Ingredients are not fully "
                "listed, so allergens are not known. Not confirmed by the kitchen."
            ),
            1390,
        ),
        (
            "Cauliflower and Avocado Salad",
            (
                "Lightly fried cauliflower with avocado. Vegetarian, vegan and gluten "
                "free on the menu. No allergen is declared in the listed ingredients. "
                "Cauliflower is fried; shared fryer not known. Not confirmed by the "
                "kitchen. Price source: Uber Eats."
            ),
            1400,
        ),
        (
            "Tabouli",
            (
                "Parsley, tomatoes, shallots, bulgur, olive oil, lemon juice, salt and "
                "pepper. Vegan on the menu. Allergens in the listed ingredients: "
                "wheat/gluten (bulgur). Not gluten free. Not confirmed by the kitchen. "
                "Price source: Uber Eats."
            ),
            1400,
        ),
        (
            "Red Cabbage Salad",
            (
                "Chopped red cabbage in a slightly sweet and sour dressing. No allergen "
                "is declared in the listed ingredients. Not confirmed by the kitchen. "
                "Price source: Uber Eats."
            ),
            1200,
        ),
        (
            "Pickles",
            (
                "Roughly sliced pickles, fermented. No allergen is declared in the listed "
                "ingredients. Not confirmed by the kitchen. Price source: Uber Eats."
            ),
            1000,
        ),
        (
            "Crunchy Edamame Salad",
            (
                "Edamame salad. Vegan and gluten free on the menu. Allergens in the "
                "listed ingredients: soy (edamame). Not confirmed by the kitchen. Price "
                "source: Uber Eats."
            ),
            1400,
        ),
        (
            "Lentil, Quinoa and Haloumi Salad",
            (
                "Lentil, quinoa and halloumi. Vegetarian and gluten free on the menu. "
                "Allergens in the listed ingredients: milk (halloumi). Not confirmed by "
                "the kitchen. Price source: Uber Eats."
            ),
            1400,
        ),
    ],
    "Sides": [
        (
            "Hot Chips",
            (
                "Lightly seasoned chips. Vegetarian and vegan on the menu. No allergen is "
                "declared in the listed ingredients. Fryer sharing not known. Not "
                "confirmed by the kitchen."
            ),
            600,
        ),
        (
            "Sweet Potato Chips",
            (
                "Thick cut sweet potato chips, lightly seasoned. Vegetarian and vegan on "
                "the menu. No allergen is declared in the listed ingredients. Fryer "
                "sharing not known. Not confirmed by the kitchen."
            ),
            700,
        ),
        (
            "Falafel, 6 pieces",
            (
                "Falafel balls (chickpeas, sesame seeds, green herbs) served with tahini "
                "dip. Allergens in the listed ingredients: sesame (falafel, tahini). "
                "Fried; shared fryer not known. Not confirmed by the kitchen."
            ),
            890,
        ),
        (
            "Falafel, 12 pieces",
            (
                "Falafel balls (chickpeas, sesame seeds, green herbs) served with tahini "
                "dip. Vegetarian and vegan on the menu. Allergens in the listed "
                "ingredients: sesame (falafel, tahini). Fried; shared fryer not known. "
                "Not confirmed by the kitchen."
            ),
            1490,
        ),
        (
            "Corn Chips with Guacamole",
            (
                "Corn chips served with guacamole. No allergen is declared in the listed "
                "ingredients. Not confirmed by the kitchen."
            ),
            690,
        ),
        (
            "Vine Leaves",
            (
                "Four rolled vine leaves stuffed with rice, tomato, onion, parsley and "
                "spices, cooked with olive oil and lemon juice. Vegetarian and vegan on "
                "the menu. No allergen is declared in the listed ingredients. Not "
                "confirmed by the kitchen."
            ),
            690,
        ),
        (
            "Haloumi Chips with Tzatziki",
            (
                "Golden halloumi chips with tzatziki for dipping. Vegetarian. Allergens "
                "in the listed ingredients: milk (halloumi). Probably also: milk "
                "(tzatziki yoghurt). Not confirmed by the kitchen. Price source: Uber "
                "Eats."
            ),
            1390,
        ),
        (
            "Chicken Shawarma (side)",
            (
                "Thinly sliced chicken shawarma seasoned with Middle Eastern spices. "
                "Ingredients are not fully listed, so allergens are not known. Not "
                "confirmed by the kitchen. Price source: Uber Eats."
            ),
            1900,
        ),
        (
            "Chicken Shish (side)",
            (
                "Marinated chicken skewers, grilled. Ingredients are not fully listed, so "
                "allergens are not known. Not confirmed by the kitchen. Price source: "
                "Uber Eats."
            ),
            1900,
        ),
        (
            "Lamb Shish (side)",
            (
                "Lamb skewers, marinated and grilled. Ingredients are not fully listed, "
                "so allergens are not known. Not confirmed by the kitchen. Price source: "
                "Uber Eats."
            ),
            2190,
        ),
        (
            "Lamb Kofta (side)",
            (
                "Lamb patties flavoured with aromatic spices. Ingredients are not fully "
                "listed, so allergens are not known. Not confirmed by the kitchen. Price "
                "source: Uber Eats."
            ),
            1890,
        ),
        (
            "Beef Shawarma (side)",
            (
                "Shawarma-spiced beef slices with onions. Ingredients are not fully "
                "listed, so allergens are not known. Not confirmed by the kitchen. Price "
                "source: Uber Eats."
            ),
            2090,
        ),
        (
            "Chicken Schnitzel (side)",
            (
                "Breaded and fried chicken breast cutlet. No allergen is declared in the "
                "listed ingredients. Probably also: wheat/gluten (crumb), egg (crumb). "
                "Not confirmed by the kitchen. Price source: Uber Eats."
            ),
            1600,
        ),
        (
            "Grilled Barramundi (side)",
            (
                "Barramundi grilled with Sabbaba spices. Allergens in the listed "
                "ingredients: fish (barramundi). Not confirmed by the kitchen. Price "
                "source: Uber Eats."
            ),
            1990,
        ),
        (
            "Chips and Dips Share Pack",
            (
                "Hot chips and sweet potato chips with two chip dips. Ingredients are not "
                "fully listed, so allergens are not known. Not confirmed by the kitchen. "
                "Price source: Uber Eats."
            ),
            1500,
        ),
    ],
    "Dips and Extras": [
        (
            "Hummus",
            (
                "Homemade small batch hummus with chickpeas and olive oil. Vegan on the "
                "menu. The side serve comes with a pita. No allergen is declared in the "
                "listed ingredients. Probably also: sesame (tahini). Not confirmed by the "
                "kitchen. Price source: Uber Eats."
            ),
            1390,
        ),
        (
            "Tahini",
            (
                "Tahini blended with fresh garlic, lemon, salt and pepper. Vegan on the "
                "menu. Allergens in the listed ingredients: sesame (tahini). Not "
                "confirmed by the kitchen. Price source: Uber Eats."
            ),
            1390,
        ),
        (
            "Babaganoush",
            (
                "Roasted eggplant, smashed and blended with tahini. Vegan on the menu. "
                "Allergens in the listed ingredients: sesame (tahini). Not confirmed by "
                "the kitchen. Price source: Uber Eats."
            ),
            1390,
        ),
        (
            "Salsa",
            (
                "Fire roasted tomatoes, capsicums and onions blended with fresh herbs and "
                "spices. Vegan on the menu. No allergen is declared in the listed "
                "ingredients. Not confirmed by the kitchen. Price source: Uber Eats."
            ),
            1390,
        ),
        (
            "Red Chilli",
            (
                "House made chilli of smashed red chillies, herbs and spices. Ingredients "
                "are not fully listed, so allergens are not known. Not confirmed by the "
                "kitchen. Price source: Uber Eats."
            ),
            350,
        ),
        (
            "Green Chilli",
            (
                "House made chilli of smashed green chillies, herbs and spices. "
                "Ingredients are not fully listed, so allergens are not known. Not "
                "confirmed by the kitchen. Price source: Uber Eats."
            ),
            350,
        ),
        (
            "Garlic Dip",
            (
                "Traditional creamy garlic dip. Ingredients are not fully listed, so "
                "allergens are not known. Probably also: egg or milk, depending on the "
                "recipe. Not confirmed by the kitchen. Price source: Uber Eats."
            ),
            350,
        ),
        (
            "Garlic Aioli",
            (
                "Garlic aioli, gluten free on the menu. Ingredients are not fully listed, "
                "so allergens are not known. Probably also: egg. Not confirmed by the "
                "kitchen. Price source: Uber Eats."
            ),
            250,
        ),
        (
            "Jalapenos",
            (
                "Jalapenos for a chilli kick. No allergen is declared in the listed "
                "ingredients. Not confirmed by the kitchen. Price source: Uber Eats."
            ),
            250,
        ),
        (
            "White Pita Bread (4 pieces)",
            (
                "House made pita bread. Ingredients are not fully listed, so allergens "
                "are not known. Probably also: wheat/gluten. Not confirmed by the "
                "kitchen. Price source: Uber Eats."
            ),
            600,
        ),
        (
            "Brown Pita Bread (4 pieces)",
            (
                "House made pita bread. Ingredients are not fully listed, so allergens "
                "are not known. Probably also: wheat/gluten. Not confirmed by the "
                "kitchen. Price source: Uber Eats."
            ),
            650,
        ),
        (
            "Wholemeal Pita Bread",
            (
                "Soft pita made from wholemeal flour. Allergens in the listed "
                "ingredients: wheat/gluten (flour). Not confirmed by the kitchen. Price "
                "source: Uber Eats."
            ),
            300,
        ),
        (
            "Zaatar Pita (2 pieces)",
            (
                "Soft, crispy pita infused with zaatar. Ingredients are not fully listed, "
                "so allergens are not known. Probably also: wheat/gluten, sesame (zaatar "
                "often includes sesame). Not confirmed by the kitchen. Price source: Uber "
                "Eats."
            ),
            550,
        ),
    ],
    "Breakfast": [
        (
            "Ham, Cheese and Tomato Bagel",
            (
                "Ham, cheese and tomato on a bagel. Toasted or not. Allergens in the "
                "listed ingredients: milk (cheese). Probably also: wheat/gluten (bagel). "
                "Not confirmed by the kitchen."
            ),
            1190,
        ),
        (
            "Salami, Cheese and Tomato Bagel",
            (
                "Salami, cheese and tomato on a bagel. Toasted or not. Allergens in the "
                "listed ingredients: milk (cheese). Probably also: wheat/gluten (bagel). "
                "Not confirmed by the kitchen."
            ),
            1190,
        ),
        (
            "Cheese, Tomato and Basil Bagel",
            (
                "Melted cheese, fresh tomato and basil on a toasted bagel. Vegetarian. "
                "Allergens in the listed ingredients: milk (cheese). Probably also: "
                "wheat/gluten (bagel). Not confirmed by the kitchen."
            ),
            1090,
        ),
        (
            "Salmon and Cream Cheese Bagel",
            (
                "Smoked salmon and cream cheese on a bagel. Toasted or not. Allergens in "
                "the listed ingredients: fish (salmon), milk (cream cheese). Probably "
                "also: wheat/gluten (bagel). Not confirmed by the kitchen."
            ),
            1290,
        ),
        (
            "Bacon, Egg and Cheese Bagel",
            (
                "Crisp bacon, fried egg and melted cheese. Toasted or not. Allergens in "
                "the listed ingredients: egg, milk (cheese). Probably also: wheat/gluten "
                "(bagel). Not confirmed by the kitchen. Also listed as Bacon Egg "
                "Envelopes."
            ),
            1190,
        ),
        (
            "Grilled Haloumi, Chicken and Avocado Bagel",
            (
                "Grilled halloumi, chicken and avocado on a bagel. Toasted or not. "
                "Allergens in the listed ingredients: milk (halloumi). Probably also: "
                "wheat/gluten (bagel). Not confirmed by the kitchen."
            ),
            1290,
        ),
        (
            "Grilled Chicken and Avocado Gondola",
            (
                "Grilled chicken and creamy avocado on a bagel. Toasted or not. No "
                "allergen is declared in the listed ingredients. Probably also: "
                "wheat/gluten (bagel). Not confirmed by the kitchen."
            ),
            1290,
        ),
        (
            "Grilled Haloumi and Eggplant Gondola",
            (
                "Grilled halloumi and charred eggplant on a bagel. Toasted or not. "
                "Vegetarian. Allergens in the listed ingredients: milk (halloumi). "
                "Probably also: wheat/gluten (bagel). Not confirmed by the kitchen."
            ),
            1290,
        ),
        (
            "Haloumi and Egg Triangle",
            (
                "Crisp triangle filled with halloumi and egg. Vegetarian. Allergens in "
                "the listed ingredients: milk (halloumi), egg. Probably also: "
                "wheat/gluten (pastry). Not confirmed by the kitchen."
            ),
            1190,
        ),
        (
            "Spicy Tuna Bagel",
            (
                "Spicy tuna on a bagel. Allergens in the listed ingredients: fish (tuna). "
                "Probably also: wheat/gluten (bagel), egg (mayonnaise). Not confirmed by "
                "the kitchen."
            ),
            1190,
        ),
        (
            "Chicken Wrap",
            (
                "Chicken wrap. Ingredients are not fully listed, so allergens are not "
                "known. Probably also: wheat/gluten (wrap). Not confirmed by the kitchen."
            ),
            1290,
        ),
        (
            "Tuna Wrap",
            (
                "Tuna wrap. Allergens in the listed ingredients: fish (tuna). Probably "
                "also: wheat/gluten (wrap). Not confirmed by the kitchen."
            ),
            1290,
        ),
        (
            "Tuna, Cheese and Tender Greens Bagel",
            (
                "Tuna, melted cheese and tender greens on a bagel. Allergens in the "
                "listed ingredients: fish (tuna), milk (cheese). Probably also: "
                "wheat/gluten (bagel). Not confirmed by the kitchen. Price source: Uber "
                "Eats."
            ),
            1590,
        ),
        (
            "Chunky Egg and Tender Greens Bagel",
            (
                "Chunky egg and tender greens in a bagel. Allergens in the listed "
                "ingredients: egg. Probably also: wheat/gluten (bagel). Not confirmed by "
                "the kitchen."
            ),
            None,
        ),
        (
            "Grilled Chicken and Avocado Bagel",
            (
                "Grilled chicken and avocado in a toasted bagel. No allergen is declared "
                "in the listed ingredients. Probably also: wheat/gluten (bagel). Not "
                "confirmed by the kitchen. Price source: Uber Eats."
            ),
            1590,
        ),
    ],
    "Coffee and Hot Drinks": [
        (
            "Coffee: Cappuccino, Flat White, Latte, Mocha, Chai Latte or Tea",
            (
                "Hot drinks. Milk choices: full cream, skim, soy and almond. A large size "
                "is also offered, see Large Coffee. Allergens in the listed ingredients: "
                "milk (full cream, skim), soy (soy milk option), tree nut: almond (almond "
                "milk option). Not confirmed by the kitchen."
            ),
            450,
        ),
        (
            "Large Coffee",
            (
                "Large size of the milk coffees such as cappuccino, flat white and latte. "
                "Milk choices: full cream, skim, soy and almond. Allergens in the listed "
                "ingredients: milk (full cream, skim), soy (soy milk option), tree nut: "
                "almond (almond milk option). Not confirmed by the kitchen. Price source: "
                "Uber Eats."
            ),
            750,
        ),
        (
            "Hot Chocolate",
            (
                "Steamed milk over melted chocolate with chocolate powder. Allergens in "
                "the listed ingredients: milk. Probably also: soy (milk choice). Not "
                "confirmed by the kitchen."
            ),
            400,
        ),
        (
            "Long Black, Macchiato or Piccolo",
            (
                "Espresso based drinks; macchiato and piccolo include a little steamed "
                "milk. Allergens in the listed ingredients: milk (macchiato, piccolo). "
                "Not confirmed by the kitchen."
            ),
            400,
        ),
        (
            "Espresso",
            (
                "A single shot of espresso. No allergen is declared in the listed "
                "ingredients. Not confirmed by the kitchen."
            ),
            350,
        ),
        (
            "Babyccino",
            (
                "Small frothed milk drink for children. Allergens in the listed "
                "ingredients: milk. Not confirmed by the kitchen."
            ),
            100,
        ),
    ],
    "Cold Drinks": [
        (
            "Soft Drink Can",
            (
                "Cold canned soft drink. Flavours are not listed. Ingredients are not "
                "fully listed, so allergens are not known. Not confirmed by the kitchen."
            ),
            360,
        ),
        (
            "Housemade Lemonade",
            (
                "House made lemon drink. No allergen is declared in the listed "
                "ingredients. Not confirmed by the kitchen. Also listed as Sabbaba "
                "Lemonade."
            ),
            400,
        ),
        (
            "Juice",
            (
                "Juice; the flavour is chosen in store. Ingredients are not fully listed, "
                "so allergens are not known. Not confirmed by the kitchen."
            ),
            450,
        ),
        (
            "Sparkling Water",
            (
                "Sparkling water. No allergen is declared in the listed ingredients. Not "
                "confirmed by the kitchen."
            ),
            400,
        ),
        (
            "Water",
            (
                "Water. No allergen is declared in the listed ingredients. Not confirmed "
                "by the kitchen."
            ),
            360,
        ),
    ],
    "Sweets": [
        (
            "Baklava",
            (
                "Layered pastry filled with nuts. Allergens in the listed ingredients: "
                "tree nuts (type not listed). Probably also: wheat/gluten (pastry), milk "
                "(butter). Not confirmed by the kitchen."
            ),
            450,
        ),
        (
            "Chocolate Brownie",
            (
                "Rich, fudgy brownie. Ingredients are not fully listed, so allergens are "
                "not known. Probably also: wheat/gluten, egg, milk. Not confirmed by the "
                "kitchen."
            ),
            480,
        ),
        (
            "Muffin",
            (
                "Muffin, chocolate or mixed berry. Ingredients are not fully listed, so "
                "allergens are not known. Probably also: wheat/gluten, egg, milk. Not "
                "confirmed by the kitchen."
            ),
            480,
        ),
        (
            "Banana Bread",
            (
                "Moist banana loaf with a hint of vanilla. Ingredients are not fully "
                "listed, so allergens are not known. Probably also: wheat/gluten, egg. "
                "Not confirmed by the kitchen."
            ),
            480,
        ),
        (
            "Cinnamon Scroll",
            (
                "Sweet, swirly pastry filled with cinnamon. Ingredients are not fully "
                "listed, so allergens are not known. Probably also: wheat/gluten, egg, "
                "milk. Not confirmed by the kitchen."
            ),
            480,
        ),
        (
            "Caramel Slice",
            (
                "Caramel slice. Ingredients are not fully listed, so allergens are not "
                "known. Probably also: wheat/gluten, milk. Not confirmed by the kitchen."
            ),
            480,
        ),
        (
            "FNG Bar (Fig, Nut, Grain)",
            (
                "Bar of fig, nuts and grain. Allergens in the listed ingredients: tree "
                "nuts (type not listed). Not confirmed by the kitchen."
            ),
            490,
        ),
        (
            "Pistachio Bar",
            (
                "Rich coconut and pistachio bar. Gluten free on the menu. Allergens in "
                "the listed ingredients: tree nut: pistachio. Not confirmed by the "
                "kitchen. Also listed as Coconut and Pistachio Bar."
            ),
            490,
        ),
        (
            "Protein Balls",
            (
                "Protein balls. Ingredients are not fully listed, so allergens are not "
                "known. Not confirmed by the kitchen."
            ),
            470,
        ),
        (
            "Smart Cookie",
            (
                "A classic cookie. Ingredients are not fully listed, so allergens are not "
                "known. Probably also: wheat/gluten, egg, milk. Not confirmed by the "
                "kitchen. Price source: Uber Eats."
            ),
            420,
        ),
        (
            "Caramel Cookie",
            (
                "Caramel cookie. Ingredients are not fully listed, so allergens are not "
                "known. Probably also: wheat/gluten, egg, milk. Not confirmed by the "
                "kitchen."
            ),
            None,
        ),
    ],
}
