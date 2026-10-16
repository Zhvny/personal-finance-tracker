"""
Business Analytics & Earned Value Management (EVM) Engine
==========================================================
Handles multi-project analytics, EVM KPI calculations (PV, EV, AC, CPI, SPI, CV, SV),
S-Curve time series generation, labor/attendance tracking, and multi-format
executive report generation (JSON, Markdown, HTML/PDF-ready).
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import packages.database.index as _db_module

logger = logging.getLogger(__name__)


class BusinessAnalyticsService:
    """
    Domain service for Business Profile analytics.
    All methods are async and use Prisma via packages.database.index.
    """

    # ── Project CRUD ──────────────────────────────────────────────────────────

    async def get_projects(self) -> List[Dict[str, Any]]:
        db = await _db_module.get_db()
        projects = await db.businessproject.find_many(order={"createdAt": "desc"})
        return [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
                "description": p.description,
                "budget": float(p.budget),
                "startDate": p.startDate.isoformat(),
                "endDate": p.endDate.isoformat(),
                "status": p.status,
            }
            for p in projects
        ]

    async def create_project(
        self,
        name: str,
        code: str,
        budget: float,
        start_date: datetime,
        end_date: datetime,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        db = await _db_module.get_db()
        created = await db.businessproject.create(
            data={
                "name": name,
                "code": code.upper(),
                "budget": float(budget),
                "startDate": start_date,
                "endDate": end_date,
                "description": description,
            }
        )
        return {
            "id": created.id,
            "name": created.name,
            "code": created.code,
            "budget": float(created.budget),
        }

    # ── Daily Progress Logging ────────────────────────────────────────────────

    async def record_daily_progress(
        self,
        project_id: int,
        log_date: datetime,
        planned_pct: float,
        actual_pct: float,
        actual_cost: float,
        headcount: int = 0,
        work_hours: float = 8.0,
        tasks_completed: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        db = await _db_module.get_db()
        log = await db.dailyprogresslog.upsert(
            where={"projectId_logDate": {"projectId": project_id, "logDate": log_date}},
            data={
                "create": {
                    "projectId": project_id,
                    "logDate": log_date,
                    "plannedProgressFloat": float(planned_pct),
                    "actualProgressFloat": float(actual_pct),
                    "actualCost": float(actual_cost),
                    "headcount": headcount,
                    "workHours": float(work_hours),
                    "tasksCompleted": tasks_completed,
                    "notes": notes,
                },
                "update": {
                    "plannedProgressFloat": float(planned_pct),
                    "actualProgressFloat": float(actual_pct),
                    "actualCost": float(actual_cost),
                    "headcount": headcount,
                    "workHours": float(work_hours),
                    "tasksCompleted": tasks_completed,
                    "notes": notes,
                },
            },
        )
        return {"id": log.id, "ok": True}

    # ── Labor & Attendance Logging ────────────────────────────────────────────

    async def record_labor_attendance(
        self,
        project_id: int,
        log_date: datetime,
        worker_role: str,
        present_count: int,
        total_count: int,
        man_hours: float,
    ) -> Dict[str, Any]:
        db = await _db_module.get_db()
        rec = await db.laborattendancelog.create(
            data={
                "projectId": project_id,
                "date": log_date,
                "workerRole": worker_role,
                "presentCount": present_count,
                "totalCount": total_count,
                "manHours": float(man_hours),
            }
        )
        return {"id": rec.id, "ok": True}

    # ── Milestone Management ──────────────────────────────────────────────────

    async def add_milestone(
        self,
        project_id: int,
        title: str,
        target_date: datetime,
        weight: float = 1.0,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        db = await _db_module.get_db()
        m = await db.projectmilestone.create(
            data={
                "projectId": project_id,
                "title": title,
                "targetDate": target_date,
                "weight": float(weight),
                "description": description,
            }
        )
        return {"id": m.id, "ok": True}

    async def complete_milestone(self, milestone_id: int) -> Dict[str, Any]:
        db = await _db_module.get_db()
        await db.projectmilestone.update(
            where={"id": milestone_id},
            data={"isCompleted": True, "completedAt": datetime.now()},
        )
        return {"ok": True}

    # ── Core Analytics & EVM Engine ───────────────────────────────────────────

    async def get_project_analytics(self, project_id: int) -> Dict[str, Any]:
        """
        Computes full EVM analytics for a project:
          PV  = Budget × Planned%
          EV  = Budget × Actual%
          AC  = Σ actual_cost from daily logs
          CPI = EV / AC      (> 1.0 = under budget)
          SPI = EV / PV      (> 1.0 = ahead of schedule)
          CV  = EV − AC      (positive = under budget)
          SV  = EV − PV      (positive = ahead of schedule)
          EAC = Budget / CPI (projected cost at completion)
          ETC = EAC − AC     (remaining estimated cost)
        """
        db = await _db_module.get_db()
        project = await db.businessproject.find_unique(
            where={"id": project_id},
            include={"dailyLogs": True, "milestones": True, "attendance": True},
        )
        if not project:
            raise ValueError(f"Project ID {project_id} not found.")

        logs = sorted(project.dailyLogs, key=lambda x: x.logDate)
        budget = float(project.budget)

        # Latest cumulative figures
        latest = logs[-1] if logs else None
        planned_pct = float(latest.plannedProgressFloat) if latest else 0.0
        actual_pct  = float(latest.actualProgressFloat)  if latest else 0.0
        ac           = sum(float(l.actualCost) for l in logs)

        # EVM core
        pv  = budget * (planned_pct / 100.0)
        ev  = budget * (actual_pct  / 100.0)
        cpi = (ev / ac) if ac > 0 else (1.0 if ev == 0 else 9.99)
        spi = (ev / pv) if pv > 0 else (1.0 if ev == 0 else 9.99)
        cv  = ev - ac
        sv  = ev - pv
        eac = (budget / cpi) if cpi > 0 else budget
        etc = eac - ac

        # Health badge
        if cpi >= 1.0 and spi >= 0.95:
            status_badge = "ON_TRACK"
        elif cpi < 0.9 or spi < 0.85:
            status_badge = "CRITICAL"
        else:
            status_badge = "WARNING"

        # S-Curve time series
        s_curve = []
        cum_cost = 0.0
        for l in logs:
            cum_cost += float(l.actualCost)
            s_curve.append({
                "date":          l.logDate.strftime("%Y-%m-%d"),
                "planned_pct":   round(float(l.plannedProgressFloat), 2),
                "actual_pct":    round(float(l.actualProgressFloat),  2),
                "planned_value": round(budget * float(l.plannedProgressFloat) / 100.0, 2),
                "earned_value":  round(budget * float(l.actualProgressFloat)  / 100.0, 2),
                "actual_cost":   round(cum_cost, 2),
                "daily_cost":    round(float(l.actualCost), 2),
                "headcount":     l.headcount,
                "work_hours":    float(l.workHours),
            })

        # Attendance summary
        att_logs = project.attendance
        total_mh = sum(float(a.manHours) for a in att_logs)
        avg_att  = (
            sum(
                float(a.presentCount) / float(a.totalCount) * 100.0
                for a in att_logs
                if a.totalCount > 0
            )
            / len(att_logs)
        ) if att_logs else 100.0

        # Milestone breakdown
        milestones_data = [
            {
                "id":          m.id,
                "title":       m.title,
                "target_date": m.targetDate.strftime("%Y-%m-%d"),
                "weight":      float(m.weight),
                "is_completed": m.isCompleted,
                "completed_at": m.completedAt.isoformat() if m.completedAt else None,
            }
            for m in project.milestones
        ]
        milestones_completed = sum(1 for m in project.milestones if m.isCompleted)
        milestones_total     = len(project.milestones)

        # Velocity trend (7-day rolling avg actual progress increment)
        velocity_7d = 0.0
        if len(s_curve) >= 7:
            last7 = s_curve[-7:]
            velocity_7d = round((last7[-1]["actual_pct"] - last7[0]["actual_pct"]) / 7.0, 3)

        # ── BI/BA Advanced Analytics Calculations ─────────────────────────────
        # 1. Root Cause Analysis
        root_causes = []
        if cpi < 0.9:
            root_causes.append({
                "category": "Cost Overrun",
                "severity": "HIGH",
                "primary_factor": f"Cost Performance Index (CPI={cpi:.2f}) indicates spending exceeds progress earned. Total actual spend Rp {ac:,.0f} vs earned Rp {ev:,.0f}.",
                "trigger": "Low capital efficiency or unbudgeted material/resource inflation."
            })
        if spi < 0.85:
            root_causes.append({
                "category": "Schedule Delay",
                "severity": "HIGH",
                "primary_factor": f"Schedule Performance Index (SPI={spi:.2f}) indicates progress lag behind plan ({actual_pct}% vs {planned_pct}%).",
                "trigger": "Bottleneck in daily execution or manpower attendance."
            })
        if avg_att < 80.0:
            root_causes.append({
                "category": "Labor Productivity",
                "severity": "MEDIUM",
                "primary_factor": f"Average attendance ({avg_att:.1f}%) is below optimal threshold (80%).",
                "trigger": "Resource absenteeism impacting task velocity."
            })
        if not root_causes:
            root_causes.append({
                "category": "Optimal Operation",
                "severity": "LOW",
                "primary_factor": "Project operates within acceptable EVM tolerance thresholds.",
                "trigger": "Effective cost and schedule governance."
            })

        # 2. Anomaly / Exception Analysis
        anomalies = []
        avg_daily_cost = (ac / len(logs)) if logs else 0.0
        for l in logs:
            cost_val = float(l.actualCost)
            dt_str = l.logDate.strftime("%Y-%m-%d")
            if avg_daily_cost > 0 and cost_val > 2.2 * avg_daily_cost:
                anomalies.append({
                    "date": dt_str,
                    "type": "COST_SPIKE",
                    "severity": "WARNING",
                    "description": f"Daily cost Rp {cost_val:,.0f} is {(cost_val / avg_daily_cost):.1f}x higher than average daily spend."
                })
            if l.plannedProgressFloat > l.actualProgressFloat + 15.0:
                anomalies.append({
                    "date": dt_str,
                    "type": "PROGRESS_GAP",
                    "severity": "CRITICAL",
                    "description": f"Progress gap of {(l.plannedProgressFloat - l.actualProgressFloat):.1f}% on {dt_str}."
                })

        # 3. Forecasting Engine
        rem_pct = max(0.0, 100.0 - actual_pct)
        est_days_to_complete = round(rem_pct / velocity_7d, 1) if velocity_7d > 0 else 999.0
        forecast_30d_pct = min(100.0, round(actual_pct + (velocity_7d * 30.0), 2))
        cost_overrun_projected = max(0.0, eac - budget)

        # 4. Actionable Recommendations
        recommendations = []
        if cpi < 0.95:
            recommendations.append("Lakukan audit biaya material dan negosiasi ulang supplier untuk menekan CPI mendekati ≥ 1.0.")
        if spi < 0.90:
            _dev = round(actual_pct - planned_pct, 1)
            recommendations.append(f"Tambah kapasitas tenaga kerja atau alokasikan lembur untuk mengejar deviasi progres ({_dev:+.1f}%).")
        if est_days_to_complete > 90 and actual_pct < 50:
            recommendations.append("Lakukan pemecahan milestone kritis menjadi sprint mingguan untuk mempercepat velocity.")
        if not recommendations:
            recommendations.append("Pertahankan ritme eksekusi dan alokasi anggaran saat ini.")

        # 5. Executive Summary Synthesis
        exec_headline = (
            f"Proyek {project.name} berjalan dengan status {status_badge.replace('_',' ')}. "
            f"Progres aktual mencapai {actual_pct}% (rencana {planned_pct}%). "
            f"CPI = {cpi:.2f}, SPI = {spi:.2f}."
        )

        # 6. Drill-down Logs mapping
        drill_down_logs = [
            {
                "id": l.id,
                "date": l.logDate.strftime("%Y-%m-%d"),
                "planned_pct": float(l.plannedProgressFloat),
                "actual_pct": float(l.actualProgressFloat),
                "actual_cost": float(l.actualCost),
                "headcount": l.headcount,
                "work_hours": float(l.workHours),
                "tasks_completed": l.tasksCompleted or "—",
                "notes": l.notes or "—"
            }
            for l in logs
        ]

        return {
            "project_id":    project.id,
            "project_name":  project.name,
            "project_code":  project.code,
            "budget":        budget,
            "status_badge":  status_badge,
            "executive_summary": {
                "headline": exec_headline,
                "status": status_badge,
                "cpi": round(cpi, 3),
                "spi": round(spi, 3),
                "progress_deviation": round(actual_pct - planned_pct, 2),
            },
            "kpi_metrics": {
                "revenue_ev": round(ev, 2),
                "cost_ac": round(ac, 2),
                "gross_profit": round(ev - ac, 2),
                "profit_margin_pct": round(((ev - ac) / ev * 100) if ev > 0 else 0.0, 1),
                "productivity": round(actual_pct / (total_mh / 100.0) if total_mh > 0 else 0.0, 2),
                "target_fulfillment_pct": round((actual_pct / planned_pct * 100.0) if planned_pct > 0 else 100.0, 1)
            },
            "evm": {
                "pv":  round(pv,  2),
                "ev":  round(ev,  2),
                "ac":  round(ac,  2),
                "cpi": round(cpi, 3),
                "spi": round(spi, 3),
                "cv":  round(cv,  2),
                "sv":  round(sv,  2),
                "eac": round(eac, 2),
                "etc": round(etc, 2),
            },
            "progress": {
                "planned_pct":   round(planned_pct, 2),
                "actual_pct":    round(actual_pct,  2),
                "deviation_pct": round(actual_pct - planned_pct, 2),
            },
            "s_curve": s_curve,
            "labor": {
                "total_man_hours":    round(total_mh, 1),
                "avg_attendance_pct": round(avg_att,  1),
            },
            "milestones": {
                "total":     milestones_total,
                "completed": milestones_completed,
                "items":     milestones_data,
            },
            "trend": {
                "velocity_7d_pct_per_day": velocity_7d,
            },
            "root_cause_analysis": root_causes,
            "anomalies": anomalies,
            "forecasting": {
                "est_days_to_complete": est_days_to_complete,
                "forecast_30d_pct": forecast_30d_pct,
                "projected_final_cost_eac": round(eac, 2),
                "cost_overrun_projected": round(cost_overrun_projected, 2),
            },
            "recommendations": recommendations,
            "drill_down": drill_down_logs,
            "methodology": {
                "framework": "ANSI/EIA-748 Earned Value Management Standard & S-Curve Time Series Analysis",
                "data_source": "Prisma PostgreSQL Business Analytics Engine",
                "calculated_at": datetime.now().isoformat()
            }
        }

    # ── Executive Report Generator ────────────────────────────────────────────

    async def generate_executive_report(
        self, project_id: int, period_type: str = "weekly"
    ) -> Dict[str, Any]:
        """
        Generates a comprehensive 12-section BI/BA executive report (Daily, Weekly, Monthly):
          1. Executive Summary          7. Segmentasi (Milestones)
          2. KPI & Metrics              8. Forecasting/Prediksi
          3. Dashboard/Visualisasi      9. Anomaly/Exception Analysis
          4. Analisis Tren (S-Curve)   10. Recommendation
          5. Target vs Actual          11. Drill-down Detail
          6. Analisis Penyebab         12. Data Source & Methodology
        Outputs: JSON | Markdown | HTML (PDF-ready)
        """
        period_type_clean = period_type.lower()
        if period_type_clean not in ["daily", "weekly", "monthly"]:
            period_type_clean = "weekly"

        a = await self.get_project_analytics(project_id)
        evm   = a["evm"]
        prog  = a["progress"]
        labor = a["labor"]
        ms    = a["milestones"]
        name  = a["project_name"]
        code  = a["project_code"]
        badge = a["status_badge"]
        kpi   = a["kpi_metrics"]
        exc   = a["executive_summary"]
        rca   = a["root_cause_analysis"]
        anom  = a["anomalies"]
        fcast = a["forecasting"]
        recs  = a["recommendations"]
        dd    = a["drill_down"]
        meth  = a["methodology"]
        trend = a["trend"]
        s_curve = a.get("s_curve", [])

        # S-Curve period slice
        if period_type_clean == "daily":
            sc = s_curve[-2:] if len(s_curve) >= 2 else s_curve
            period_label = "Laporan Harian (Daily Report)"
        elif period_type_clean == "monthly":
            sc = s_curve[-30:] if len(s_curve) >= 30 else s_curve
            period_label = "Laporan Bulanan (Monthly Report)"
        else:
            sc = s_curve[-7:] if len(s_curve) >= 7 else s_curve
            period_label = "Laporan Mingguan (Weekly Report)"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

        # ── Build S-Curve MD table ────────────────────────────────────────────
        sc_md = "\n".join(
            f"| {p['date']} | {p['planned_pct']}% | {p['actual_pct']}% "
            f"| Rp {p['planned_value']:,.0f} | Rp {p['earned_value']:,.0f} "
            f"| Rp {p['actual_cost']:,.0f} | Rp {p['daily_cost']:,.0f} |"
            for p in sc
        ) or "| — | — | — | — | — | — | — |"

        # ── Build RCA MD ──────────────────────────────────────────────────────
        rca_md = "\n".join(
            f"- **[{r['severity']}] {r['category']}:** {r['primary_factor']} *(Trigger: {r['trigger']})*"
            for r in rca
        )

        # ── Build Anomaly MD ──────────────────────────────────────────────────
        anom_md = "\n".join(
            f"- **{anm['date']} [{anm['severity']}] {anm['type'].replace('_',' ')}:** {anm['description']}"
            for anm in anom
        ) or "- Tidak ada anomali terdeteksi dalam periode ini."

        # ── Build Recs MD ─────────────────────────────────────────────────────
        recs_md = "\n".join(f"{i+1}. {r}" for i, r in enumerate(recs))

        # ── Build Milestone MD ────────────────────────────────────────────────
        ms_items_md = "\n".join(
            f"- {'[x]' if m['is_completed'] else '[ ]'} **{m['title']}** (Target: {m['target_date']}, Bobot: {m['weight']})"
            for m in ms["items"]
        ) or "- Belum ada milestone."

        # ── Build Drill-down MD table (last 10 entries) ───────────────────────
        drill_md = "\n".join(
            f"| {d['date']} | {d['planned_pct']:.1f}% | {d['actual_pct']:.1f}% "
            f"| {d['actual_pct']-d['planned_pct']:+.1f}% | Rp {d['actual_cost']:,.0f} "
            f"| {d['headcount']} | {d['work_hours']}h |"
            for d in dd[-10:]
        ) or "| — | — | — | — | — | — | — |"

        # ════════════════════════════════════════════════════════════════════
        # MARKDOWN REPORT
        # ════════════════════════════════════════════════════════════════════
        md = f"""# Business Intelligence & Analytics Report
## {name} ({code}) · {period_label}
**Generated:** {now_str} · **Framework:** {meth['framework']}

---

## 1. Executive Summary

> **Status:** `{badge.replace("_"," ")}`

{exc['headline']}

| KPI | Value |
|---|---|
| CPI | **{evm['cpi']:.2f}** — {'Within Budget' if evm['cpi'] >= 1 else 'Over Budget'} |
| SPI | **{evm['spi']:.2f}** — {'On Schedule' if evm['spi'] >= 1 else 'Behind Schedule'} |
| Progress Deviation | **{prog['deviation_pct']:+.2f}%** |
| Velocity (7d) | **{trend['velocity_7d_pct_per_day']}%/hari** |

---

## 2. KPI & Metrik

| Metrik | Nilai | Keterangan |
|---|---|---|
| Earned Value (Revenue Proxy) | Rp {kpi['revenue_ev']:,.0f} | Budget × Aktual% |
| Actual Cost (Biaya) | Rp {kpi['cost_ac']:,.0f} | Total pengeluaran nyata |
| Gross Profit (EV−AC) | Rp {kpi['gross_profit']:,.0f} | {'Surplus' if kpi['gross_profit'] >= 0 else 'Deficit'} |
| Profit Margin | {kpi['profit_margin_pct']:.1f}% | |
| Produktivitas | {kpi['productivity']:.2f} | % progres per 100 man-hours |
| Target Fulfillment | {kpi['target_fulfillment_pct']:.1f}% | Aktual vs Rencana |
| Total Man-Hours | {labor['total_man_hours']} hrs | |
| Rata-rata Kehadiran | {labor['avg_attendance_pct']}% | |

---

## 3. Analisis Tren & Kurva S — {period_label}

| Tanggal | Rencana % | Aktual % | PV (Rp) | EV (Rp) | AC (Rp) | Biaya Harian |
|---|---|---|---|---|---|---|
{sc_md}

---

## 4. Target vs Actual

| Dimensi | Target/Rencana | Aktual | Deviasi |
|---|---|---|---|
| Progres Kumulatif | {prog['planned_pct']}% | {prog['actual_pct']}% | {prog['deviation_pct']:+.2f}% |
| Planned Value (PV) | Rp {evm['pv']:,.0f} | Rp {evm['ev']:,.0f} | Rp {evm['sv']:+,.0f} |
| Budget vs EAC | Rp {a['budget']:,.0f} | Rp {evm['eac']:,.0f} | Rp {evm['eac']-a['budget']:+,.0f} |
| Target Fulfillment | 100% | {kpi['target_fulfillment_pct']:.1f}% | {kpi['target_fulfillment_pct']-100:.1f}% |

---

## 5. Analisis Penyebab (Root Cause Analysis)

{rca_md}

---

## 6. Segmentasi — Milestones ({ms['completed']}/{ms['total']} selesai)

{ms_items_md}

---

## 7. Forecasting & Prediksi

| Proyeksi | Nilai |
|---|---|
| Estimasi Hari Selesai | {'N/A' if fcast['est_days_to_complete'] >= 999 else f"{fcast['est_days_to_complete']} hari"} |
| Proyeksi Progres 30 Hari | {fcast['forecast_30d_pct']}% |
| EAC (Proyeksi Total Biaya) | Rp {fcast['projected_final_cost_eac']:,.0f} |
| Proyeksi Cost Overrun | {'Tidak ada' if fcast['cost_overrun_projected'] == 0 else f"Rp {fcast['cost_overrun_projected']:,.0f}"} |

---

## 8. Anomali & Exception Analysis

{anom_md}

---

## 9. Rekomendasi

{recs_md}

---

## 10. Drill-down Detail (10 Entri Terakhir)

| Tanggal | Rencana % | Aktual % | Deviasi | Biaya | HC | Jam |
|---|---|---|---|---|---|---|
{drill_md}

---

## 11. Data Source & Metodologi

- **Framework:** {meth['framework']}
- **Sumber Data:** {meth['data_source']}
- **Periode Laporan:** {period_label}
- **Dihitung Pada:** {meth['calculated_at']}
- **Definisi CPI:** EV/AC — >1 under budget, <1 over budget
- **Definisi SPI:** EV/PV — >1 ahead of schedule, <1 behind
- **EAC:** Budget/CPI — proyeksi biaya akhir berdasarkan efisiensi saat ini
- **Anomaly Detection:** Cost spike >2.2× rata-rata harian; Progress gap >15% pada satu hari
- **Velocity 7d:** Rata-rata kenaikan % aktual per hari selama 7 hari terakhir

---
*Report generated automatically by Alpha Business Intelligence & Analytics Engine · {now_str}*
"""

        # ════════════════════════════════════════════════════════════════════
        # HTML REPORT (PDF-ready)
        # ════════════════════════════════════════════════════════════════════
        badge_color = {"ON_TRACK": "#059669", "WARNING": "#d97706", "CRITICAL": "#dc2626"}.get(badge, "#64748b")

        # HTML helpers
        def _sc_html():
            if not sc:
                return "<tr><td colspan='7'>Belum ada data.</td></tr>"
            return "".join(
                f"<tr><td>{p['date']}</td><td>{p['planned_pct']}%</td><td>{p['actual_pct']}%</td>"
                f"<td>Rp {p['planned_value']:,.0f}</td><td>Rp {p['earned_value']:,.0f}</td>"
                f"<td>Rp {p['actual_cost']:,.0f}</td><td>Rp {p['daily_cost']:,.0f}</td></tr>"
                for p in sc
            )

        def _rca_html():
            colors = {"HIGH": "#fee2e2", "MEDIUM": "#fef3c7", "LOW": "#d1fae5"}
            bcolors = {"HIGH": "#dc2626", "MEDIUM": "#d97706", "LOW": "#059669"}
            return "".join(
                f"""<div style="background:{colors.get(r['severity'],'#f1f5f9')};border-left:4px solid {bcolors.get(r['severity'],'#64748b')};
                    padding:12px 16px;border-radius:8px;margin-bottom:10px;">
                  <div style="font-weight:700;font-size:13px;margin-bottom:4px;">
                    <span style="background:{bcolors.get(r['severity'],'#64748b')};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;margin-right:8px;">{r['severity']}</span>
                    {r['category']}
                  </div>
                  <p style="font-size:12px;margin:0 0 4px 0;">{r['primary_factor']}</p>
                  <p style="font-size:11px;color:#64748b;margin:0;">Trigger: {r['trigger']}</p>
                </div>"""
                for r in rca
            )

        def _anom_html():
            if not anom:
                return "<p style='color:#059669;font-size:13px;'>Tidak ada anomali terdeteksi.</p>"
            colors = {"WARNING": "#fef3c7", "CRITICAL": "#fee2e2"}
            bcolors = {"WARNING": "#d97706", "CRITICAL": "#dc2626"}
            return "".join(
                f"""<div style="background:{colors.get(anm['severity'],'#f1f5f9')};border-left:4px solid {bcolors.get(anm['severity'],'#64748b')};
                    padding:10px 14px;border-radius:8px;margin-bottom:8px;">
                  <div style="font-weight:700;font-size:12px;margin-bottom:3px;">{anm['type'].replace('_',' ')} · {anm['date']}</div>
                  <p style="font-size:12px;margin:0;">{anm['description']}</p>
                </div>"""
                for anm in anom
            )

        def _recs_html():
            return "".join(
                f'<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:10px;">'
                f'<div style="width:24px;height:24px;border-radius:50%;background:#0f172a;color:#fff;'
                f'display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;">{i+1}</div>'
                f'<p style="font-size:13px;margin:4px 0 0 0;">{r}</p></div>'
                for i, r in enumerate(recs)
            )

        def _drill_html():
            rows = dd[-10:]
            if not rows:
                return "<tr><td colspan='7'>Belum ada data.</td></tr>"
            return "".join(
                f"<tr><td>{d['date']}</td><td>{d['planned_pct']:.1f}%</td><td>{d['actual_pct']:.1f}%</td>"
                f"<td style='color:{'#059669' if d['actual_pct']>=d['planned_pct'] else '#d97706'};font-weight:600;'>"
                f"{d['actual_pct']-d['planned_pct']:+.1f}%</td>"
                f"<td>Rp {d['actual_cost']:,.0f}</td><td>{d['headcount']}</td><td>{d['work_hours']}h</td></tr>"
                for d in rows
            )

        def _ms_html():
            if not ms["items"]:
                return "<p style='color:#64748b;'>Belum ada milestone.</p>"
            return "".join(
                f"""<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:8px;
                    margin-bottom:6px;background:{'#f0fdf4' if m['is_completed'] else '#f8fafc'};
                    border:1px solid {'#bbf7d0' if m['is_completed'] else '#e2e8f0'};">
                  <div style="width:18px;height:18px;border-radius:50%;background:{'#059669' if m['is_completed'] else 'transparent'};
                    border:2px solid {'#059669' if m['is_completed'] else '#94a3b8'};flex-shrink:0;
                    display:flex;align-items:center;justify-content:center;">
                    {'<span style="color:#fff;font-size:9px;">✓</span>' if m["is_completed"] else ''}
                  </div>
                  <div style="flex:1;">
                    <p style="font-size:12px;font-weight:600;margin:0;{'text-decoration:line-through;color:#94a3b8;' if m['is_completed'] else ''}">{m['title']}</p>
                    <p style="font-size:11px;color:#64748b;margin:0;">Target: {m['target_date']} · Bobot: {m['weight']}</p>
                  </div>
                </div>"""
                for m in ms["items"]
            )

        html = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>BI/BA Executive Report — {name}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{font-family:'Inter',sans-serif;color:#1e293b;background:#f8fafc;padding:0;}}
    .page{{max-width:960px;margin:0 auto;background:#fff;padding:48px;box-shadow:0 4px 24px rgba(0,0,0,.07);}}
    .header{{border-bottom:3px solid #0f172a;padding-bottom:20px;margin-bottom:36px;}}
    h1{{font-size:22px;font-weight:800;color:#0f172a;}}
    .meta{{color:#64748b;font-size:12px;margin-top:4px;}}
    .badge{{display:inline-block;padding:4px 14px;border-radius:20px;font-weight:700;font-size:12px;color:#fff;background:{badge_color};margin-top:8px;}}
    .section{{margin-bottom:36px;}}
    h2{{font-size:14px;font-weight:700;color:#0f172a;margin:0 0 14px 0;padding:8px 0;border-bottom:1px solid #e2e8f0;letter-spacing:.02em;text-transform:uppercase;}}
    .grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;}}
    .grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;}}
    .grid2{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:16px;}}
    .kpi{{background:#f8fafc;border:1px solid #e2e8f0;padding:14px;border-radius:10px;}}
    .kpi-label{{font-size:10px;font-weight:600;color:#64748b;text-transform:uppercase;letter-spacing:.06em;}}
    .kpi-value{{font-size:20px;font-weight:700;color:#0f172a;margin:4px 0 2px;}}
    .kpi-sub{{font-size:11px;color:#94a3b8;}}
    table{{width:100%;border-collapse:collapse;margin-bottom:12px;font-size:12px;}}
    th{{background:#f1f5f9;padding:8px 10px;text-align:left;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0;}}
    td{{padding:7px 10px;border-bottom:1px solid #f1f5f9;}}
    tr:last-child td{{border-bottom:none;}}
    .exec-box{{background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:16px;margin-bottom:16px;}}
    .exec-box p{{font-size:13px;line-height:1.6;color:#0c4a6e;}}
    .footer{{margin-top:48px;padding-top:16px;border-top:1px solid #e2e8f0;color:#94a3b8;font-size:11px;text-align:center;}}
    .pill{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;}}
    .pill-green{{background:#d1fae5;color:#059669;}}
    .pill-red{{background:#fee2e2;color:#dc2626;}}
    .pill-amber{{background:#fef3c7;color:#d97706;}}
    @media print{{body{{background:#fff;}} .page{{box-shadow:none;padding:24px;}}}}
  </style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="header">
    <h1>Business Intelligence & Analytics — Executive Report</h1>
    <div class="meta">{name} ({code}) · {period_label} · Generated {now_str}</div>
    <span class="badge">{badge.replace("_"," ")}</span>
  </div>

  <!-- 1. EXECUTIVE SUMMARY -->
  <div class="section">
    <h2>1. Executive Summary</h2>
    <div class="exec-box"><p>{exc['headline']}</p></div>
    <div class="grid4">
      <div class="kpi"><div class="kpi-label">CPI</div><div class="kpi-value" style="color:{'#059669' if evm['cpi']>=1 else '#dc2626'}">{evm['cpi']:.2f}</div><div class="kpi-sub">{'Within Budget' if evm['cpi']>=1 else 'Over Budget'}</div></div>
      <div class="kpi"><div class="kpi-label">SPI</div><div class="kpi-value" style="color:{'#059669' if evm['spi']>=1 else '#d97706'}">{evm['spi']:.2f}</div><div class="kpi-sub">{'On Schedule' if evm['spi']>=1 else 'Behind Schedule'}</div></div>
      <div class="kpi"><div class="kpi-label">Deviasi</div><div class="kpi-value" style="color:{'#059669' if prog['deviation_pct']>=0 else '#d97706'}">{prog['deviation_pct']:+.1f}%</div><div class="kpi-sub">Aktual vs Rencana</div></div>
      <div class="kpi"><div class="kpi-label">Velocity 7d</div><div class="kpi-value">{trend['velocity_7d_pct_per_day']}</div><div class="kpi-sub">%/hari rata-rata</div></div>
    </div>
  </div>

  <!-- 2. KPI & METRIK -->
  <div class="section">
    <h2>2. KPI & Metrik Bisnis</h2>
    <div class="grid3">
      <div class="kpi"><div class="kpi-label">Earned Value (EV)</div><div class="kpi-value">Rp {kpi['revenue_ev']:,.0f}</div><div class="kpi-sub">Budget × Aktual%</div></div>
      <div class="kpi"><div class="kpi-label">Actual Cost (AC)</div><div class="kpi-value">Rp {kpi['cost_ac']:,.0f}</div><div class="kpi-sub">Total pengeluaran nyata</div></div>
      <div class="kpi"><div class="kpi-label">Gross Profit (EV−AC)</div><div class="kpi-value" style="color:{'#059669' if kpi['gross_profit']>=0 else '#dc2626'}">Rp {kpi['gross_profit']:,.0f}</div><div class="kpi-sub">{'Surplus' if kpi['gross_profit']>=0 else 'Deficit'}</div></div>
    </div>
    <table>
      <thead><tr><th>Metrik</th><th>Nilai</th><th>Keterangan</th></tr></thead>
      <tbody>
        <tr><td>Profit Margin</td><td><b>{kpi['profit_margin_pct']:.1f}%</b></td><td>(EV−AC)/EV × 100</td></tr>
        <tr><td>Produktivitas</td><td><b>{kpi['productivity']:.2f}</b></td><td>% progres per 100 man-hours</td></tr>
        <tr><td>Target Fulfillment</td><td><b>{kpi['target_fulfillment_pct']:.1f}%</b></td><td>Aktual% / Rencana% × 100</td></tr>
        <tr><td>Total Man-Hours</td><td><b>{labor['total_man_hours']} hrs</b></td><td></td></tr>
        <tr><td>Rata-rata Kehadiran</td><td><b>{labor['avg_attendance_pct']}%</b></td><td></td></tr>
      </tbody>
    </table>
  </div>

  <!-- 3. EVM -->
  <div class="section">
    <h2>3. EVM KPIs — Target vs Actual</h2>
    <table>
      <thead><tr><th>Metrik</th><th>Target/Rencana</th><th>Aktual</th><th>Deviasi</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td>Progres Kumulatif</td><td>{prog['planned_pct']}%</td><td>{prog['actual_pct']}%</td><td><b style="color:{'#059669' if prog['deviation_pct']>=0 else '#d97706'}">{prog['deviation_pct']:+.2f}%</b></td><td><span class="pill {'pill-green' if prog['deviation_pct']>=0 else 'pill-amber'}">{'OK' if prog['deviation_pct']>=0 else 'GAP'}</span></td></tr>
        <tr><td>Planned Value (PV)</td><td>Rp {evm['pv']:,.0f}</td><td>Rp {evm['ev']:,.0f}</td><td><b style="color:{'#059669' if evm['sv']>=0 else '#d97706'}">Rp {evm['sv']:+,.0f}</b></td><td><span class="pill {'pill-green' if evm['sv']>=0 else 'pill-amber'}">{'OK' if evm['sv']>=0 else 'GAP'}</span></td></tr>
        <tr><td>Budget vs EAC</td><td>Rp {a['budget']:,.0f}</td><td>Rp {evm['eac']:,.0f}</td><td><b style="color:{'#059669' if evm['cv']>=0 else '#dc2626'}">Rp {evm['eac']-a['budget']:+,.0f}</b></td><td><span class="pill {'pill-green' if evm['cv']>=0 else 'pill-red'}">{'OK' if evm['cv']>=0 else 'OVER'}</span></td></tr>
        <tr><td>ETC (Sisa Biaya)</td><td colspan="2">Rp {evm['etc']:,.0f}</td><td colspan="2"><span class="pill pill-amber">Tersisa</span></td></tr>
      </tbody>
    </table>
  </div>

  <!-- 4. S-CURVE TREND -->
  <div class="section">
    <h2>4. Analisis Tren — Kurva S ({period_label})</h2>
    <table>
      <thead><tr><th>Tanggal</th><th>Rencana %</th><th>Aktual %</th><th>PV (Rp)</th><th>EV (Rp)</th><th>AC Kumulatif (Rp)</th><th>Biaya Harian (Rp)</th></tr></thead>
      <tbody>{_sc_html()}</tbody>
    </table>
  </div>

  <!-- 5. ROOT CAUSE ANALYSIS -->
  <div class="section">
    <h2>5. Analisis Penyebab (Root Cause Analysis)</h2>
    {_rca_html()}
  </div>

  <!-- 6. SEGMENTASI — MILESTONES -->
  <div class="section">
    <h2>6. Segmentasi — Milestones ({ms['completed']}/{ms['total']} selesai)</h2>
    {_ms_html()}
  </div>

  <!-- 7. FORECASTING -->
  <div class="section">
    <h2>7. Forecasting & Prediksi</h2>
    <div class="grid4">
      <div class="kpi"><div class="kpi-label">Est. Hari Selesai</div><div class="kpi-value">{'N/A' if fcast['est_days_to_complete']>=999 else fcast['est_days_to_complete']}</div><div class="kpi-sub">Berdasarkan velocity 7d</div></div>
      <div class="kpi"><div class="kpi-label">Proyeksi 30 Hari</div><div class="kpi-value">{fcast['forecast_30d_pct']}%</div><div class="kpi-sub">Prediksi progres</div></div>
      <div class="kpi"><div class="kpi-label">EAC Proyeksi</div><div class="kpi-value" style="font-size:14px;">Rp {fcast['projected_final_cost_eac']:,.0f}</div><div class="kpi-sub">Budget / CPI</div></div>
      <div class="kpi"><div class="kpi-label">Cost Overrun</div><div class="kpi-value" style="color:{'#dc2626' if fcast['cost_overrun_projected']>0 else '#059669'}">{'Rp '+f"{fcast['cost_overrun_projected']:,.0f}" if fcast['cost_overrun_projected']>0 else 'Tidak ada'}</div><div class="kpi-sub">max(0, EAC−Budget)</div></div>
    </div>
  </div>

  <!-- 8. ANOMALI -->
  <div class="section">
    <h2>8. Anomali & Exception Analysis ({len(anom)} temuan)</h2>
    {_anom_html()}
  </div>

  <!-- 9. REKOMENDASI -->
  <div class="section">
    <h2>9. Rekomendasi Tindakan</h2>
    {_recs_html()}
  </div>

  <!-- 10. DRILL-DOWN -->
  <div class="section">
    <h2>10. Drill-down Detail (10 Entri Terakhir)</h2>
    <table>
      <thead><tr><th>Tanggal</th><th>Rencana %</th><th>Aktual %</th><th>Deviasi</th><th>Biaya</th><th>HC</th><th>Jam</th></tr></thead>
      <tbody>{_drill_html()}</tbody>
    </table>
  </div>

  <!-- 11. METODOLOGI -->
  <div class="section">
    <h2>11. Data Source & Metodologi</h2>
    <table>
      <thead><tr><th>Item</th><th>Keterangan</th></tr></thead>
      <tbody>
        <tr><td>Framework</td><td>{meth['framework']}</td></tr>
        <tr><td>Sumber Data</td><td>{meth['data_source']}</td></tr>
        <tr><td>Periode</td><td>{period_label}</td></tr>
        <tr><td>Dihitung Pada</td><td>{meth['calculated_at']}</td></tr>
        <tr><td>CPI</td><td>EV/AC — &gt;1.0 under budget, &lt;1.0 over budget</td></tr>
        <tr><td>SPI</td><td>EV/PV — &gt;1.0 ahead of schedule, &lt;1.0 behind</td></tr>
        <tr><td>EAC</td><td>Budget/CPI — proyeksi biaya akhir</td></tr>
        <tr><td>Anomaly Detection</td><td>Cost spike &gt;2.2× rata-rata harian; Progress gap &gt;15%/hari</td></tr>
        <tr><td>Velocity 7d</td><td>Rata-rata kenaikan % aktual per hari, 7 hari terakhir</td></tr>
      </tbody>
    </table>
  </div>

  <div class="footer">
    Generated automatically by Alpha Business Intelligence & Analytics Engine · {now_str}
  </div>
</div>
</body>
</html>"""

        return {
            "project_id":        project_id,
            "period":            period_type_clean,
            "generated_at":      datetime.now().isoformat(),
            "markdown":          md,
            "html":              html,
            "analytics_snapshot": a,
        }

