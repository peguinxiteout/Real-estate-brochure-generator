"""Brand kit: the developer's identity."""
from pydantic import Field

from brochure.contracts.base import ContractModel


class BrandColor(ContractModel):
    name: str
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    cmyk: tuple[int, int, int, int] | None = None


class BrandFonts(ContractModel):
    heading: str
    body: str


class Contact(ContractModel):
    phone: str = ""
    email: str = ""
    website: str = ""
    address: str = ""


class BrandKit(ContractModel):
    company_name: str
    logo_path: str
    colors: list[BrandColor]
    fonts: BrandFonts
    about_text: str
    contact: Contact
    disclaimer: str
