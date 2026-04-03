"""
tneb.py — TNEB billing calculation logic.

TNEB Domestic Tariff (per 2-month billing cycle):
  0   – 100  units : FREE
  101 – 200  units : ₹1.50 / unit
  201 – 500  units : ₹3.00 / unit
  501+       units : ₹5.00 / unit

Fixed charge: ₹30 (added only if bill > ₹0)
"""

import datetime
import calendar

FREE_LIMIT   = 100
FIXED_CHARGE = 30.0

SLABS = [
    (100,          0.00),
    (200,          1.50),
    (500,          3.00),
    (float('inf'), 5.00),
]


def calculate_bill(units: float) -> dict:
    """Apply TNEB slab rates. Returns full bill breakdown dict."""
    units   = max(0, float(units))
    is_free = units <= FREE_LIMIT

    breakdown    = []
    remaining    = units
    total_charge = 0.0
    prev_limit   = 0

    for limit, rate in SLABS:
        if remaining <= 0:
            break
        slab_cap = min(limit - prev_limit, remaining)
        charge   = slab_cap * rate
        breakdown.append({
            'slab'         : f"{prev_limit + 1}–{'∞' if limit == float('inf') else int(limit)}",
            'units_in_slab': round(slab_cap, 2),
            'rate'         : rate,
            'charge'       : round(charge, 2),
        })
        total_charge += charge
        remaining    -= slab_cap
        prev_limit    = limit

    fixed = FIXED_CHARGE if total_charge > 0 else 0.0
    total = round(total_charge + fixed, 2)

    if units <= FREE_LIMIT:
        left  = FREE_LIMIT - units
        alert = f"⚠️ Only {left:.0f} free units left!" if left <= 20 else f"✅ Within free slab — {left:.0f} units remaining."
        tip   = "Keep under 100 units to pay ₹0 this cycle."
    elif units <= 200:
        alert = f"💡 Crossed free slab by {units - FREE_LIMIT:.0f} units. Bill: ₹{total}."
        tip   = f"Reduce by {units - FREE_LIMIT:.0f} units next cycle to avoid charges."
    elif units <= 500:
        alert = f"🔴 Moderate-high usage ({units:.0f} units). Bill: ₹{total}."
        tip   = "Reduce AC usage and shift heavy loads to off-peak hours."
    else:
        alert = f"🚨 Very high usage ({units:.0f} units). Bill: ₹{total}. Immediate action needed."
        tip   = "Check for continuously running appliances. Consider an energy audit."

    return {
        'units'         : round(units, 2),
        'is_free'       : is_free,
        'amount'        : round(total_charge, 2),
        'fixed_charge'  : fixed,
        'total'         : total,
        'slab_breakdown': breakdown,
        'alert'         : alert,
        'savings_tip'   : tip,
    }


def units_consumed(prev_reading, curr_reading) -> float:
    """Calculate units from two consecutive meter readings."""
    if prev_reading is None or curr_reading is None:
        return 0
    return max(0, float(curr_reading) - float(prev_reading))


def predict_bill_from_readings(readings: list) -> dict:
    """Given list of reading docs sorted oldest→newest, predict bill."""
    if len(readings) < 2:
        return None
    units = units_consumed(readings[0]['reading_value'], readings[-1]['reading_value'])
    return calculate_bill(units)


def get_current_cycle_dates():
    """Returns (cycle_start, cycle_end) date objects for the current TNEB 2-month cycle."""
    today       = datetime.date.today()
    month       = today.month
    start_month = month if month % 2 == 1 else month - 1
    cycle_start = today.replace(month=start_month, day=1)
    end_month   = start_month + 1
    end_year    = today.year
    if end_month > 12:
        end_month = 1
        end_year += 1
    last_day  = calendar.monthrange(end_year, end_month)[1]
    cycle_end = datetime.date(end_year, end_month, last_day)
    return cycle_start, cycle_end


def days_left_in_cycle() -> int:
    _, cycle_end = get_current_cycle_dates()
    return max(0, (cycle_end - datetime.date.today()).days)


def daily_budget(target_units: float = FREE_LIMIT) -> float:
    cycle_start, cycle_end = get_current_cycle_dates()
    total_days = (cycle_end - cycle_start).days + 1
    return round(target_units / total_days, 2)


def get_recommendations(units_so_far: float, days_elapsed: int, total_days: int = 61) -> list:
    """Personalized tips based on current consumption pace."""
    tips = []
    projected = round((units_so_far / days_elapsed * total_days) if days_elapsed > 0 else 0, 1)

    if projected <= FREE_LIMIT:
        tips.append({'icon': '✅', 'severity': 'good',  'title': 'On track for free slab',
                     'body': f'Projected: ~{projected} units — within the 100-unit free limit.'})
    elif projected <= 200:
        tips.append({'icon': '⚠️', 'severity': 'warn',  'title': 'Slightly over free slab',
                     'body': f'Projected: {projected} units. Reduce by {projected-FREE_LIMIT:.0f} units.'})
    else:
        tips.append({'icon': '🔴', 'severity': 'danger','title': 'High consumption pace',
                     'body': f'Projected: {projected} units. Est. bill: ₹{calculate_bill(projected)["total"]}.'})

    tips += [
        {'icon':'❄️','severity':'info','title':'AC efficiency',
         'body':'Set AC to 24–26°C. Each degree lower increases consumption by ~6%.'},
        {'icon':'🌡️','severity':'info','title':'Water heater timer',
         'body':'2 hours/day is enough for most households. Use a timer switch.'},
        {'icon':'💡','severity':'info','title':'Switch to LED',
         'body':'LED bulbs use 80% less energy than incandescent bulbs.'},
        {'icon':'🔌','severity':'info','title':'Standby power',
         'body':'Unplug chargers and TVs when not in use — standby can be 5–10% of your bill.'},
        {'icon':'🌙','severity':'info','title':'Off-peak scheduling',
         'body':'Run washing machine after 10 PM when load on the grid is lower.'},
    ]
    return tips
