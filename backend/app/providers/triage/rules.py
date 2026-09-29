"""
app/providers/triage/rules.py
─────────────────────────────
Rule-based deterministic keyword triage provider.

Always available, zero external dependencies, never fails.
Serves as:
  1. Primary rule provider (`triaged_by = "rules"`)
  2. Fallback provider when LLM or Ollama fails (`triaged_by = "rules:fallback"`)
"""

import re

from app.core.enums import ComplaintCategory, ComplaintPriority
from app.providers.triage.base import TriageResult


class RuleBasedTriage:
    """
    Deterministic rule-based triage classifier based on keyword scoring.
    """

    def __init__(self, name: str = "rules") -> None:
        self.name = name

    def triage(self, text: str, location: str) -> TriageResult:
        lowered = text.lower()

        # ── Category Detection ────────────────────────────────────────────
        category = self._detect_category(lowered)

        # ── Priority Detection ────────────────────────────────────────────
        priority = self._detect_priority(lowered, category)

        # ── Summary Extraction ────────────────────────────────────────────
        summary = self._generate_summary(text)

        # High confidence for explicit matches, lower for generic fallback
        confidence = 0.9 if category != ComplaintCategory.other else 0.6

        return TriageResult(
            category=category,
            priority=priority,
            summary=summary,
            confidence=confidence,
        )

    def _detect_category(self, text: str) -> ComplaintCategory:
        scores = {
            ComplaintCategory.sanitation: [
                "sanitation", "sewage", "raw sewage", "sewage overflow",
                "garbage", "trash", "waste", "rubbish", "dump",
                "dumping", "fly-tip", "bin", "bins", "toilet", "toilets",
                "stench", "odor", "smell", "rats"
            ],
            ComplaintCategory.water: [
                "water", "water main", "pipe", "pipes", "burst", "flood",
                "flooding", "flooded", "leak", "leaking", "gushing", "tap",
                "taps", "drinking water", "drain", "drainage", "irrigation",
                "water meter", "supply", "gully", "gulley"
            ],
            ComplaintCategory.electricity: [
                "electricity", "power", "wire", "wires", "sparking", "spark",
                "live wire", "transformer", "substation", "voltage", "outage",
                "blackout", "shock", "electrocution", "cable", "electrical"
            ],
            ComplaintCategory.roads: [
                "road", "pothole", "potholes", "sinkhole", "highway", "asphalt",
                "pavement", "paving", "crossing", "marking", "markings", "speed bump",
                "traffic", "carriageway", "footpath", "sidewalk", "slab"
            ],
            ComplaintCategory.streetlights: [
                "streetlight", "street light", "streetlights", "lamp", "lamps",
                "lighting", "bulb", "dark", "darkness", "flicker", "flickering",
                "unlit", "string lights"
            ],
        }

        best_category = ComplaintCategory.other
        highest_score = 0

        for cat, keywords in scores.items():
            count = sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", text))
            if count > highest_score:
                highest_score = count
                best_category = cat

        return best_category

    def _detect_priority(self, text: str, category: ComplaintCategory) -> ComplaintPriority:
        high_urgent_keywords = [
            "danger", "emergency", "urgent", "hazard", "fire", "burning",
            "live wire", "exposed wire", "electrocution", "sparking",
            "burst", "flooding", "flooded", "gushing", "high pressure",
            "broken water main", "contamination", "raw sewage", "sewage overflow",
            "overflow", "severe", "hospital",
            "sinkhole", "injury", "injured", "accident", "fatal", "collapse",
            "children", "school", "clinic", "elderly"
        ]

        if any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in high_urgent_keywords):
            return ComplaintPriority.high

        low_priority_keywords = [
            "bench", "fountain", "noticeboard", "decorative", "string light",
            "graffiti", "paint", "subsided", "cosmetic", "park"
        ]

        if category in {ComplaintCategory.streetlights, ComplaintCategory.other}:
            if any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in low_priority_keywords):
                return ComplaintPriority.low

        return ComplaintPriority.normal

    def _generate_summary(self, text: str) -> str:
        clean = " ".join(text.split()).strip()
        first_sentence = clean.split(".")[0].strip()
        if len(first_sentence) > 137:
            return first_sentence[:137] + "..."
        if len(first_sentence) < 15 and len(clean) > 15:
            return clean[:137] + "..." if len(clean) > 140 else clean
        return first_sentence
