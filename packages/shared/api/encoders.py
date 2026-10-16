import json
import logging

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            import numpy as np

            if isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            if isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            if isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            # Fallback for numpy types if numpy is not installed but objects exist (unlikely but safe)
            classname = obj.__class__.__name__
            if classname in ["bool_", "bool8"]:
                return bool(obj)
            if classname in ["int64", "int32", "intc"]:
                return int(obj)
            if classname in ["float64", "float32", "floatc"]:
                return float(obj)

        from datetime import date, datetime

        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        from decimal import Decimal

        if isinstance(obj, Decimal):
            return float(obj)

        try:
            # Try jsonable_encoder but catch errors to avoid crashing the whole response
            return jsonable_encoder(obj)
        except Exception:
            try:
                # Last resort: convert to string
                return str(obj)
            except Exception:
                logger.warning("CustomJSONEncoder: unserializable object of type %s", type(obj).__name__)
                return None


def custom_json_encoder(obj):
    # This is a helper for direct calls if needed, but we prefer the class for JSONResponse
    return json.loads(json.dumps(obj, cls=CustomJSONEncoder))


class ExtendedJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=CustomJSONEncoder,
        ).encode("utf-8")
