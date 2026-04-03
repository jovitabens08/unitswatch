"""
db.py — MongoDB connection using PyMongo.

Collections used:
  - meters     : { user_id, nickname, eb_account_no, location, created_at }
  - readings   : { meter_id, user_id, reading_value, recorded_at, notes }
  - bills      : { meter_id, user_id, start_reading, end_reading, units_used,
                   estimated_amount, is_free, cycle_start, cycle_end, created_at }

All IDs are stored as strings (Django auth user pk → str).
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from django.conf import settings

_client = None
_db = None


def get_db():
    """Return MongoDB database instance (singleton)."""
    global _client, _db
    if _db is None:
        _client = MongoClient(settings.MONGO_URI)
        _db = _client.get_default_database()
        _ensure_indexes()
    return _db


def _ensure_indexes():
    """Create indexes for faster queries."""
    db = _db
    db.meters.create_index([("user_id", ASCENDING)])
    db.readings.create_index([("meter_id", ASCENDING), ("recorded_at", DESCENDING)])
    db.bills.create_index([("meter_id", ASCENDING), ("created_at", DESCENDING)])


def get_meters_col():
    return get_db().meters


def get_readings_col():
    return get_db().readings


def get_bills_col():
    return get_db().bills
