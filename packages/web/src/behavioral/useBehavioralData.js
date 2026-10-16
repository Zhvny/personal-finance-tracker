// ─── useBehavioralData.js ─────────────────────────────────────────────────────
// Interface layer — fetches pre-computed behavioral report from the CLI API.
//
// Clean Architecture: GUI is the outermost ring only.
//   - No business logic here.
//   - No computation here.
//   - Domain scoring lives in CLI: behavioral_finance/domain/models.py
//   - Data persistence lives in CLI: behavioral_finance/data/behavioral.db
//   - This hook is a pure data-fetch adapter only.
//
// Low Coupling   : depends on API_BASE constant only.
// High Cohesion  : single responsibility — fetch + expose behavioral report.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../finance/useApi.js";

/**
 * useBehavioralData — fetches the full behavioral finance report from the CLI layer.
 *
 * The CLI's api_server.py computes the report using domain models and persists
 * the snapshot to the CLI SQLite database. The GUI receives only the parsed result.
 *
 * @returns {{ loading, error, report, reload }}
 */
export function useBehavioralData() {
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [report,  setReport]  = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch("/behavioral");
      setReport(data);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return { loading, error, report, reload: load };
}
