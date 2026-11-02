"""Print geometry for one page: the PDF page boxes and the crop mark segments, in millimetres and in points.

Pure maths from PrintConfig; no WeasyPrint import. Coordinates have their origin at the lower-left corner of the trim
box, y upwards, which is how WeasyPrint writes its pages: the TrimBox is [0, 0, w, h] and the BleedBox and MediaBox
start at negative coordinates.
"""
PT_PER_MM = 72 / 25.4


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_MM
