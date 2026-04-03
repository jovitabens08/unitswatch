from pymongo import MongoClient
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        try:
            logger.info(f"Connecting to MongoDB with URI: {settings.MONGO_URI[:30]}...")
            _client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
            _client.server_info()  # force connection test
            _db = _client.get_default_database()
            logger.info("MongoDB connected successfully!")
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise
    return _db


def get_meters_col():
    return get_db().meters


def get_readings_col():
    return get_db().readings


def get_bills_col():
    return get_db().bills