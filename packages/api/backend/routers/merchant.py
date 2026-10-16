import logging

"""

backend/routers/merchant.py — Merchant memory + Allocation rules

=================================================================

Extracted from api_server.py as part of Step 5 router split.

Architecture: High Cohesion — this file owns only /api/merchant-map|/api/allocation routes.

Low Coupling : depends only on backend/routers/deps.py and FastAPI. Never imports other routers.

"""









from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.routers.deps import (
    _get_allocation_engine,
    _get_merchant_memory,
)
from packages.api.backend.security.core import require_scope

router = APIRouter(dependencies=[Depends(require_scope("write"))])

logger = logging.getLogger(__name__)



# ═════════════════════════════════════════════════════════════════════

# MERCHANT MEMORY — Persistent merchant → category mapping

# ═════════════════════════════════════════════════════════════════════



@router.get("/api/merchant-map")

def get_merchant_map():

    """List all remembered merchant → category mappings."""

    mm = _get_merchant_memory()

    if not mm:

        logger.error("Merchant memory module not available")

        raise HTTPException(503, "Merchant memory module tidak tersedia.")

    return {"ok": True, "mappings": mm.MerchantMemory.list_all(), "stats": mm.MerchantMemory.stats()}





@router.post("/api/merchant-map/remember")

def remember_merchant(body: dict):

    """

    Store or update a merchant → category mapping.

    body: { merchant_name: str, category: str }

    Call this whenever user manually edits a receipt category.

    """

    merchant = (body.get("merchant_name") or "").strip()

    category = (body.get("category") or "").strip()

    if not merchant or not category:

        raise HTTPException(400, "merchant_name and category are required.")

    mm = _get_merchant_memory()

    if not mm:

        logger.error("Merchant memory module not available")

        raise HTTPException(503, "Merchant memory module tidak tersedia.")

    ok = mm.MerchantMemory.remember(merchant, category)

    return {"ok": ok, "merchant_name": merchant, "category": category}





@router.delete("/api/merchant-map/{merchant_name}")

def forget_merchant(merchant_name: str):

    """Remove a merchant mapping (admin / correction)."""

    mm = _get_merchant_memory()

    if not mm:

        logger.error("Merchant memory module not available")

        raise HTTPException(503, "Merchant memory module tidak tersedia.")

    ok = mm.MerchantMemory.forget(merchant_name)

    return {"ok": ok, "merchant_name": merchant_name}





# ═════════════════════════════════════════════════════════════════════

# SMART SAVING ALLOCATION — Auto-distribute income into buckets

# ═════════════════════════════════════════════════════════════════════



@router.get("/api/allocation/rules")

def get_allocation_rules():

    """Return current saving allocation rules from saving_rules.json."""

    ae = _get_allocation_engine()

    if not ae:

        logger.error("Allocation engine not available")

        raise HTTPException(503, "Allocation engine tidak tersedia.")

    rules = ae.load_rules()

    errors = ae.validate_rules(rules)

    return {"ok": True, "rules": rules, "valid": len(errors) == 0, "errors": errors}





@router.put("/api/allocation/rules")

def put_allocation_rules(body: dict):

    """

    Overwrite saving_rules.json with new rules.

    body must be a full rules object (same shape as saving_rules.json).

    Validates before saving.

    """

    ae = _get_allocation_engine()

    if not ae:

        logger.error("Allocation engine not available")

        raise HTTPException(503, "Allocation engine tidak tersedia.")

    errors = ae.validate_rules(body)

    if errors:

        raise HTTPException(400, f"Validation errors: {'; '.join(errors)}")

    ok = ae.save_rules(body)

    return {"ok": ok, "rules": body}





@router.post("/api/allocation/simulate")

def simulate_allocation(body: dict):

    """

    Preview how income would be split without writing to DB.

    body: { amount: float, rules?: {...} }

    """

    amount = float(body.get("amount", 0))

    if amount <= 0:

        raise HTTPException(400, "amount must be > 0")

    ae = _get_allocation_engine()

    if not ae:

        logger.error("Allocation engine not available")

        raise HTTPException(503, "Allocation engine tidak tersedia.")

    custom_rules = body.get("rules")

    result = ae.AllocationEngine.simulate(amount, custom_rules)

    return {"ok": True, "simulation": result}





