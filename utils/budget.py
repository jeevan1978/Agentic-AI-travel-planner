"""Authoritative arithmetic. Missing amounts never become estimated prices."""
import re
from decimal import Decimal, InvalidOperation


def parse_budget(value):
    text = str(value).strip().replace(',', '').replace('₹', '')
    text = re.sub(r'\s*INR\s*$', '', text, flags=re.I).strip()
    try:
        amount = Decimal(text or '0')
    except InvalidOperation:
        raise ValueError('Budget must be a nonnegative INR amount')
    if not amount.is_finite() or amount < 0:
        raise ValueError('Budget must be a nonnegative INR amount')
    return float(amount)


def valid_amount(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
        return amount if amount.is_finite() and amount >= 0 else None
    except InvalidOperation:
        return None


def calculate_budget(state):
    totals = {k: Decimal(0) for k in ('transport', 'hotels', 'food', 'activities')}
    entries, missing = [], []
    def add(category, label, result, amount):
        number = valid_amount(amount)
        if not result.get('success') or result.get('currency') != 'INR' or number is None:
            missing.append(label)
            entries.append({'category': category, 'label': label, 'amount': None, 'provenance': 'UNAVAILABLE'})
        else:
            totals[category] += number
            entries.append({'category': category, 'label': label, 'amount': float(number), 'provenance': 'CONFIGURED_ESTIMATE' if result.get('source_type')=='CONFIGURED_ESTIMATE' else 'LIVE_PROVIDER', 'source': result.get('source')})
    for leg in state.get('transport_legs', []):
        result = leg.get('result', {})
        add('transport', f"Transport {leg['origin']} to {leg['destination']} on {leg['departure_date']}", result, result.get('price'))
    for stay in state.get('stay_periods', []):
        result = stay.get('result', {})
        add('hotels', f"Stay {stay['location']} {stay['check_in']} to {stay['check_out']}", result, result.get('total_price'))
    for day in state.get('daily_plans', []):
        for category in ('food', 'activities'):
            missing.append(f"Day {day['day']} {category} price unavailable")
            entries.append({'category': category, 'label': missing[-1], 'amount': None, 'provenance': 'UNAVAILABLE'})
    total = sum(totals.values())
    budget = Decimal(str(parse_budget(state['user_requirements'].get('budget', 0))))
    over = budget > 0 and total > budget
    complete = not missing
    return {**{k: float(v) for k, v in totals.items()}, 'breakdown': {k: float(v) for k,v in totals.items()},
            'total': float(total), 'known_subtotal': float(total), 'complete': complete,
            'user_budget': float(budget), 'remaining_budget': float(budget-total) if complete else None,
            'within_budget': False if over else (True if complete else None),
            'status': 'OVER_BUDGET' if over else ('WITHIN_BUDGET' if complete else 'PARTIAL'),
            'currency': 'INR', 'entries': entries, 'missing_costs': missing,
            'component_provenance': {'user_budget': 'USER_PROVIDED', **{k: (next((e['provenance'] for e in entries if e['category']==k and e['amount'] is not None), 'UNAVAILABLE')) for k in totals}},
            'nights_counted': sum(s['nights'] for s in state.get('stay_periods', []))}
