"""
Dynamic availability for Wellness Partners providers.
Slots are generated relative to today, starting tomorrow, up to 60 days out.
This ensures availability always looks current regardless of when the app runs.
"""

from datetime import date, datetime, timedelta

START_DAYS = 1   # slots start tomorrow
END_DAYS   = 60  # slots go up to 60 days out

DOCTOR_NAMES = {
    "dr_sarah_kim":    "Dr. Sarah Kim",
    "dr_james_chen":   "Dr. James Chen",
    "dr_maria_santos": "Dr. Maria Santos",
    "dr_david_okafor": "Dr. David Okafor",
    "dr_emily_larson": "Dr. Emily Larson",
}


def generate_slots(weekday: int, hour: int, minute: int) -> list[dict]:
    """
    Generate all occurrences of a given weekday/time within the booking window.

    Args:
        weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
        hour:    24-hour clock
        minute:  minutes
    """
    today = date.today()
    start = today + timedelta(days=START_DAYS)
    end   = today + timedelta(days=END_DAYS)

    # Fast-forward to the first occurrence of `weekday` on or after `start`
    days_ahead = (weekday - start.weekday()) % 7
    current = start + timedelta(days=days_ahead)

    slots = []
    while current <= end:
        slots.append({
            "datetime":  f"{current.strftime('%Y-%m-%d')} {hour:02d}:{minute:02d}",
            "available": True,
        })
        current += timedelta(weeks=1)

    return slots


def _build_availability() -> dict[str, list[dict]]:
    return {
        "dr_sarah_kim": (               # Orthopedics — bones, joints, spine
            generate_slots(1,  9,  0) + # Tuesdays   9:00 AM
            generate_slots(4, 14,  0)   # Fridays    2:00 PM
        ),
        "dr_james_chen": (              # Cardiology — heart, blood pressure
            generate_slots(0,  8, 30) + # Mondays    8:30 AM
            generate_slots(3, 13,  0)   # Thursdays  1:00 PM
        ),
        "dr_maria_santos": (            # Gastroenterology — stomach, digestion
            generate_slots(1, 10,  0) + # Tuesdays  10:00 AM
            generate_slots(2, 15, 30)   # Wednesdays 3:30 PM
        ),
        "dr_david_okafor": (            # Dermatology — skin, rashes, acne
            generate_slots(0, 11,  0) + # Mondays   11:00 AM
            generate_slots(4,  9,  0)   # Fridays    9:00 AM
        ),
        "dr_emily_larson": (            # General Practice — checkups, physicals
            generate_slots(1,  9,  0) + # Tuesdays   9:00 AM
            generate_slots(2, 14,  0) + # Wednesdays 2:00 PM
            generate_slots(4, 10, 30)   # Fridays   10:30 AM
        ),
    }


# Build once at startup — slots are stable for the lifetime of the process
AVAILABILITY: dict[str, list[dict]] = _build_availability()


# ── Tool functions called by Vapi webhook ──────────────────────────────────────

def check_availability(provider: str, preference: str | None = None) -> dict:
    """
    Return available slots for a provider, optionally filtered by preference.

    Args:
        provider:   e.g. "dr_sarah_kim"
        preference: optional — "tuesday", "morning", "afternoon", etc.
    """
    slots = AVAILABILITY.get(provider)
    if slots is None:
        return {"error": f"Unknown provider: {provider}"}

    available = [s for s in slots if s["available"]]

    if preference:
        pref = preference.lower().strip()
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }
        if pref in day_map:
            target = day_map[pref]
            available = [
                s for s in available
                if datetime.strptime(s["datetime"], "%Y-%m-%d %H:%M").weekday() == target
            ]
        elif "morning" in pref:
            available = [
                s for s in available
                if datetime.strptime(s["datetime"], "%Y-%m-%d %H:%M").hour < 12
            ]
        elif "afternoon" in pref:
            available = [
                s for s in available
                if datetime.strptime(s["datetime"], "%Y-%m-%d %H:%M").hour >= 12
            ]

    if not available:
        return {
            "provider": DOCTOR_NAMES.get(provider, provider),
            "slots":    [],
            "message":  "No slots match that preference. Try a different day or time.",
        }

    formatted = []
    for s in available[:4]:
        dt = datetime.strptime(s["datetime"], "%Y-%m-%d %H:%M")
        formatted.append({
            "datetime": s["datetime"],
            "display":  dt.strftime("%A, %B %d at %I:%M %p").replace(" 0", " "),
        })

    return {
        "provider": DOCTOR_NAMES.get(provider, provider),
        "slots":    formatted,
    }


def book_appointment(provider: str, datetime_str: str, patient_name: str) -> dict:
    """
    Book a slot. Marks it unavailable to prevent double-booking.

    Args:
        provider:      e.g. "dr_sarah_kim"
        datetime_str:  "YYYY-MM-DD HH:MM"
        patient_name:  full name of the patient
    """
    slots = AVAILABILITY.get(provider)
    if slots is None:
        return {"success": False, "error": f"Unknown provider: {provider}"}

    for slot in slots:
        if slot["datetime"] == datetime_str:
            if not slot["available"]:
                return {"success": False, "error": "That slot is no longer available. Please choose another."}
            slot["available"] = False
            dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            return {
                "success":         True,
                "confirmation_id": f"WP-{abs(hash(patient_name + datetime_str)) % 100000:05d}",
                "provider":        DOCTOR_NAMES.get(provider, provider),
                "patient":         patient_name,
                "datetime":        datetime_str,
                "display":         dt.strftime("%A, %B %d at %I:%M %p").replace(" 0", " "),
            }

    return {"success": False, "error": f"Slot {datetime_str} not found for {provider}."}