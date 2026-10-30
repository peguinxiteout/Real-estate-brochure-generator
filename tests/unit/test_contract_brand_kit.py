import pytest
from pydantic import ValidationError

from brochure.contracts.brand import BrandKit


def brand_data(**overrides):
    data = {
        "company_name": "Kestrel Urbanscapes",
        "logo_path": "logo.svg",
        "colors": [
            {"name": "primary", "hex": "#1F3A5F", "cmyk": [100, 80, 30, 25]},
            {"name": "accent", "hex": "#C8A24A"},
        ],
        "fonts": {"heading": "Playfair Display", "body": "Inter"},
        "about_text": "Kestrel Urbanscapes builds homes in Pune.",
        "contact": {
            "phone": "+91 20 5555 0100",
            "email": "sales@example.com",
            "website": "https://example.com",
            "address": "1 Sample Road, Pune",
        },
        "disclaimer": "Artist impression. Subject to approvals.",
    }
    data.update(overrides)
    return data


def test_valid_brand_kit_parses():
    kit = BrandKit.model_validate(brand_data())
    assert kit.colors[0].hex == "#1F3A5F"
    assert kit.colors[1].cmyk is None
    assert kit.fonts.heading == "Playfair Display"
    assert kit.contact.email == "sales@example.com"


@pytest.mark.parametrize("bad_hex", ["1F3A5F", "#1F3A5", "#GGGGGG", "navy"])
def test_color_hex_must_be_six_digit_hash_form(bad_hex):
    bad = [{"name": "primary", "hex": bad_hex}]
    with pytest.raises(ValidationError):
        BrandKit.model_validate(brand_data(colors=bad))
