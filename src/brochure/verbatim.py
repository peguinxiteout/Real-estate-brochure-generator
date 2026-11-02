"""The text slots that code fills word for word from the project facts and the brand kit. The Copywriter never writes them."""
from brochure.contracts.brand import BrandKit
from brochure.contracts.project import ProjectFacts

VERBATIM_SLOTS: tuple[str, ...] = (
    "cover_rera_line", "rera_number", "location_address", "location_landmarks", "amenities_list",
    "config_table", "specs_list", "about_text", "contact_block", "disclaimer",
)


def verbatim_copy(facts: ProjectFacts, brand: BrandKit) -> dict[str, str]:
    """slot id -> text for every verbatim slot. Legal and contact text is never reworded."""
    contact = brand.contact
    lines = "\n".join
    return {
        "cover_rera_line": f"RERA No. {facts.rera_number}",
        "rera_number": facts.rera_number,
        "location_address": facts.location,
        "location_landmarks": lines(f"{m.name}, {m.distance_km:g} km" for m in facts.landmarks),
        "amenities_list": lines(facts.amenities),
        "config_table": lines(f"{c.label}: {c.carpet_area_sqft:g} sq ft carpet" for c in facts.configurations),
        "specs_list": lines(f"{x.category}: {x.detail}" for x in facts.specifications),
        "about_text": brand.about_text,
        "contact_block": lines(v for v in (contact.phone, contact.email, contact.website, contact.address) if v),
        "disclaimer": brand.disclaimer,
    }
