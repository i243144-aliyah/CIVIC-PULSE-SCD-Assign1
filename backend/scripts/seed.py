"""
scripts/seed.py
────────────────
Idempotent seed script that loads 30 realistic complaints into PostgreSQL.

Idempotency guarantee
─────────────────────
Each complaint has a deterministic, stable UUID derived from its seed index
(uuid.uuid5 + a namespace UUID).  On every run the script checks whether a
row with that UUID already exists:
  - If it exists   → skip (no INSERT, no UPDATE)
  - If it doesn't  → insert it

Running this script twice (or N times) results in exactly the same 30 rows.

Usage
─────
    # From project root (with DATABASE_URL / DATABASE_SYNC_URL in .env):
    python scripts/seed.py

    # Or via the virtual env:
    .venv/bin/python scripts/seed.py

Requirements
─────────────
psycopg2-binary (for synchronous inserts; avoids asyncio boilerplate in a
one-shot script).  Alternatively, set USE_SYNC_URL=true and point
DATABASE_SYNC_URL to a psycopg2-compatible DSN.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

# ── Make `app` importable when running from project root ─────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from dotenv import load_dotenv
except ImportError:
    # The seed script can still run when python-dotenv isn't installed.
    def load_dotenv() -> bool:
        return False


load_dotenv()


# ── Seed namespace UUID (stable across runs) ──────────────────────────────────
# Any fixed UUID can serve as the namespace; this one is project-specific.
_SEED_NAMESPACE = uuid.UUID("a3b4c5d6-e7f8-4a9b-8c0d-1e2f3a4b5c6d")


def _seed_uuid(index: int) -> uuid.UUID:
    """Derive a stable, deterministic UUID for seed row `index`."""
    return uuid.uuid5(_SEED_NAMESPACE, f"civicpulse-seed-complaint-{index:04d}")


# ── Seed data ─────────────────────────────────────────────────────────────────
# 30 realistic complaints distributed across all 6 categories.
# Categories: water(6), electricity(5), sanitation(5), roads(6), streetlights(5), other(3)
SEED_COMPLAINTS: list[dict] = [
    # ── WATER (6) ─────────────────────────────────────────────────────────
    {
        "index": 1,
        "text": (
            "There is a burst water main on Oak Street flooding three front gardens. "
            "Water has been running since yesterday morning and the pressure in our "
            "homes has dropped significantly. Residents on this block urgently need "
            "this repaired."
        ),
        "location": "Oak Street, Block 3, near junction with Elm Avenue",
        "reporter_contact": "sarah.okonkwo@email.com",
        "category": "water",
        "priority": "high",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 12,
        "ai_summary": "Burst water main flooding Oak Street; significant pressure loss reported.",
    },
    {
        "index": 2,
        "text": (
            "The water supply to our entire apartment block has been cut off for "
            "48 hours. We have received no notification from the water authority. "
            "There are elderly residents and families with young children who are "
            "severely affected."
        ),
        "location": "Sunrise Apartments, Block C, Westfield Road",
        "reporter_contact": "james.mutua@gmail.com",
        "category": "water",
        "priority": "high",
        "status": "in_progress",
        "triaged_by": "llm:groq",
        "triage_latency_ms": 842,
        "ai_summary": "48-hour water outage at Sunrise Apartments; elderly and children affected.",
    },
    {
        "index": 3,
        "text": (
            "Tap water coming out of our taps has a strong brown discolouration and "
            "smells like rust or sewage. Multiple neighbours on the street have "
            "confirmed the same issue. We are afraid to use it for drinking or cooking."
        ),
        "location": "14–28 Magnolia Drive, Northgate Estate",
        "reporter_contact": None,
        "category": "water",
        "priority": "high",
        "status": "open",
        "triaged_by": "llm:ollama",
        "triage_latency_ms": 3210,
        "ai_summary": "Brown discoloured tap water with sewage smell reported on Magnolia Drive.",
    },
    {
        "index": 4,
        "text": (
            "A water meter in the pavement outside number 7 has been leaking for "
            "two weeks. It is wasting a significant amount of clean water and making "
            "the pavement slippery for pedestrians."
        ),
        "location": "7 Cedar Close, Riverside District",
        "reporter_contact": "linda.chen@outlook.com",
        "category": "water",
        "priority": "normal",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 8,
        "ai_summary": "Leaking water meter on Cedar Close causing pavement hazard for two weeks.",
    },
    {
        "index": 5,
        "text": (
            "The public water fountain in Jubilee Park has been broken for a month. "
            "During summer this fountain serves joggers and children playing in the "
            "park. A simple repair or replacement would greatly benefit the community."
        ),
        "location": "Jubilee Park, central plaza near the bandstand",
        "reporter_contact": None,
        "category": "water",
        "priority": "low",
        "status": "resolved",
        "triaged_by": "rules",
        "triage_latency_ms": 6,
        "ai_summary": (
            "Broken public fountain in Jubilee Park needs repair; "
            # Keep adjacent literals split for the configured line limit.
            "serves joggers and children."
        ),
    },
    {
        "index": 6,
        "text": (
            "Irrigation pipes running along the perimeter of the community allotments "
            "have sprung multiple leaks. Several plots are now waterlogged and crops "
            "are at risk. The groundskeeper reported it two weeks ago with no follow-up."
        ),
        "location": "Community Allotments, Greenfield Lane, Plot Rows A–D",
        "reporter_contact": "groundskeeper@allotments-gf.org",
        "category": "water",
        "priority": "normal",
        "status": "open",
        "triaged_by": "rules:fallback",
        "triage_latency_ms": 5,
        "ai_summary": (
            "Multiple irrigation pipe leaks waterlogging allotment plots "
            # Keep adjacent literals split for the configured line limit.
            "on Greenfield Lane."
        ),
    },
    # ── ELECTRICITY (5) ───────────────────────────────────────────────────
    {
        "index": 7,
        "text": (
            "An electricity pole on the corner of Maple Road and High Street has "
            "exposed live wires dangling at head height after last night's storm. "
            "The area has been cordoned off by a neighbour using traffic cones but "
            "this is an urgent safety risk."
        ),
        "location": "Corner of Maple Road and High Street",
        "reporter_contact": "tom.harrison@email.com",
        "category": "electricity",
        "priority": "high",
        "status": "in_progress",
        "triaged_by": "llm:groq",
        "triage_latency_ms": 917,
        "ai_summary": (
            "Dangling live wires at head height after storm on Maple Road; "
            # Keep adjacent literals split for the configured line limit.
            "urgent hazard."
        ),
    },
    {
        "index": 8,
        "text": (
            "Power has been intermittent in our street for three days. Each outage "
            "lasts between 30 minutes and 2 hours. Home appliances and refrigerators "
            "are being damaged. The local clinic on this block is also affected."
        ),
        "location": "Victoria Terrace, numbers 1 through 40",
        "reporter_contact": "victoria.terrace.residents@gmail.com",
        "category": "electricity",
        "priority": "high",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 9,
        "ai_summary": (
            "Three-day intermittent power outage on Victoria Terrace "
            # Keep adjacent literals split for the configured line limit.
            "affecting clinic and homes."
        ),
    },
    {
        "index": 9,
        "text": (
            "An electricity substation near the school has been sparking and making "
            "loud humming noises for the past two days. Parents are concerned about "
            "children's safety given the proximity to the school entrance."
        ),
        "location": "Substation adjacent to St. Mary's Primary School, Park Lane",
        "reporter_contact": "headteacher@stmarys-primary.edu",
        "category": "electricity",
        "priority": "high",
        "status": "open",
        "triaged_by": "llm:groq",
        "triage_latency_ms": 788,
        "ai_summary": (
            "Sparking substation near school entrance on Park Lane "
            # Keep adjacent literals split for the configured line limit.
            "poses child safety risk."
        ),
    },
    {
        "index": 10,
        "text": (
            "Street lights are powered by electricity and a transformer serving the "
            "Harbour View housing estate has been overloaded. This causes trips every "
            "evening between 6pm and 9pm leaving residents in darkness. A capacity "
            "upgrade is needed."
        ),
        "location": "Harbour View Estate, main distribution panel on Quayside Road",
        "reporter_contact": None,
        "category": "electricity",
        "priority": "normal",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 11,
        "ai_summary": "Overloaded transformer causes daily evening outages at Harbour View Estate.",
    },
    {
        "index": 11,
        "text": (
            "An electricity meter box on the external wall of the community centre "
            "has been damaged and is no longer weather-proof. Rain is entering the "
            "box. This is a potential shock risk to anyone touching it."
        ),
        "location": "Riverside Community Centre, 88 River Road",
        "reporter_contact": "admin@riversidecc.org",
        "category": "electricity",
        "priority": "normal",
        "status": "rejected",
        "triaged_by": "rules",
        "triage_latency_ms": 7,
        "ai_summary": (
            "Weather-damaged meter box at community centre poses shock "
            # Keep adjacent literals split for the configured line limit.
            "risk in wet conditions."
        ),
    },
    # ── SANITATION (5) ────────────────────────────────────────────────────
    {
        "index": 12,
        "text": (
            "Raw sewage is overflowing from a manhole cover in the middle of Birch "
            "Street. The overflow has reached the pavement and is flowing toward the "
            "school playground. The smell is overwhelming and there is a serious "
            "public health risk."
        ),
        "location": "Birch Street, outside number 22, near school junction",
        "reporter_contact": "birchstreet.residents@yahoo.com",
        "category": "sanitation",
        "priority": "high",
        "status": "in_progress",
        "triaged_by": "llm:groq",
        "triage_latency_ms": 1102,
        "ai_summary": (
            "Raw sewage overflow on Birch Street reaching school playground; "
            # Keep adjacent literals split for the configured line limit.
            "public health risk."
        ),
    },
    {
        "index": 13,
        "text": (
            "Public bins on the high street have not been emptied for 10 days. "
            "Rubbish is overflowing onto the pavement, attracting rats and foxes. "
            "Several businesses have complained that the litter is deterring customers."
        ),
        "location": "High Street, between Market Square and the Town Hall",
        "reporter_contact": "shopkeepersalliance@highstreet.biz",
        "category": "sanitation",
        "priority": "normal",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 10,
        "ai_summary": (
            "Overflowing bins on High Street for 10 days attracting pests "
            # Keep adjacent literals split for the configured line limit.
            "and deterring shoppers."
        ),
    },
    {
        "index": 14,
        "text": (
            "Illegal dumping has created a large fly-tip at the entrance to the "
            "nature reserve on Woodland Path. The dump includes old mattresses, "
            "construction rubble, and what appears to be chemical containers. "
            "Walkers and dog owners are exposed to this every day."
        ),
        "location": "Entrance to Greenwood Nature Reserve, Woodland Path",
        "reporter_contact": None,
        "category": "sanitation",
        "priority": "normal",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 9,
        "ai_summary": "Large illegal dump with chemicals at Greenwood Nature Reserve entrance.",
    },
    {
        "index": 15,
        "text": (
            "The public toilets in Central Market have been out of order for two "
            "weeks. Traders and shoppers, including people with disabilities and "
            "elderly visitors, have no accessible facilities available."
        ),
        "location": "Central Market, Block B, toilet block near the east entrance",
        "reporter_contact": "centralmarket.manager@city.gov",
        "category": "sanitation",
        "priority": "normal",
        "status": "resolved",
        "triaged_by": "llm:ollama",
        "triage_latency_ms": 4561,
        "ai_summary": (
            "Central Market toilets out of order for 2 weeks; no accessible "
            # Keep adjacent literals split for the configured line limit.
            "facilities for disabled."
        ),
    },
    {
        "index": 16,
        "text": (
            "Drainage gullies along the pedestrian underpass on Station Road are "
            "completely blocked causing pooling water. The underpass floods even in "
            "light rain and becomes unusable for pedestrians and cyclists."
        ),
        "location": "Station Road pedestrian underpass, south entrance",
        "reporter_contact": "cycling.club@stationroad.net",
        "category": "sanitation",
        "priority": "low",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 8,
        "ai_summary": (
            "Blocked drainage causing flooding in Station Road underpass; "
            # Keep adjacent literals split for the configured line limit.
            "impassable in rain."
        ),
    },
    # ── ROADS (6) ─────────────────────────────────────────────────────────
    {
        "index": 17,
        "text": (
            "A deep pothole on the dual carriageway approach to the bypass has "
            "already caused two tyre blow-outs today that I witnessed. The pothole "
            "is approximately 40cm wide and 10cm deep. Traffic is heavy and at speed "
            "here making this extremely dangerous."
        ),
        "location": "A40 Westbound carriageway, 200m before the bypass junction",
        "reporter_contact": "highway.reporter@email.com",
        "category": "roads",
        "priority": "high",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 15,
        "ai_summary": (
            "Deep pothole on A40 bypass approach causing tyre blow-outs; "
            # Keep adjacent literals split for the configured line limit.
            "high-speed traffic risk."
        ),
    },
    {
        "index": 18,
        "text": (
            "Part of the road surface on Fountain Square has collapsed creating a "
            "sinkhole approximately one metre in diameter. A delivery van almost "
            "fell into it this morning. The square is a busy pedestrian and vehicle "
            "area. The hole needs immediate barriers and urgent repair."
        ),
        "location": "Fountain Square, in front of the old post office",
        "reporter_contact": None,
        "category": "roads",
        "priority": "high",
        "status": "in_progress",
        "triaged_by": "llm:groq",
        "triage_latency_ms": 956,
        "ai_summary": (
            "One-metre sinkhole on Fountain Square; delivery van near-miss; "
            # Keep adjacent literals split for the configured line limit.
            "urgent barriers needed."
        ),
    },
    {
        "index": 19,
        "text": (
            "Road markings on the pedestrian crossing outside the primary school "
            "have completely faded. Drivers are not yielding to children crossing "
            "and there have been several near-misses at the school run times. "
            "Repainting is urgently needed."
        ),
        "location": "School Road crossing, outside Greenhill Primary School",
        "reporter_contact": "parentcouncil@greenhillprimary.sch",
        "category": "roads",
        "priority": "high",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 11,
        "ai_summary": (
            "Faded pedestrian crossing markings near primary school; "
            # Keep adjacent literals split for the configured line limit.
            "near-misses at school run."
        ),
    },
    {
        "index": 20,
        "text": (
            "The speed bumps on Orchard Lane have subsided significantly. They are "
            "now almost flat and provide no traffic calming. Speeding has returned "
            "to this residential street that was previously calmed by these measures."
        ),
        "location": "Orchard Lane, between the roundabout and the post box",
        "reporter_contact": "orchardlane.residents@community.net",
        "category": "roads",
        "priority": "normal",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 7,
        "ai_summary": (
            "Subsided speed bumps on Orchard Lane no longer effective; "
            # Keep adjacent literals split for the configured line limit.
            "speeding has returned."
        ),
    },
    {
        "index": 21,
        "text": (
            "Paving slabs on the main pedestrian route from the bus terminus to the "
            "library have lifted and cracked. Several elderly residents have tripped. "
            "One person fell and injured their wrist last week. A safety repair is "
            "overdue."
        ),
        "location": "Library Walk, between Bus Terminal Gate 3 and the library entrance",
        "reporter_contact": "library.manager@city.gov",
        "category": "roads",
        "priority": "normal",
        "status": "open",
        "triaged_by": "llm:groq",
        "triage_latency_ms": 1034,
        "ai_summary": (
            "Lifted paving slabs on Library Walk causing trips; one wrist "
            # Keep adjacent literals split for the configured line limit.
            "injury reported last week."
        ),
    },
    {
        "index": 22,
        "text": (
            "A large pothole has appeared outside the entrance to Whitmore Court "
            "residents' car park. It is causing vehicles to scrape when entering "
            "and exiting. Residents have complained for three months with no repair."
        ),
        "location": "Whitmore Court car park entrance, Beacon Hill Road",
        "reporter_contact": "whitmore.residents@email.com",
        "category": "roads",
        "priority": "low",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 9,
        "ai_summary": (
            "Pothole at Whitmore Court car park entrance scraping vehicles "
            # Keep adjacent literals split for the configured line limit.
            "for three months."
        ),
    },
    # ── STREETLIGHTS (5) ──────────────────────────────────────────────────
    {
        "index": 23,
        "text": (
            "All six street lights on Pine Avenue have been out for five nights. "
            "The street is completely dark after sunset. Residents are worried about "
            "personal safety, especially the section adjacent to the alley that had "
            "a robbery last month."
        ),
        "location": "Pine Avenue, full length between numbers 1 and 60",
        "reporter_contact": "pine.ave.watch@neighborhood.org",
        "category": "streetlights",
        "priority": "normal",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 8,
        "ai_summary": (
            "All six streetlights on Pine Avenue out for 5 nights; safety "
            # Keep adjacent literals split for the configured line limit.
            "concern near crime alley."
        ),
    },
    {
        "index": 24,
        "text": (
            "The street light on the corner of Ash Road and the cycle path is "
            "flickering continuously throughout the night. This is causing distress "
            "to nearby residents, especially those with photosensitive epilepsy. "
            "A replacement lamp or ballast is needed."
        ),
        "location": "Corner of Ash Road and the Riverside Cycle Path",
        "reporter_contact": "ash.road.resident@gmail.com",
        "category": "streetlights",
        "priority": "normal",
        "status": "in_progress",
        "triaged_by": "rules",
        "triage_latency_ms": 6,
        "ai_summary": (
            "Flickering streetlight on Ash Road causing distress to "
            # Keep adjacent literals split for the configured line limit.
            "photosensitive residents."
        ),
    },
    {
        "index": 25,
        "text": (
            "Three street lights in the multi-storey car park on Mill Street have "
            "failed. The affected area is now unlit at night creating a safety "
            "concern for car park users. The management company is awaiting a council "
            "repair order."
        ),
        "location": "Mill Street Multi-Storey Car Park, Level 2, Section C",
        "reporter_contact": "parking.manager@millstreetcp.com",
        "category": "streetlights",
        "priority": "low",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 7,
        "ai_summary": (
            "Three streetlights failed on Level 2 of Mill Street car park; "
            # Keep adjacent literals split for the configured line limit.
            "area unlit at night."
        ),
    },
    {
        "index": 26,
        "text": (
            "A streetlight column on Harbour Road has been struck by a vehicle and "
            "is visibly leaning at a 45-degree angle. There is a risk of the pole "
            "falling into traffic or onto pedestrians. This should be treated as "
            "an urgent structural safety issue."
        ),
        "location": "Harbour Road, outside number 14, near the marina entrance",
        "reporter_contact": None,
        "category": "streetlights",
        "priority": "normal",
        "status": "open",
        "triaged_by": "llm:groq",
        "triage_latency_ms": 873,
        "ai_summary": (
            "Vehicle-struck streetlight column leaning 45° on Harbour Road; "
            # Keep adjacent literals split for the configured line limit.
            "collapse risk."
        ),
    },
    {
        "index": 27,
        "text": (
            "The decorative string lights above the pedestrianised shopping area "
            "on Market Street have failed in one section. While not safety-critical, "
            "the area looks neglected and it impacts the town centre's attractiveness "
            "for evening visitors."
        ),
        "location": "Market Street pedestrian zone, between the fountain and Costa Coffee",
        "reporter_contact": "bid@marketstreet-businessimprovement.org",
        "category": "streetlights",
        "priority": "low",
        "status": "resolved",
        "triaged_by": "rules",
        "triage_latency_ms": 5,
        "ai_summary": "Section of decorative lights failed on Market Street pedestrian zone.",
    },
    # ── OTHER (3) ─────────────────────────────────────────────────────────
    {
        "index": 28,
        "text": (
            "The park bench near the duck pond in Manor Park has been completely "
            "vandalised. The wooden slats have been broken off and there is graffiti "
            "on the metal frame. This is the only seating in this section of the "
            "park and is used heavily by elderly residents."
        ),
        "location": "Manor Park, bench adjacent to the duck pond, east side",
        "reporter_contact": "friendsofmanorpark@volunteers.org",
        "category": "other",
        "priority": "low",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 6,
        "ai_summary": (
            "Vandalised park bench near duck pond in Manor Park; only seating "
            # Keep adjacent literals split for the configured line limit.
            "for elderly visitors."
        ),
    },
    {
        "index": 29,
        "text": (
            "The noticeboard outside the community hall on Church Lane has been "
            "damaged by the recent storm. The glass cover is broken and pinned "
            "notices are exposed to weather. Local clubs and groups rely on this "
            "board to communicate with residents."
        ),
        "location": "Community Hall, 3 Church Lane, Eastfield",
        "reporter_contact": "communityhall.eastfield@gmail.com",
        "category": "other",
        "priority": "low",
        "status": "open",
        "triaged_by": "rules",
        "triage_latency_ms": 5,
        "ai_summary": "Storm-damaged noticeboard at Eastfield Community Hall; glass cover broken.",
    },
    {
        "index": 30,
        "text": (
            "A large overhanging branch from a council-maintained tree on Poplar "
            "Avenue has split after the high winds last night. The branch is hanging "
            "precariously over the pavement and could fall on pedestrians at any "
            "time. Emergency pruning is needed."
        ),
        "location": "Poplar Avenue, outside number 31, council tree near the bus stop",
        "reporter_contact": "poplaraveresidents@neighborhood.co.uk",
        "category": "other",
        "priority": "normal",
        "status": "in_progress",
        "triaged_by": "llm:groq",
        "triage_latency_ms": 791,
        "ai_summary": (
            "Overhanging split tree branch over pavement on Poplar Avenue; "
            # Keep adjacent literals split for the configured line limit.
            "imminent fall risk."
        ),
    },
]

assert len(SEED_COMPLAINTS) >= 30, f"Expected >= 30 complaints, got {len(SEED_COMPLAINTS)}"


# ── Category distribution summary (for documentation) ───────────────────────
_CATEGORY_COUNTS: dict[str, int] = {}
for _c in SEED_COMPLAINTS:
    _CATEGORY_COUNTS[_c["category"]] = _CATEGORY_COUNTS.get(_c["category"], 0) + 1


def _build_insert_row(complaint: dict, seed_id: uuid.UUID) -> dict:
    """Build a flat dict ready for INSERT matching the complaints table schema."""
    now = datetime.now(UTC)
    return {
        "id": str(seed_id),
        "text": complaint["text"].strip(),
        "location": complaint["location"],
        "reporter_contact": complaint.get("reporter_contact"),
        "category": complaint["category"],
        "priority": complaint["priority"],
        "status": complaint["status"],
        "ai_summary": complaint.get("ai_summary"),
        "triaged_by": complaint["triaged_by"],
        "triage_latency_ms": complaint["triage_latency_ms"],
        "created_at": now,
        "updated_at": now,
    }


def run_seed(database_url: str | None = None) -> None:
    """
    Execute the idempotent seed operation.

    Parameters
    ----------
    database_url : str | None
        Sync SQLAlchemy DSN.  If None, falls back to DATABASE_SYNC_URL
        then DATABASE_URL from the environment.
    """
    url = (
        database_url
        or os.environ.get("DATABASE_SYNC_URL")
        or os.environ.get("DATABASE_URL", "").replace("+asyncpg", "+psycopg2")
    )
    if not url:
        raise RuntimeError("No database URL found.  Set DATABASE_SYNC_URL in your .env file.")

    print("[seed] Connecting to database …")
    engine = create_engine(url, echo=False)

    inserted = 0
    skipped = 0

    with engine.begin() as conn:
        for complaint in SEED_COMPLAINTS:
            seed_id = _seed_uuid(complaint["index"])
            # Idempotency check: does this deterministic UUID already exist?
            exists = conn.execute(
                text("SELECT 1 FROM complaints WHERE id = :id"),
                {"id": str(seed_id)},
            ).fetchone()

            if exists:
                skipped += 1
                continue

            row = _build_insert_row(complaint, seed_id)
            conn.execute(
                text(
                    """
                    INSERT INTO complaints (
                        id, text, location, reporter_contact,
                        category, priority, status,
                        ai_summary, triaged_by, triage_latency_ms,
                        created_at, updated_at
                    ) VALUES (
                        :id, :text, :location, :reporter_contact,
                        :category, :priority, :status,
                        :ai_summary, :triaged_by, :triage_latency_ms,
                        :created_at, :updated_at
                    )
                    """
                ),
                row,
            )
            inserted += 1

    print(
        f"[seed] Done. "
        f"Inserted: {inserted}, Skipped (already existed): {skipped}, "
        f"Total seed rows: {len(SEED_COMPLAINTS)}"
    )
    print("[seed] Category distribution:")
    for cat, count in sorted(_CATEGORY_COUNTS.items()):
        print(f"         {cat:<14} {count} complaints")


if __name__ == "__main__":
    run_seed()
