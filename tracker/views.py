"""
views.py — All Django view functions for UnitsWatch.

Auth      : home, register_view, login_view, logout_view
Dashboard : dashboard
Meters    : meters_list, add_meter, delete_meter, meter_detail
Readings  : add_reading, delete_reading
Billing   : billing_cycles, close_cycle
Reports   : history, recommendations, export_csv
API       : api_readings
"""

import csv
import datetime
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from bson import ObjectId
from flask import request

from .db import get_meters_col, get_readings_col, get_bills_col
from .tneb import (
    calculate_bill, units_consumed, predict_bill_from_readings,
    get_current_cycle_dates, days_left_in_cycle, daily_budget,
    get_recommendations, FREE_LIMIT,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_meter_or_404(meter_id, user_id):
    meter = get_meters_col().find_one({'_id': ObjectId(meter_id), 'user_id': user_id})
    return meter


# ─── Auth ────────────────────────────────────────────────────────────────────

def home(request):
    return redirect('dashboard') if request.user.is_authenticated else redirect('login')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        email     = request.POST.get('email', '').strip()
        password  = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        fullname  = request.POST.get('full_name', '').strip()

        if not username or not password:
            messages.error(request, 'Username and password are required.')
        elif password != password2:
            messages.error(request, 'Passwords do not match.')
        elif len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            if fullname:
                parts = fullname.split(' ', 1)
                user.first_name = parts[0]
                user.last_name  = parts[1] if len(parts) > 1 else ''
                user.save()
            login(request, user)
            messages.success(request, f'Welcome to UnitsWatch, {username}!')
            return redirect('dashboard')
    return render(request, 'tracker/register.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        print(f"Attempting login with username: '{username}' and password: '{password}'")  # Debugging
        user = authenticate(request,
                            username=request.POST.get('username', '').strip(),
                            password=request.POST.get('password', ''))
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'tracker/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    user_id = str(request.user.pk)
    meters  = list(get_meters_col().find({'user_id': user_id}))

    cycle_start, cycle_end = get_current_cycle_dates()
    days_left = days_left_in_cycle()
    meter_data, alerts = [], []
    total_units = 0

    for meter in meters:
        mid = str(meter['_id'])
        readings = list(get_readings_col().find({'meter_id': mid}).sort('recorded_at', -1).limit(2))
        latest = readings[0]['reading_value'] if readings else None
        prev   = readings[1]['reading_value'] if len(readings) > 1 else None
        units  = units_consumed(prev, latest)
        bill   = calculate_bill(units)
        total_units += units

        if bill['alert']:
            alerts.append({'meter': meter.get('nickname', mid), 'msg': bill['alert']})

        meter_data.append({
            'id': mid, 'nickname': meter.get('nickname', '—'),
            'eb_account_no': meter.get('eb_account_no', '—'),
            'location': meter.get('location', '—'),
            'latest_reading': latest, 'prev_reading': prev,
            'units': round(units, 2), 'bill': bill,
            'reading_count': get_readings_col().count_documents({'meter_id': mid}),
        })

    overall = calculate_bill(total_units)
    budget  = daily_budget()

    return render(request, 'tracker/dashboard.html', {
        'meter_data'  : meter_data,
        'total_units' : round(total_units, 2),
        'overall_bill': overall,
        'alerts'      : alerts,
        'meter_count' : len(meters),
        'cycle_start' : cycle_start,
        'cycle_end'   : cycle_end,
        'days_left'   : days_left,
        'daily_budget': budget,
        'free_limit'  : FREE_LIMIT,
    })


# ─── Meters ──────────────────────────────────────────────────────────────────

@login_required
def meters_list(request):
    user_id = str(request.user.pk)
    meters  = list(get_meters_col().find({'user_id': user_id}).sort('created_at', -1))
    for m in meters:
        m['id'] = str(m['_id'])
        m['reading_count'] = get_readings_col().count_documents({'meter_id': m['id']})
    return render(request, 'tracker/meters.html', {'meters': meters})


@login_required
def add_meter(request):
    if request.method == 'POST':
        eb  = request.POST.get('eb_account_no', '').strip()
        nick = request.POST.get('nickname', '').strip()
        loc  = request.POST.get('location', '').strip()
        if not eb:
            messages.error(request, 'EB Account Number is required.')
        else:
            get_meters_col().insert_one({
                'user_id': str(request.user.pk), 'nickname': nick or eb,
                'eb_account_no': eb, 'location': loc,
                'created_at': datetime.datetime.utcnow(),
            })
            messages.success(request, f'Meter "{nick or eb}" added!')
    return redirect('meters')


@login_required
def delete_meter(request, meter_id):
    user_id = str(request.user.pk)
    meter   = _get_meter_or_404(meter_id, user_id)
    if not meter:
        messages.error(request, 'Meter not found.')
        return redirect('meters')
    if request.method == 'POST':
        get_readings_col().delete_many({'meter_id': meter_id})
        get_bills_col().delete_many({'meter_id': meter_id})
        get_meters_col().delete_one({'_id': ObjectId(meter_id)})
        messages.success(request, 'Meter deleted.')
    return redirect('meters')


# ─── Meter Detail & Readings ─────────────────────────────────────────────────

@login_required
def meter_detail(request, meter_id):
    user_id = str(request.user.pk)
    meter   = _get_meter_or_404(meter_id, user_id)
    if not meter:
        messages.error(request, 'Meter not found.')
        return redirect('meters')

    readings_asc = list(get_readings_col().find({'meter_id': meter_id}).sort('recorded_at', 1))

    annotated = []
    for i, r in enumerate(readings_asc):
        prev_val = readings_asc[i - 1]['reading_value'] if i > 0 else None
        units    = units_consumed(prev_val, r['reading_value'])
        bill     = calculate_bill(units)
        annotated.append({
            'id': str(r['_id']), 'reading_value': r['reading_value'],
            'recorded_at': r['recorded_at'], 'notes': r.get('notes', ''),
            'units': round(units, 2), 'bill_total': bill['total'],
            'is_free': bill['is_free'],
        })

    predicted    = predict_bill_from_readings(readings_asc)
    total_units  = predicted['units'] if predicted else 0
    cycle_start, cycle_end = get_current_cycle_dates()

    # Past bills for this meter
    past_bills = list(get_bills_col().find({'meter_id': meter_id}).sort('created_at', -1).limit(10))

    return render(request, 'tracker/meter_detail.html', {
        'meter'      : {**meter, 'id': meter_id},
        'readings'   : list(reversed(annotated)),
        'predicted'  : predicted,
        'total_units': total_units,
        'free_limit' : FREE_LIMIT,
        'cycle_start': cycle_start,
        'cycle_end'  : cycle_end,
        'past_bills' : past_bills,
        'days_left'  : days_left_in_cycle(),
    })


@login_required
def add_reading(request, meter_id):
    user_id = str(request.user.pk)
    meter   = _get_meter_or_404(meter_id, user_id)
    if not meter:
        messages.error(request, 'Meter not found.')
        return redirect('meters')

    if request.method == 'POST':
        try:
            value = float(request.POST.get('reading_value', ''))
        except ValueError:
            messages.error(request, 'Enter a valid reading number.')
            return redirect('meter_detail', meter_id=meter_id)

        last = get_readings_col().find_one({'meter_id': meter_id}, sort=[('recorded_at', -1)])
        if last and value < last['reading_value']:
            messages.error(request, f'Reading must be ≥ last reading ({last["reading_value"]}). Meter never goes backwards.')
            return redirect('meter_detail', meter_id=meter_id)

        get_readings_col().insert_one({
            'meter_id': meter_id, 'user_id': user_id,
            'reading_value': value, 'notes': request.POST.get('notes', '').strip(),
            'recorded_at': datetime.datetime.utcnow(),
        })
        messages.success(request, f'Reading {value} logged!')
    return redirect('meter_detail', meter_id=meter_id)


@login_required
def delete_reading(request, reading_id):
    r = get_readings_col().find_one({'_id': ObjectId(reading_id)})
    if r:
        mid = r['meter_id']
        get_readings_col().delete_one({'_id': ObjectId(reading_id)})
        messages.success(request, 'Reading deleted.')
        return redirect('meter_detail', meter_id=mid)
    return redirect('dashboard')


# ─── Billing Cycles ──────────────────────────────────────────────────────────

@login_required
def billing_cycles(request):
    """View and manage billing cycles across all meters."""
    user_id = str(request.user.pk)
    meters  = list(get_meters_col().find({'user_id': user_id}))
    data    = []

    for meter in meters:
        mid   = str(meter['_id'])
        bills = list(get_bills_col().find({'meter_id': mid}).sort('created_at', -1))
        readings_asc = list(get_readings_col().find({'meter_id': mid}).sort('recorded_at', 1))
        predicted    = predict_bill_from_readings(readings_asc)
        data.append({
            'meter'    : {**meter, 'id': mid},
            'bills'    : bills,
            'predicted': predicted,
        })

    cycle_start, cycle_end = get_current_cycle_dates()
    return render(request, 'tracker/billing_cycles.html', {
        'data'       : data,
        'cycle_start': cycle_start,
        'cycle_end'  : cycle_end,
        'days_left'  : days_left_in_cycle(),
    })


@login_required
def close_cycle(request, meter_id):
    """Manually close a billing cycle and save the bill to MongoDB."""
    user_id = str(request.user.pk)
    meter   = _get_meter_or_404(meter_id, user_id)
    if not meter or request.method != 'POST':
        return redirect('billing_cycles')

    readings_asc = list(get_readings_col().find({'meter_id': meter_id}).sort('recorded_at', 1))
    if len(readings_asc) < 2:
        messages.error(request, 'Need at least 2 readings to close a cycle.')
        return redirect('billing_cycles')

    bill_info = predict_bill_from_readings(readings_asc)
    cycle_start, cycle_end = get_current_cycle_dates()

    get_bills_col().insert_one({
        'meter_id'        : meter_id,
        'user_id'         : user_id,
        'start_reading'   : readings_asc[0]['reading_value'],
        'end_reading'     : readings_asc[-1]['reading_value'],
        'units_used'      : bill_info['units'],
        'estimated_amount': bill_info['total'],
        'is_free'         : bill_info['is_free'],
        'cycle_start'     : cycle_start.isoformat(),
        'cycle_end'       : cycle_end.isoformat(),
        'created_at'      : datetime.datetime.utcnow(),
    })
    messages.success(request, f'Cycle closed. Bill: ₹{bill_info["total"]} for {bill_info["units"]} units.')
    return redirect('billing_cycles')


# ─── Recommendations ─────────────────────────────────────────────────────────

@login_required
def recommendations(request):
    user_id = str(request.user.pk)
    meters  = list(get_meters_col().find({'user_id': user_id}))

    cycle_start, _ = get_current_cycle_dates()
    today          = datetime.date.today()
    days_elapsed   = max(1, (today - cycle_start).days)

    # Aggregate total units across all meters
    total_units = 0
    for meter in meters:
        mid      = str(meter['_id'])
        readings = list(get_readings_col().find({'meter_id': mid}).sort('recorded_at', 1))
        if len(readings) >= 2:
            total_units += units_consumed(readings[0]['reading_value'], readings[-1]['reading_value'])

    tips = get_recommendations(total_units, days_elapsed)
    bill = calculate_bill(total_units)

    return render(request, 'tracker/recommendations.html', {
        'tips'        : tips,
        'total_units' : round(total_units, 2),
        'bill'        : bill,
        'days_elapsed': days_elapsed,
        'days_left'   : days_left_in_cycle(),
        'daily_budget': daily_budget(),
    })


# ─── History ─────────────────────────────────────────────────────────────────

@login_required
def history(request):
    user_id = str(request.user.pk)
    meters  = list(get_meters_col().find({'user_id': user_id}))
    all_data = []
    for meter in meters:
        mid      = str(meter['_id'])
        readings = list(get_readings_col().find({'meter_id': mid}).sort('recorded_at', -1).limit(10))
        bills    = list(get_bills_col().find({'meter_id': mid}).sort('created_at', -1).limit(5))
        if readings or bills:
            all_data.append({'meter': {**meter, 'id': mid}, 'readings': readings, 'bills': bills})
    return render(request, 'tracker/history.html', {'all_data': all_data})


# ─── CSV Export ──────────────────────────────────────────────────────────────

@login_required
def export_csv(request):
    """Export all readings for the logged-in user as a CSV file."""
    user_id  = str(request.user.pk)
    meters   = list(get_meters_col().find({'user_id': user_id}))

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="unitswatch_export.csv"'
    writer   = csv.writer(response)
    writer.writerow(['Meter Nickname', 'EB Account No', 'Location', 'Date', 'Reading (units)', 'Units Since Prev', 'Notes'])

    for meter in meters:
        mid      = str(meter['_id'])
        readings = list(get_readings_col().find({'meter_id': mid}).sort('recorded_at', 1))
        for i, r in enumerate(readings):
            prev  = readings[i-1]['reading_value'] if i > 0 else None
            units = round(units_consumed(prev, r['reading_value']), 2)
            writer.writerow([
                meter.get('nickname', ''), meter.get('eb_account_no', ''),
                meter.get('location', ''),
                r['recorded_at'].strftime('%Y-%m-%d %H:%M'),
                r['reading_value'], units if i > 0 else '—',
                r.get('notes', ''),
            ])
    return response


# ─── API ─────────────────────────────────────────────────────────────────────

@login_required
def api_readings(request, meter_id):
    user_id = str(request.user.pk)
    meter   = _get_meter_or_404(meter_id, user_id)
    if not meter:
        return JsonResponse({'error': 'Not found'}, status=404)

    readings = list(get_readings_col().find({'meter_id': meter_id}).sort('recorded_at', 1).limit(30))
    labels   = [r['recorded_at'].strftime('%d %b') for r in readings]
    values   = [r['reading_value'] for r in readings]
    units    = [0 if i == 0 else round(readings[i]['reading_value'] - readings[i-1]['reading_value'], 2)
                for i in range(len(readings))]
    return JsonResponse({'labels': labels, 'values': values, 'units': units})
