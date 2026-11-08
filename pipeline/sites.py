"""Sites the pipeline knows about, with their bbox and the EIA series used as ground truth.

Cushing is a clean test: one hub, tank-farm stocks and tank working capacity published for it alone.
Gulf Coast sites are only a loose check: EIA publishes PADD 3 as a whole (refinery tanks, tank farms,
salt caverns, pipeline fill), and Gulf Coast tanks also hold refined products and chemicals.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    name: str
    bbox: tuple[float, float, float, float]  # south, west, north, east
    eia_stocks: str                          # EIA weekly series id
    capacity_sheet: str                      # sheet in EIA crudeoilstorage.xlsx
    capacity_row: str                        # working capacity row in that sheet

    @property
    def bbox_wsen(self) -> list[float]:
        s, w, n, e = self.bbox
        return [w, s, e, n]


PADD3 = dict(eia_stocks="WCESTP31", capacity_sheet="PADD 3",
             capacity_row="Refinery and Tank and Underground Working Storage Capacity")

SITES = {
    "cushing": Site("cushing", (35.90, -96.85, 36.02, -96.68), "W_EPC0_SAX_YCUOK_MBBL",
                    "Cushing", "Tank Working Storage Capacity"),
    "houston": Site("houston", (29.68, -95.30, 29.78, -95.05), **PADD3),
    "corpus_christi": Site("corpus_christi", (27.78, -97.55, 27.86, -97.38), **PADD3),
}
