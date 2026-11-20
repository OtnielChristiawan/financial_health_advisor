from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import owlready2
from owlready2 import World, sync_reasoner_pellet


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = PROJECT_ROOT / "Finance_Health_Expert_System_v2.owl"
ALLOWED_NUMBER_PROPERTIES = {
    "hasCOGSGrowth", "hasRevenueGrowth", "hasOPEXGrowth", "hasMarketingGrowth",
    "hasGrossMargin", "hasGrossMarginLowerBound", "hasNetProfit", "hasNetMargin",
    "hasNetMarginLowerBound", "hasChangeInCash", "hasOperatingCashFlow",
    "hasOwnerDrawAmount", "hasPreviousOwnerDrawAmount",
    "hasCashRunwayMonths", "hasRunwayMinimumMonths",
    "hasCapexAmount", "hasLoanPrincipalPaid", "hasEndingCash", "hasEquity",
}


def find_java() -> str:
    candidates = []
    configured = os.environ.get("JAVA25", "").strip()
    if configured:
        candidates.append(configured)
    candidates.extend(
        [
            "/usr/lib/jvm/java-25-openjdk-amd64/bin/java",
            "/usr/lib/jvm/java-25-openjdk/bin/java",
            "/opt/java25/bin/java",
            r"C:\Program Files\BellSoft\LibericaJDK-25\bin\java.exe",
            r"C:\Program Files\Zulu\zulu-25\bin\java.exe",
            r"C:\Program Files\Eclipse Adoptium\jdk-25\bin\java.exe",
            r"C:\Program Files\Microsoft\jdk-25\bin\java.exe",
            r"C:\Program Files\Java\jdk-25\bin\java.exe",
        ]
    )
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    java_on_path = shutil.which("java")
    if java_on_path:
        return java_on_path
    raise RuntimeError("Java 25+ tidak ditemukan. Install JDK 25 atau atur JAVA25.")


def java_version(executable: str) -> tuple[int, str]:
    result = subprocess.run(
        [executable, "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
    )
    match = re.search(r'"(\d+)', result.stdout)
    if not match:
        raise RuntimeError("Versi Java tidak dapat dibaca.")
    major = int(match.group(1))
    if major < 25:
        raise RuntimeError(f"Java {major} ditemukan; reasoning membutuhkan Java 25+.")
    return major, f"Java {major}"


JAVA_EXE = find_java()
JAVA_MAJOR, JAVA_VERSION = java_version(JAVA_EXE)
owlready2.JAVA_EXE = JAVA_EXE


def _valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


_ONTOLOGY_CACHE: dict[str, Any] | None = None


def get_ontology_knowledge() -> tuple[dict[str, dict[str, Any]], dict[str, float]]:
    global _ONTOLOGY_CACHE
    if _ONTOLOGY_CACHE is not None:
        return _ONTOLOGY_CACHE["findings"], _ONTOLOGY_CACHE["policy"]

    if not ONTOLOGY_PATH.is_file():
        raise FileNotFoundError(f"Ontology tidak ditemukan: {ONTOLOGY_PATH}")

    world = World()
    onto = world.get_ontology("file://" + str(ONTOLOGY_PATH)).load()

    findings_meta: dict[str, dict[str, Any]] = {}
    for cls in onto.classes():
        title = getattr(cls, "hasTitle", None)
        if title:
            fid = cls.name
            t_val = title[0] if isinstance(title, list) else str(title)
            dom_val = getattr(cls, "hasDomain", ["Umum"])
            dom_val = dom_val[0] if isinstance(dom_val, list) else str(dom_val)
            sev_val = getattr(cls, "hasSeverity", ["Waspada"])
            sev_val = sev_val[0] if isinstance(sev_val, list) else str(sev_val)
            rule_val = getattr(cls, "hasRuleId", [fid])
            rule_val = rule_val[0] if isinstance(rule_val, list) else str(rule_val)
            exp_val = getattr(cls, "hasExplanationText", [""])
            exp_val = exp_val[0] if isinstance(exp_val, list) else str(exp_val)
            adv_val = getattr(cls, "hasAdviceText", [""])
            adv_val = adv_val[0] if isinstance(adv_val, list) else str(adv_val)
            chain_vals = getattr(cls, "hasChainStep", [])
            raw_steps = [str(x) for x in chain_vals]
            sorted_steps = sorted(
                [(int(x.split(":", 1)[0]), x.split(":", 1)[1]) for x in raw_steps if ":" in x],
                key=lambda item: item[0],
            )
            chain = [s[1] for s in sorted_steps] if sorted_steps else raw_steps
            findings_meta[fid] = {
                "title": str(t_val),
                "domain": str(dom_val),
                "severity": str(sev_val),
                "rule": str(rule_val),
                "explanation": str(exp_val),
                "chain": chain,
                "advice": str(adv_val),
            }

    policy_dict: dict[str, float] = {
        "gross_margin_tolerance": 0.03,
        "net_margin_tolerance": 0.03,
        "cash_materiality_threshold": 1000000.0,
        "runway_minimum_months": 2.0,
    }
    p_def = getattr(onto, "Policy_Default", None)
    if p_def:
        if hasattr(p_def, "hasGrossMarginTolerance") and p_def.hasGrossMarginTolerance:
            val = p_def.hasGrossMarginTolerance[0] if isinstance(p_def.hasGrossMarginTolerance, list) else p_def.hasGrossMarginTolerance
            policy_dict["gross_margin_tolerance"] = float(val)
        if hasattr(p_def, "hasNetMarginTolerance") and p_def.hasNetMarginTolerance:
            val = p_def.hasNetMarginTolerance[0] if isinstance(p_def.hasNetMarginTolerance, list) else p_def.hasNetMarginTolerance
            policy_dict["net_margin_tolerance"] = float(val)
        if hasattr(p_def, "hasCashMaterialityThreshold") and p_def.hasCashMaterialityThreshold:
            val = p_def.hasCashMaterialityThreshold[0] if isinstance(p_def.hasCashMaterialityThreshold, list) else p_def.hasCashMaterialityThreshold
            policy_dict["cash_materiality_threshold"] = float(val)
        if hasattr(p_def, "hasRunwayMinimumMonths") and p_def.hasRunwayMinimumMonths:
            val = p_def.hasRunwayMinimumMonths[0] if isinstance(p_def.hasRunwayMinimumMonths, list) else p_def.hasRunwayMinimumMonths
            policy_dict["runway_minimum_months"] = float(val)

    _ONTOLOGY_CACHE = {
        "findings": findings_meta,
        "policy": policy_dict,
    }
    return findings_meta, policy_dict


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    states_input = payload.get("states")
    if states_input is not None:
        if not isinstance(states_input, list) or not states_input:
            raise ValueError("'states' harus berupa daftar non-kosong.")
        for st in states_input:
            if not isinstance(st, dict):
                raise ValueError("Setiap elemen 'states' harus berupa objek.")
            nums = st.get("numbers", {})
            movs = st.get("movements", [])
            if not isinstance(nums, dict) or not isinstance(movs, list):
                raise ValueError("'numbers' harus objek dan 'movements' harus berupa daftar.")
            unknown = set(nums) - ALLOWED_NUMBER_PROPERTIES
            if unknown:
                raise ValueError(f"Properti indikator tidak dikenal: {', '.join(sorted(unknown))}.")
            if any(not _valid_number(value) for value in nums.values()):
                raise ValueError("Semua indikator harus berupa angka finite.")
            for m in movs:
                if (
                    not isinstance(m, dict)
                    or not isinstance(m.get("name"), str)
                    or not m["name"].strip()
                    or len(m["name"]) > 80
                    or not _valid_number(m.get("growth"))
                    or not isinstance(m.get("is_top"), bool)
                ):
                    raise ValueError("Format pergerakan kategori tidak valid.")
    else:
        numbers = payload.get("numbers", {})
        movements = payload.get("movements", [])
        if not isinstance(numbers, dict) or not isinstance(movements, list):
            raise ValueError("'numbers' harus objek dan 'movements' harus berupa daftar.")
        unknown = set(numbers) - ALLOWED_NUMBER_PROPERTIES
        if unknown:
            raise ValueError(f"Properti indikator tidak dikenal: {', '.join(sorted(unknown))}.")
        if any(not _valid_number(value) for value in numbers.values()):
            raise ValueError("Semua indikator harus berupa angka finite.")
        for movement in movements:
            if (
                not isinstance(movement, dict)
                or not isinstance(movement.get("name"), str)
                or not movement["name"].strip()
                or len(movement["name"]) > 80
                or not _valid_number(movement.get("growth"))
                or not isinstance(movement.get("is_top"), bool)
            ):
                raise ValueError("Format pergerakan kategori tidak valid.")
        states_input = [
            {
                "id": "Web_Analysis",
                "period": "Period_Current",
                "numbers": numbers,
                "movements": movements,
                "is_current": True,
            }
        ]

    if not ONTOLOGY_PATH.is_file():
        raise FileNotFoundError(f"Ontology tidak ditemukan: {ONTOLOGY_PATH}")

    t0 = time.perf_counter()
    world = World()
    ontology = world.get_ontology("file://" + str(ONTOLOGY_PATH)).load()
    t_load = time.perf_counter()

    with ontology:
        biz = ontology.Business(payload.get("business_name") or "Web_Business")
        created_states = []
        prev_state_ind = None
        prev_period_ind = None
        current_state_ind = None

        for idx, st in enumerate(states_input):
            st_id = st.get("id") or f"Web_State_{idx}"
            period_name = st.get("period") or f"Web_Period_{idx}"
            period_ind = ontology.Period(period_name)
            state_ind = ontology.MonthlyFinancialState(st_id)
            state_ind.forPeriod = period_ind

            for prop_name, val in st.get("numbers", {}).items():
                setattr(state_ind, prop_name, float(val))

            category_individuals = []
            for m_idx, mov in enumerate(st.get("movements", [])):
                cat = ontology.CategoryMovement(f"{st_id}_Mov_{m_idx}")
                cat.hasCategoryName = mov["name"]
                cat.hasCategoryGrowth = float(mov["growth"])
                cat.isTopContributor = mov["is_top"]
                category_individuals.append(cat)
            if category_individuals:
                state_ind.hasCategoryMovement = category_individuals

            if prev_state_ind is not None:
                state_ind.comparedWith = prev_state_ind
            if prev_period_ind is not None:
                period_ind.previousPeriod = prev_period_ind

            created_states.append(state_ind)
            if st.get("is_current", idx == len(states_input) - 1):
                current_state_ind = state_ind

            prev_state_ind = state_ind
            prev_period_ind = period_ind

        biz.hasState = created_states
        biz.hasCurrentState = current_state_ind or created_states[-1]

    t_assert = time.perf_counter()

    with ontology:
        sync_reasoner_pellet(
            world,
            infer_property_values=True,
            infer_data_property_values=True,
            debug=0,
        )

    t_pellet = time.perf_counter()

    target_state = current_state_ind or created_states[-1]
    inferred = sorted(entity.name for entity in target_state.INDIRECT_is_a if hasattr(entity, "name"))
    business_classes = sorted(entity.name for entity in biz.INDIRECT_is_a if hasattr(entity, "name"))
    persistent_findings = [c for c in inferred if "Persistent" in c]
    recommendations = sorted({
        str(area.label.first() or area.name) for area in target_state.recommendsInvestigation
    })
    cost_drivers = sorted(
        movement.hasCategoryName
        for movement in target_state.hasCostDriver
        if movement.hasCategoryName
    )

    timings = {
        "load_ms": round((t_load - t0) * 1000),
        "assert_ms": round((t_assert - t_load) * 1000),
        "pellet_ms": round((t_pellet - t_assert) * 1000),
        "total_ms": round((t_pellet - t0) * 1000),
    }

    return {
        "engine": "OWL + SWRL / Pellet",
        "java": JAVA_VERSION,
        "elapsed_ms": timings["total_ms"],
        "timings": timings,
        "inferred": inferred,
        "business_classes": business_classes,
        "persistent_findings": persistent_findings,
        "recommendations": recommendations,
        "cost_drivers": cost_drivers,
    }


def _format_money(value: float | int) -> str:
    val = float(value)
    if abs(val) >= 1_000_000:
        return f"Rp{val / 1_000_000:.1f} jt"
    return f"Rp{val:,.0f}"


def _format_pct(val: float | None) -> str:
    if val is None or not math.isfinite(val):
        return "—"
    sign = "+" if val > 0 else ""
    return f"{sign}{val * 100:.1f}%"


def diagnose_finance(report: dict[str, Any], previous_report: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Authoritative OWL/SWRL diagnosis generator.
    Evaluates data completeness, prepares parameters, runs Pellet reasoner,
    and returns explainable signals with Indonesian recommendations.
    """
    findings_metadata, policy = get_ontology_knowledge()

    prev = report.get("previous")
    rev = float(report.get("revenue") or 0)
    prev_rev = float(prev.get("revenue") or 0) if prev else 0.0

    is_comparable = bool(prev and prev_rev > 0 and rev > 0)
    is_provisional = bool(report.get("isProvisional", False))
    is_closed = bool(report.get("isClosed", False))

    notes = []
    if not prev:
        notes.append("Data transaksi bulan sebelumnya belum tersedia; aturan perbandingan tren belum dapat dijalankan.")
    elif prev_rev <= 0:
        notes.append("Pendapatan bulan pembanding nihil; pertumbuhan persentase tidak dapat dihitung.")
    if rev <= 0:
        notes.append("Belum ada omzet penjualan tercatat pada periode ini; rasio margin belum dapat dievaluasi.")
    if is_provisional:
        notes.append("Laporan masih berstatus estimasi/belum tutup buku fisik; angka HPP dan laba belum final.")

    if not is_comparable:
        return {
            "status": "DATA_TIDAK_CUKUP",
            "status_label": "Data Belum Cukup",
            "level": "limited",
            "summary": "Sistem membutuhkan data minimal 2 bulan transaksi berurutan untuk menganalisis tren dan sinyal kesehatan keuangan secara andal.",
            "data_completeness": {
                "is_comparable": False,
                "has_previous": bool(prev),
                "is_provisional": is_provisional,
                "is_closed": is_closed,
                "notes": notes,
            },
            "findings": [],
            "why_not": [
                "Aturan inferensi SWRL berbasis komparasi tren (pertumbuhan omzet, margin, dan biaya) membutuhkan data bulan sebelumnya.",
                "Sistem menganut Open World Assumption: ketiadaan data tidak dianggap sebagai kondisi sehat.",
            ],
            "cost_drivers": [],
            "recommendations": [
                "Lengkapi pencatatan transaksi untuk minimal 2 bulan berurutan.",
                "Lakukan stock opname fisik di menu Tutup Buku untuk menetapkan HPP yang akurat.",
            ],
            "inferred_classes": [],
            "business_status": [],
            "persistent_findings": [],
            "timings": {"load_ms": 0, "assert_ms": 0, "pellet_ms": 0, "total_ms": 0},
            "engine": "OWL + SWRL / Pellet",
            "elapsed_ms": 0,
        }

    # Prepare numbers for ontology
    rev_growth = (rev - prev_rev) / prev_rev
    cogs = float(report.get("cogs") or 0)
    prev_cogs = float(prev.get("cogs") or 0)
    cogs_growth = (cogs - prev_cogs) / prev_cogs if prev_cogs > 0 else 0.0

    opex = float(report.get("opex") or 0)
    prev_opex = float(prev.get("opex") or 0)
    opex_growth = (opex - prev_opex) / prev_opex if prev_opex > 0 else 0.0

    mkt = float(report.get("marketing") or 0)
    prev_mkt = float(prev.get("marketing") or 0)
    mkt_growth = (mkt - prev_mkt) / prev_mkt if prev_mkt > 0 else 0.0

    gross_margin = report.get("grossMargin")
    prev_gross_margin = prev.get("grossMargin")

    net_margin = report.get("netMargin")
    prev_net_margin = prev.get("netMargin")

    net_profit = float(report.get("netProfit") or 0)
    change_cash = float(report.get("changeCash") or 0)
    ocf = float(report.get("operatingCashFlow") or 0)
    equity = float(report.get("equity") or 0)

    rows = report.get("rows") or []
    prev_rows = prev.get("rows") or []

    owner_draw = sum(float(r["amount"]) for r in rows if r.get("kind") == "draw")
    prev_owner_draw = sum(float(r["amount"]) for r in prev_rows if r.get("kind") == "draw")

    raw_runway = report.get("cashRunwayMonths")
    cash_runway = float(raw_runway) if raw_runway is not None else 99.0
    raw_min = report.get("runwayMinimumMonths")
    runway_min = float(raw_min) if raw_min is not None else policy["runway_minimum_months"]

    # Threshold toleransi praktis bisnis dibaca dari Policy Parameter ontologi
    margin_tolerance = policy["gross_margin_tolerance"]
    net_margin_tolerance = policy["net_margin_tolerance"]
    cash_materiality = policy["cash_materiality_threshold"]

    material_change_cash = change_cash if change_cash < -cash_materiality else (change_cash if change_cash > 0 else 0.0)
    effective_runway = cash_runway if (change_cash < -cash_materiality and net_profit < 0) else 99.0

    numbers: dict[str, float] = {
        "hasRevenueGrowth": rev_growth,
        "hasCOGSGrowth": cogs_growth,
        "hasOPEXGrowth": opex_growth,
        "hasMarketingGrowth": mkt_growth,
        "hasNetProfit": net_profit,
        "hasChangeInCash": material_change_cash,
        "hasOperatingCashFlow": ocf,
        "hasOwnerDrawAmount": owner_draw,
        "hasPreviousOwnerDrawAmount": prev_owner_draw,
        "hasCashRunwayMonths": effective_runway,
        "hasRunwayMinimumMonths": runway_min,
        "hasEquity": equity,
    }
    if gross_margin is not None and prev_gross_margin is not None:
        numbers["hasGrossMargin"] = float(gross_margin)
        numbers["hasGrossMarginLowerBound"] = float(prev_gross_margin) - margin_tolerance
    if net_margin is not None and prev_net_margin is not None:
        numbers["hasNetMargin"] = float(net_margin)
        numbers["hasNetMarginLowerBound"] = float(prev_net_margin) - net_margin_tolerance

    # Cost movements for profit bridge & cost driver rule
    candidates = [
        ("COGS", cogs, prev_cogs),
        ("OPEX", opex, prev_opex),
        ("Marketing", mkt, prev_mkt),
    ]
    valid_candidates = [c for c in candidates if c[2] > 0]
    top_name = None
    if valid_candidates:
        top_name = max(valid_candidates, key=lambda c: c[1] - c[2])[0]

    movements = []
    for name, cur_val, p_val in valid_candidates:
        growth = (cur_val - p_val) / p_val
        is_top = (name == top_name and cur_val > p_val)
        movements.append({"name": name, "growth": growth, "is_top": is_top})

    # Prepare multi-state if previous month report is available
    if previous_report and isinstance(previous_report, dict):
        p_prev = previous_report.get("previous")
        p_rev = float(previous_report.get("revenue") or 0)
        p_prev_rev = float(p_prev.get("revenue") or 0) if p_prev else 0.0
        p_cogs = float(previous_report.get("cogs") or 0)
        p_prev_cogs = float(p_prev.get("cogs") or 0) if p_prev else 0.0
        p_gm = previous_report.get("grossMargin")
        p_prev_gm = p_prev.get("grossMargin") if p_prev else None
        p_equity = float(previous_report.get("equity") or 0)

        prev_numbers: dict[str, float] = {
            "hasEquity": p_equity,
        }
        if p_prev_rev > 0 and p_rev > 0:
            prev_numbers["hasRevenueGrowth"] = (p_rev - p_prev_rev) / p_prev_rev
        if p_prev_cogs > 0 and p_cogs > 0:
            prev_numbers["hasCOGSGrowth"] = (p_cogs - p_prev_cogs) / p_prev_cogs
        if p_gm is not None and p_prev_gm is not None:
            prev_numbers["hasGrossMargin"] = float(p_gm)
            prev_numbers["hasGrossMarginLowerBound"] = float(p_prev_gm) - margin_tolerance

        reasoner_payload = {
            "states": [
                {
                    "id": "State_Previous",
                    "period": previous_report.get("month", "Period_Prev"),
                    "numbers": prev_numbers,
                    "movements": [],
                    "is_current": False,
                },
                {
                    "id": "State_Current",
                    "period": report.get("month", "Period_Current"),
                    "numbers": numbers,
                    "movements": movements,
                    "is_current": True,
                },
            ]
        }
    else:
        reasoner_payload = {"numbers": numbers, "movements": movements}

    # Invoke Pellet reasoner with Fallback for reasoner/Java errors
    try:
        reasoner_res = analyze(reasoner_payload)
    except Exception as err:
        return {
            "status": "REASONER_ERROR",
            "status_label": "Penalaran Terkendala",
            "level": "warning",
            "summary": f"Reasoner mengalami kendala pada penalaran ontologi: {str(err)}",
            "data_completeness": {
                "is_comparable": is_comparable,
                "has_previous": bool(prev),
                "is_provisional": is_provisional,
                "is_closed": is_closed,
                "notes": notes + [f"Reasoner error: {str(err)}"],
            },
            "findings": [],
            "why_not": [f"Terjadi kesalahan saat mengeksekusi reasoner Pellet: {str(err)}"],
            "cost_drivers": [],
            "recommendations": ["Periksa kembali data numerik input atau restart engine reasoner."],
            "inferred_classes": [],
            "business_status": [],
            "persistent_findings": [],
            "timings": {"load_ms": 0, "assert_ms": 0, "pellet_ms": 0, "total_ms": 0},
            "engine": "OWL + SWRL / Pellet",
            "elapsed_ms": 0,
        }

    inferred_set = set(reasoner_res.get("inferred", []))
    business_status = reasoner_res.get("business_classes", [])
    persistent_findings = reasoner_res.get("persistent_findings", [])

    findings = []
    for fid, meta in findings_metadata.items():
        if fid in inferred_set:
            # Build specific numeric evidence
            evidence = []
            if fid in ("CostEscalation", "MarginPressure"):
                evidence = [
                    ["Pertumbuhan omzet", _format_pct(rev_growth)],
                    ["Pertumbuhan COGS", _format_pct(cogs_growth)],
                    ["Gross margin periode ini", _format_pct(gross_margin)],
                    ["Gross margin baseline lalu", _format_pct(prev_gross_margin)],
                ]
            elif fid == "OPEXPressure":
                evidence = [
                    ["Pertumbuhan omzet", _format_pct(rev_growth)],
                    ["Pertumbuhan OPEX", _format_pct(opex_growth)],
                    ["Total OPEX periode ini", _format_money(opex)],
                ]
            elif fid == "MarketingEfficiencyReview":
                evidence = [
                    ["Pertumbuhan omzet", _format_pct(rev_growth)],
                    ["Pertumbuhan biaya pemasaran", _format_pct(mkt_growth)],
                    ["Biaya pemasaran periode ini", _format_money(mkt)],
                ]
            elif fid == "ProfitPressure":
                evidence = [
                    ["Net margin periode ini", _format_pct(net_margin)],
                    ["Net margin baseline lalu", _format_pct(prev_net_margin)],
                    ["Laba bersih tercatat", _format_money(net_profit)],
                ]
            elif fid == "ProfitCashGap":
                evidence = [
                    ["Laba bersih tercatat", _format_money(net_profit)],
                    ["Perubahan kas bersih", _format_money(change_cash)],
                    ["Arus kas operasi", _format_money(ocf)],
                    ["Penarikan prive pemilik", _format_money(owner_draw)],
                ]
            elif fid == "LiquidityPressure":
                evidence = [
                    ["Perubahan kas bersih", _format_money(change_cash)],
                    ["Saldo kas & bank akhir", _format_money(report.get("cashClosing", 0))],
                    ["Arus kas operasi", _format_money(ocf)],
                ]
            elif fid == "OwnerDrawLiquidityPressure":
                evidence = [
                    ["Prive periode ini", _format_money(owner_draw)],
                    ["Prive bulan sebelumnya", _format_money(prev_owner_draw)],
                    ["Arus kas operasi (OCF)", _format_money(ocf)],
                    ["Perubahan kas bersih", _format_money(change_cash)],
                ]
            elif fid == "LiquidityCritical":
                runway_days = int(round(cash_runway * 30))
                min_days = int(round(runway_min * 30))
                evidence = [
                    ["Estimasi cadangan kas (runway)", f"{runway_days} hari ({cash_runway:.1f} bulan)"],
                    ["Batas aman minimum (policy)", f"{min_days} hari ({runway_min:.1f} bulan)"],
                    ["Perubahan kas periode ini", _format_money(change_cash)],
                    ["Saldo kas akhir", _format_money(report.get("cashClosing", 0))],
                ]
            elif fid == "NegativeEquityState":
                evidence = [
                    ["Total ekuitas tercatat", _format_money(equity)],
                    ["Status solvabilitas", "Defisit Modal (Ekuitas Negatif / Technically Insolvent)"],
                    ["Catatan kepatuhan", "Indikasi teknis akuntansi SAK EMKM, bukan nasihat hukum."],
                ]
            elif fid == "PersistentMarginPressure":
                evidence = [
                    ["Gross margin periode ini", _format_pct(gross_margin)],
                    ["Gross margin periode lalu", _format_pct(prev_gross_margin)],
                    ["Persistensi", "Tekanan margin berulang selama 2 bulan berturut-turut"],
                ]

            # Construct dynamic explanation chain from inferred intermediate classes
            chain = []
            if fid == "MarginPressure":
                if "COGSGrowthExceedsRevenue" in inferred_set:
                    chain.append("Fakta terverifikasi: Pertumbuhan COGS melebihi pertumbuhan omzet.")
                if "GrossMarginDecline" in inferred_set:
                    chain.append("Fakta terverifikasi: Gross margin turun melampaui ambang batas toleransi.")
                chain.append("Disimpulkan: Terjadi tekanan margin kotor (Margin Pressure).")
                chain.append("Aksi rekomendasi: Evaluasi harga jual menu & audit bauran produk (product mix).")
            elif fid == "CostEscalation":
                if "COGSGrowthExceedsRevenue" in inferred_set:
                    chain.append("Fakta terverifikasi: Pertumbuhan biaya bahan baku (COGS) melampaui omzet.")
                chain.append("Disimpulkan: Eskalasi biaya bahan baku terkonfirmasi.")
                chain.append("Aksi rekomendasi: Tinjau harga supplier, waste bar/kitchen, dan porsi resep menu.")
            elif fid == "OPEXPressure":
                if "OPEXGrowthExceedsRevenue" in inferred_set:
                    chain.append("Fakta terverifikasi: Beban operasional (OPEX) tumbuh lebih cepat dari omzet.")
                chain.append("Disimpulkan: Efisiensi beban operasional terganggu.")
                chain.append("Aksi rekomendasi: Audit pos beban operasional non-marketing terbesar.")
            elif fid == "MarketingEfficiencyReview":
                if "MarketingGrowthExceedsRevenue" in inferred_set:
                    chain.append("Fakta terverifikasi: Beban promosi/pemasaran tumbuh melampaui pertumbuhan omzet.")
                chain.append("Disimpulkan: Pengeluaran pemasaran memerlukan tinjauan efisiensi.")
                chain.append("Aksi rekomendasi: Optimalkan kanal promosi yang terbukti menghasilkan penjualan langsung.")
            elif fid == "ProfitPressure":
                if "NetMarginDecline" in inferred_set:
                    chain.append("Fakta terverifikasi: Margin laba bersih turun di bawah ambang batas toleransi.")
                chain.append("Disimpulkan: Terjadi tekanan pada margin laba bersih.")
                chain.append("Aksi rekomendasi: Telusuri kebocoran pos pengeluaran dan beban usaha insidental.")
            elif fid == "ProfitCashGap":
                if "PositiveProfit" in inferred_set:
                    chain.append("Fakta terverifikasi: Usaha mencatat laba bersih positif.")
                if "CashDecline" in inferred_set:
                    chain.append("Fakta terverifikasi: Saldo kas mengalami penurunan bersih.")
                chain.append("Disimpulkan: Kesenjangan laba vs arus kas nyata.")
                chain.append("Aksi rekomendasi: Telusuri arus kas keluar untuk prive pemilik, aset tetap, atau utang.")
            elif fid == "LiquidityPressure":
                if "CashDecline" in inferred_set:
                    chain.append("Fakta terverifikasi: Saldo kas dan rekening bank mengalami penurunan bersih.")
                chain.append("Disimpulkan: Tekanan likuiditas kas aktif.")
                chain.append("Aksi rekomendasi: Disiplinkan penerimaan dan kendalikan jadwal pengeluaran kas.")
            elif fid == "OwnerDrawLiquidityPressure":
                chain.append("Fakta terverifikasi: Prive pemilik naik dan melampaui kemampuan arus kas operasi.")
                if "CashDecline" in inferred_set:
                    chain.append("Fakta terverifikasi: Penurunan saldo kas terjadi bersamaan dengan tarikan prive.")
                chain.append("Disimpulkan: Penarikan prive menggerus posisi likuiditas usaha.")
                chain.append("Aksi rekomendasi: Batasi penarikan kas pribadi demi menjaga kelangsungan operasional.")
            elif fid == "LiquidityCritical":
                if "LiquidityPressure" in inferred_set or "CashDecline" in inferred_set:
                    chain.append("Fakta terverifikasi: Saldo kas menurun.")
                chain.append(f"Fakta terverifikasi: Cadangan kas runway ({cash_runway:.1f} bln) di bawah batas aman ({runway_min:.1f} bln).")
                chain.append("Disimpulkan: Risiko krisis likuiditas darurat.")
                chain.append("Aksi rekomendasi darurat: Moratorium prive, tunda pembelian aset, prioritaskan gaji dan bahan baku.")
            elif fid == "MultidimensionalDistress":
                chain.append("Fakta terverifikasi: Terjadi komplikasi simultan (Margin Pressure + OPEX Pressure + Liquidity Pressure).")
                chain.append("Disimpulkan: Distres operasional multi-dimensi.")
                chain.append("Aksi rekomendasi darurat: Restrukturisasi biaya menyeluruh dan moratorium penarikan non-operasional.")
            elif fid == "PersistentMarginPressure":
                chain.append("Fakta terverifikasi: Gross margin bulan ini tertekan di bawah baseline historis.")
                chain.append("Fakta terverifikasi: Gross margin bulan sebelumnya juga tercatat dalam tekanan margin.")
                chain.append("Disimpulkan: Persistensi tekanan margin antar-periode terdeteksi.")
                chain.append("Aksi rekomendasi: Lakukan langkah strategis penyesuaian harga menu dan renegosiasi kontrak supplier.")
            elif fid == "NegativeEquityState":
                chain.append("Fakta terverifikasi: Total kewajiban usaha melebihi total aset.")
                chain.append("Fakta terverifikasi: Ekuitas tercatat bernilai negatif (< 0).")
                chain.append("Disimpulkan: Kondisi defisit modal akumulasi (technically insolvent).")
                chain.append("Aksi rekomendasi: Injeksi modal pemilik atau restrukturisasi kewajiban usaha.")
            else:
                chain = meta.get("chain", [])

            findings.append({
                "id": fid,
                "title": meta["title"],
                "domain": meta["domain"],
                "severity": meta["severity"],
                "rule": meta["rule"],
                "explanation": meta["explanation"],
                "evidence": evidence,
                "chain": chain,
                "advice": meta["advice"],
                "is_persistent": (fid == "MarginPressure" and "PersistentMarginPressure" in inferred_set),
            })

    # Determine overall status
    has_critical = any(f["severity"] == "Kritis" for f in findings) or ("DistressedBusiness" in business_status)
    has_warning = any(f["severity"] == "Waspada" for f in findings)

    if has_critical:
        status = "KRITIS"
        status_label = "Kondisi Kritis"
        level = "critical"
        summary = f"Terdeteksi {len(findings)} indikasi risiko keuangan, termasuk risiko kritis yang membutuhkan tindakan penanganan darurat segera."
    elif has_warning:
        status = "WASPADA"
        status_label = "Perlu Diperiksa"
        level = "warning"
        summary = f"Terdeteksi {len(findings)} indikasi perhatian keuangan berdasarkan penalaran aturan SWRL/OWL. Telusuri bukti dan rekomendasi di bawah."
    else:
        status = "SEHAT"
        status_label = "Kondisi Sehat"
        level = "healthy"
        summary = "Tidak ada indikasi risiko signifikan yang terdeteksi oleh aturan SWRL/OWL. Rasio margin, biaya, dan likuiditas berada dalam batas wajar historis."

    why_not = []
    for fid, meta in findings_metadata.items():
        if fid not in inferred_set:
            if fid == "CostEscalation":
                why_not.append("CostEscalation tidak disimpulkan karena pertumbuhan COGS tidak melebihi pertumbuhan omzet.")
            elif fid == "MarginPressure":
                why_not.append("MarginPressure tidak disimpulkan karena gross margin tidak turun di bawah baseline historis bersamaan dengan eskalasi COGS.")
            elif fid == "OPEXPressure":
                why_not.append("OPEXPressure tidak disimpulkan karena beban operasional tumbuh terkendali di bawah omzet.")
            elif fid == "LiquidityCritical":
                why_not.append(f"LiquidityCritical tidak disimpulkan karena cadangan kas ({int(round(cash_runway * 30))} hari / {cash_runway:.1f} bulan) masih berada di atas batas minimum {int(round(runway_min * 30))} hari ({runway_min:.1f} bulan).")
            elif fid == "OwnerDrawLiquidityPressure":
                why_not.append("OwnerDrawPressure tidak disimpulkan karena penarikan prive pemilik masih tertutup oleh arus kas operasional.")
            elif fid == "PersistentMarginPressure" and "MarginPressure" in inferred_set:
                why_not.append("PersistentMarginPressure tidak disimpulkan karena tekanan margin belum terbukti terjadi secara berulang lintas periode.")

    return {
        "status": status,
        "status_label": status_label,
        "level": level,
        "summary": summary,
        "data_completeness": {
            "is_comparable": is_comparable,
            "has_previous": bool(prev),
            "is_provisional": is_provisional,
            "is_closed": is_closed,
            "notes": notes,
        },
        "findings": findings,
        "why_not": why_not[:4],
        "cost_drivers": reasoner_res.get("cost_drivers", []),
        "recommendations": reasoner_res.get("recommendations", []),
        "inferred_classes": sorted(list(inferred_set)),
        "business_status": business_status,
        "persistent_findings": persistent_findings,
        "timings": reasoner_res.get("timings", {}),
        "engine": "OWL + SWRL / Pellet",
        "elapsed_ms": reasoner_res.get("elapsed_ms", 0),
    }


def __getattr__(name: str) -> Any:
    if name == "FINDING_METADATA":
        meta, _ = get_ontology_knowledge()
        return meta
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

