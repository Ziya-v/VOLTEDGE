import os

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "voltedge")

client: MongoClient | None = (
    MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    if MONGODB_URI
    else None
)
database: Database | None = client[MONGODB_DATABASE] if client else None


def check_database_connection() -> str:
    """Return a safe connection status without exposing credentials or the URI."""
    if client is None:
        return "missing_uri"
    try:
        client.admin.command("ping")
        return "connected"
    except ServerSelectionTimeoutError:
        return "network_or_cluster_unreachable"
    except OperationFailure:
        return "authentication_failed"
    except ConfigurationError:
        return "invalid_uri_configuration"
    except Exception:
        return "connection_error"
