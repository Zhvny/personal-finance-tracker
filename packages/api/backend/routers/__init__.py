"""
backend/routers/__init__.py
============================
Router package for Finance Tracker API.
Each module owns exactly one domain and exposes a single `router: APIRouter`.

Registered in api_server.py via:
    from packages.api.backend.routers import expenses, income, ...
    app.include_router(expenses.router)

Domain map:
  expenses    — /api/expenses/*
  income      — /api/income/*
  investments — /api/investments/*
  receipts    — /api/receipt/*
  advanced    — /api/goals, /api/forecast, /api/budget
  behavioral  — /api/behavioral/*
  balances    — /api/balances/*
  rewards     — /api/rewards/*
  merchant    — /api/merchant-map/*, /api/allocation/*
  scheduler   — /api/scheduler/*, /api/networth/*
  analytics   — /api/behavioral/lifestyle-trend, /api/analytics/*
  ai          — /api/ai/*, /api/receipt/scan-ai

NOTE: No eager imports here — routers are loaded individually by api_server.py
to prevent circular import chains during startup.
"""
