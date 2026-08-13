"""Plain-English names for the disclosure standards metrics feed.

The raw tags on the metric set are filing shorthand — "SOX 404",
"CSRD ESRS E1", "SASB-RT-CH". They are precise, and they are meaningless
to anyone who does not already work in disclosure. A chart axis reading
"GRI 305" tells a client nothing; "Emissions · GRI 305" tells them what
it is and lets their compliance lead recognise the code.

Each entry carries three things: what the standard is *about* in ordinary
words, who issues it, and one line on what it actually requires.
"""
from __future__ import annotations

# code -> (plain topic, issuing body, what it asks for)
FRAMEWORK_LABELS: dict[str, tuple[str, str, str]] = {
    "BRSR Principal 5": (
        "Human Rights", "SEBI (India)",
        "How the company respects human rights across its workforce and "
        "value chain."),
    "BRSR Principal 6": (
        "Environment", "SEBI (India)",
        "Environmental impact — emissions, energy, water, waste and "
        "biodiversity."),
    "CSRD ESRS E1": (
        "Climate Change", "European Union",
        "Transition plans, emissions across all scopes, and energy use."),
    "CSRD ESRS S1": (
        "Own Workforce", "European Union",
        "Working conditions, pay, diversity and training for employees."),
    "CSRD ESRS G1": (
        "Business Conduct", "European Union",
        "Ethics, anti-corruption, whistleblowing and supplier relations."),
    "CSRD-DM": (
        "Double Materiality", "European Union",
        "Assessing both how sustainability affects the company and how the "
        "company affects the world."),
    "GRI 302": (
        "Energy", "Global Reporting Initiative",
        "Energy consumed, energy intensity and reductions achieved."),
    "GRI 303": (
        "Water & Effluents", "Global Reporting Initiative",
        "Water withdrawn, consumed and discharged, including in stressed "
        "areas."),
    "GRI 305": (
        "Emissions", "Global Reporting Initiative",
        "Greenhouse gases by scope, plus air pollutants."),
    "GRI 306": (
        "Waste", "Global Reporting Initiative",
        "Waste generated, diverted from disposal, and sent to disposal."),
    "GRI 403": (
        "Health & Safety", "Global Reporting Initiative",
        "Injuries, occupational illness and the safety management system."),
    "GRI 405": (
        "Diversity & Inclusion", "Global Reporting Initiative",
        "Composition of the workforce and governance bodies, and pay "
        "equality."),
    "IFRS S2": (
        "Climate Disclosures", "ISSB (global baseline)",
        "Climate risks and opportunities in financial reporting terms."),
    "SASB-RT-CH": (
        "Chemicals Industry Standard", "SASB / ISSB",
        "The sustainability topics judged financially material to chemicals "
        "companies."),
    "SEC-CLIM SX-14": (
        "Climate Disclosure Rule", "US SEC",
        "Climate risk and greenhouse-gas disclosure for US-listed filers."),
    "SOX 302": (
        "Management Sign-Off on Reports", "US Sarbanes-Oxley Act",
        "Executives personally certify that reported figures are accurate."),
    "SOX 404": (
        "Internal Financial Controls", "US Sarbanes-Oxley Act",
        "Proving the controls behind reported numbers actually work."),
    "TCFD-Metrics": (
        "Climate Metrics & Targets", "TCFD",
        "The metrics and targets used to manage climate risk."),
}


def friendly(code: str, *, with_code: bool = True) -> str:
    """Return a readable label for a framework tag.

    Unknown codes pass through unchanged rather than being hidden — a tag
    we have not translated yet should still appear on the chart.
    """
    code = str(code or "").strip()
    entry = FRAMEWORK_LABELS.get(code)
    if not entry:
        return code
    topic = entry[0]
    return f"{topic} · {code}" if with_code else topic


def issuer(code: str) -> str:
    """Who publishes the standard, for tooltips and captions."""
    entry = FRAMEWORK_LABELS.get(str(code or "").strip())
    return entry[1] if entry else ""


def describes(code: str) -> str:
    """One line on what the standard actually asks for."""
    entry = FRAMEWORK_LABELS.get(str(code or "").strip())
    return entry[2] if entry else ""


def glossary_pairs(codes) -> list[tuple[str, str]]:
    """(term, definition) pairs for the ui.glossary() component."""
    pairs = []
    for code in codes:
        entry = FRAMEWORK_LABELS.get(str(code or "").strip())
        if not entry:
            continue
        topic, body, detail = entry
        pairs.append((f"{topic} · {code}", f"{body}. {detail}"))
    return pairs
