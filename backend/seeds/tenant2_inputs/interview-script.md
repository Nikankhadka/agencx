# Tenant 2 interview script

The words the clinic owner provides during onboarding (Surface 2), one answer
per stage, in beat order (see `app/onboarding/beats.py`). This file is the
single source of truth for the proof run: `seed_tenant2_dental.py` parses the
fenced block under each `## stage: <name>` heading and folds it into the
agentic v2 draft it pre-populates before calling the confirm endpoint. Team
size, inbound channels, payment mode/terms, and tax registration are fixed
config for this proof and set directly in the seed; the free-text answers here
are the ones an owner would actually type.

Nothing here is platform configuration. It is what a dentist would say if
asked the same questions across a counter - which is the whole point of the
generalization proof. If the platform needs anything dental-specific that is
not expressible in these answers plus the three uploaded documents, that is a
domain-agnostic bug in the platform, not a gap in this script.

## stage: business_name

```
Northgate Family Dental
```

## stage: hours_contact

```
Mon-Fri 8:00 to 18:00, Sat 9:00 to 13:00
03 5555 0142
```

## stage: identity

```
We're Northgate Family Dental, a three-chair general dental practice in a
suburban high street. We look after families - kids from their first tooth,
their parents, and a lot of older patients who've been with us for years.
Mostly routine check-ups, hygiene and fillings, with crowns, root canals,
extractions and implants when people need them.
```

## stage: tone

```
Warm and reassuring, but never chatty for the sake of it. A lot of people
are genuinely anxious about the dentist, so be calm and plain-spoken, explain
things without jargon, and never oversell treatment. Professional, not
stiff.
```

## stage: services

```
New patient exam 95 dollars
Routine check-up 55 dollars
Bitewing X-rays 35 dollars
Panoramic X-ray 90 dollars
Emergency exam for pain 75 dollars
Scale and polish 85 dollars
Deep cleaning 130 dollars
Fluoride varnish 30 dollars
Fissure sealant 45 dollars
Night guard 320 dollars
White filling single surface 145 dollars
White filling larger 195 dollars
Amalgam filling 120 dollars
Porcelain crown 950 dollars
Veneer 890 dollars
Inlay or onlay 780 dollars
Root canal front tooth 620 dollars
Root canal premolar 740 dollars
Root canal molar 920 dollars
Simple extraction 180 dollars
Surgical extraction 340 dollars
Wisdom tooth extraction 420 dollars
Implant with crown 3200 dollars
Three-unit bridge 2400 dollars
Full denture 1450 dollars
Partial denture 980 dollars
Take-home whitening 380 dollars
In-chair whitening 550 dollars
Whitening gel syringe 45 dollars
```

## stage: pricing_rules

```
Deep cleaning 130 dollars per quadrant
Wisdom tooth extraction 420 dollars per tooth
Out-of-hours surcharge 60 dollars flat
Missed appointment fee 50 dollars flat
Family preventive plan 55 dollars monthly
```

## stage: escalation_threshold

```
Be cautious. Anything clinical - whether someone actually needs a
particular treatment, what's causing their pain, whether something is
urgent - goes to a human, always. Same for anything about an individual
patient's records or insurance. Answer fees, opening hours, policies and
general "what is this treatment" questions yourself, but if you're not sure,
hand it over.
```

## stage: business_number

```
41 123 456 789
```

## stage: knowledge_prompt

```
Yes, ready to confirm. I'll upload our policy sheet, the fee list and our
FAQ next.
```
