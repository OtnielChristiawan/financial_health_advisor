import re
from decimal import Decimal
from rdflib import Graph, Namespace, URIRef, Literal, BNode, RDF, RDFS, OWL, XSD

BASE = "http://www.semanticweb.org/otniel/ontologies/2026/9/financial-health-expert-system"
NS = Namespace(BASE + "#")
SWRL = Namespace("http://www.w3.org/2003/11/swrl#")
SWRLB = Namespace("http://www.w3.org/2003/11/swrlb#")
SWRLA = Namespace("http://swrl.stanford.edu/ontologies/3.3/swrla.owl#")

g = Graph()
g_demo = Graph()
for p, n in [("", NS), ("owl", OWL), ("rdf", RDF), ("rdfs", RDFS), ("xsd", XSD),
             ("swrl", SWRL), ("swrlb", SWRLB), ("swrla", SWRLA)]:
    g.bind(p, n)
    g_demo.bind(p, n)

CLASSES, OPROPS, DPROPS = set(), set(), set()


def split_camel(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ")


def lab(node, text, lang="en"):
    g.add((node, RDFS.label, Literal(text, lang=lang)))


def com(node, text):
    g.add((node, RDFS.comment, Literal(text, lang="en")))


def cls(name, parent=None, comment=None):
    c = NS[name]
    CLASSES.add(name)
    g.add((c, RDF.type, OWL.Class))
    lab(c, split_camel(name))
    for p in ([] if parent is None else parent if isinstance(parent, list) else [parent]):
        g.add((c, RDFS.subClassOf, NS[p]))
    if comment:
        com(c, comment)
    return c


def oprop(name, dom, rng, comment=None, functional=False, inverse=None):
    p = NS[name]
    OPROPS.add(name)
    g.add((p, RDF.type, OWL.ObjectProperty))
    lab(p, split_camel(name))
    g.add((p, RDFS.domain, NS[dom]))
    g.add((p, RDFS.range, NS[rng]))
    if functional:
        g.add((p, RDF.type, OWL.FunctionalProperty))
    if inverse:
        g.add((p, OWL.inverseOf, NS[inverse]))
    if comment:
        com(p, comment)


def dprop(name, dom, xsd, comment=None, functional=True):
    p = NS[name]
    DPROPS.add(name)
    g.add((p, RDF.type, OWL.DatatypeProperty))
    lab(p, split_camel(name))
    if dom:
        g.add((p, RDFS.domain, NS[dom]))
    g.add((p, RDFS.range, xsd))
    if functional:
        g.add((p, RDF.type, OWL.FunctionalProperty))
    if comment:
        com(p, comment)


def dec(x):
    return Literal(Decimal(str(round(x, 6))), datatype=XSD.decimal)


def ind(name, types, label=None, target_graph=g):
    i = NS[name]
    target_graph.add((i, RDF.type, OWL.NamedIndividual))
    for t in ([types] if isinstance(types, str) else types):
        target_graph.add((i, RDF.type, NS[t]))
    if label:
        target_graph.add((i, RDFS.label, Literal(label, lang="id")))
    return i


# ------------------------------------------------------------------ ontology header
onto = URIRef(BASE)
g.add((onto, RDF.type, OWL.Ontology))
g.add((onto, OWL.versionInfo, Literal("2.1.0")))
g.add((onto, RDFS.label, Literal("Financial Health Expert System for F&B MSMEs")))
g.add((onto, RDFS.comment, Literal(
    "Knowledge base for diagnosing the financial health of small F&B businesses. "
    "Numbers (growth, margins, baseline bounds, cash change) are computed by the backend and "
    "asserted on a MonthlyFinancialState individual; SWRL rules compare them and the reasoner "
    "classifies the state. v2: BusinessProfile removed (F&B only), per-month state added, "
    "SWRL variables correctly typed swrl:Variable, numeric comparison moved into SWRL. "
    "v2.1: reseller/segment analysis removed for the MVP (rules use total figures and the business's own baseline).")))

for ap in ["sourceStatus", "sourceNote", "hasTitle", "hasDomain", "hasSeverity", "hasRuleId", "hasExplanationText", "hasAdviceText", "hasChainStep"]:
    g.add((NS[ap], RDF.type, OWL.AnnotationProperty))
    lab(NS[ap], split_camel(ap))
g.add((SWRLA.isRuleEnabled, RDF.type, OWL.AnnotationProperty))

# ------------------------------------------------------------------ core classes
cls("Business", comment="A small business (v2: F&B only). Its monthly condition is described by MonthlyFinancialState individuals.")
cls("Period", comment="A calendar month. Linked to the previous month with previousPeriod.")
cls("MonthlyFinancialState",
    comment="Snapshot of one business in one month. The backend asserts computed numbers on it; "
            "the reasoner classifies it into observation and finding classes.")

# observations (intermediate reasoning steps)
cls("FinancialCondition", "MonthlyFinancialState",
    "Observation classes: simple facts derived by comparing numbers. They are the intermediate steps shown in the reasoning path.")
OBS = {
    "COGSGrowthExceedsRevenue": "Total COGS grew faster than total revenue (md 20.1).",
    "OPEXGrowthExceedsRevenue": "OPEX (excluding marketing) grew faster than revenue (md 20.3).",
    "MarketingGrowthExceedsRevenue": "Marketing spend grew faster than revenue (md 20.4).",
    "GrossMarginDecline": "Gross margin is below the lower bound derived from the business's own history (no universal threshold).",
    "NetMarginDecline": "Net profit margin is below the lower bound derived from the business's own history.",
    "PositiveProfit": "Net profit is greater than zero.",
    "CashDecline": "Cash balance decreased during the month (change in cash < 0).",
}
for k, v in OBS.items():
    cls(k, "FinancialCondition", v)

# findings (overall status)
cls("FinancialStatus", "MonthlyFinancialState",
    "Findings. Banner rule used by the application: Critical if the state is in CriticalCondition, else Warning if in "
    "WarningCondition, else Healthy (Healthy is a backend default; OWL is open-world, so it is never inferred).")
cls("HealthyCondition", "FinancialStatus", "Backend default when no warning/critical finding was inferred.")
cls("WarningCondition", "FinancialStatus", "At least one warning finding was inferred.")
cls("CriticalCondition", "FinancialStatus", "At least one critical finding was inferred. Not disjoint from WarningCondition: a state can have both; the highest severity wins.")
FIND_W = {
    "CostEscalation": "COGS is growing faster than revenue (early signal). This version does not tell apart higher purchase prices from a shift in what is sold; both are listed as things to check.",
    "MarginPressure": "Gross margin fell below the business's own baseline while COGS grew faster than revenue.",
    "OPEXPressure": "Operating expenses grew faster than revenue.",
    "MarketingEfficiencyReview": "Marketing spend grew faster than revenue; its efficiency should be reviewed (not a conclusion that it is wasteful).",
    "ProfitPressure": "Net profit margin fell below its own baseline (e.g. same revenue, lower profit).",
    "ProfitCashGap": "Net profit is positive but the cash balance fell. Cash left through non-expense flows (owner draw, facility purchase, loan principal).",
    "LiquidityPressure": "Cash balance fell during the month.",
    "OwnerDrawLiquidityPressure": "Owner draw increased, cash fell, and operating cash flow did not cover the draw.",
}
for k, v in FIND_W.items():
    cls(k, "WarningCondition", v)
cls("LiquidityCritical", "CriticalCondition",
    "Cash is falling and cash runway is below the minimum runway the owner/accountant configured (policy parameter, not a universal threshold).")
cls("MultidimensionalDistress", "CriticalCondition",
    "Simultaneous presence of margin pressure, OPEX pressure, and cash decline representing a multi-factor operational crisis (Newton & Whitaker distress framework).")
cls("NegativeEquityState", "CriticalCondition",
    "Monthly financial state where recorded equity is negative (liabilities exceed assets; technically insolvent condition). Catatan: ini indikasi teknis akuntansi, bukan nasihat hukum.")
cls("DistressedBusiness", "Business",
    "A business whose current financial state exhibits at least one critical condition.")
cls("PersistentMarginPressure", "MarginPressure",
    "Gross margin pressure that persists across consecutive months.")
g.add((NS["HealthyCondition"], OWL.disjointWith, NS["WarningCondition"]))
g.add((NS["HealthyCondition"], OWL.disjointWith, NS["CriticalCondition"]))

# category movement (profit bridge)
cls("CategoryMovement", comment="Month-over-month movement of one cost category (COGS, OPEX, Marketing, Depreciation). One individual per category per month; computed by the backend (profit bridge).")
cls("CostDriverMovement", "CategoryMovement", "A cost category that grew faster than revenue and is among the top contributors to the profit change. Inferred by rule.")

# investigation areas
cls("InvestigationArea", comment="Something the owner should check. Linked from findings through recommendsInvestigation.")

# data quality
cls("DataQualityStatus", comment="Completeness of the data behind a state.")

# indicators
cls("FinancialIndicator", comment="An amount (Rupiah) for one month, kept for evidence and display.")
cls("Revenue", "FinancialIndicator")
cls("COGS", "FinancialIndicator", "Cost of goods sold (raw materials, or goods bought for resale). Product groups/segments are a future extension.")
cls("OPEX", "FinancialIndicator", "Operating expenses.")
for c in ["FixedOPEX", "VariableOPEX", "MarketingOPEX"]:
    cls(c, "OPEX")
for c in ["GrossProfit", "GrossMargin", "OperatingProfit", "NetProfit", "DepreciationExpense"]:
    cls(c, "FinancialIndicator")
cls("CashFlow", "FinancialIndicator")
for c in ["OperatingCashFlow", "InvestingCashFlow", "FinancingCashFlow"]:
    cls(c, "CashFlow")
cls("InvestmentMetric", "FinancialIndicator")
for c in ["CapexAmount", "PaybackAmount", "ROIPercentage"]:
    cls(c, "InvestmentMetric")

# simple financial position (kas + aset tetap); rest = future extension
cls("BalanceSheetAccount", comment="Simple financial position (cash + fixed assets) is the MVP scope. Inventory, receivables and payables are future extensions.")
cls("Asset", "BalanceSheetAccount")
cls("CurrentAsset", "Asset")
cls("CashAndBank", "CurrentAsset")
cls("Inventory", "CurrentAsset", "Future extension (not in MVP).")
cls("Receivable", "CurrentAsset", "Future extension (not in MVP).")
cls("FixedAsset", "Asset", "Facility/equipment purchased; depreciated monthly instead of expensed at once.")
cls("AccumulatedDepreciation", "Asset", "Contra-asset.")
cls("Liability", "BalanceSheetAccount")
cls("CurrentLiability", "Liability")
cls("AccountsPayable", "CurrentLiability", "Future extension (not in MVP).")
cls("Loan", "Liability")
cls("Equity", "BalanceSheetAccount")
for c in ["OwnerCapital", "InvestorCapital", "RetainedEarnings"]:
    cls(c, "Equity")
cls("OwnerDraw", "Equity", "Prive. Not an expense; reduces equity and cash.")
dj = BNode()
g.add((dj, RDF.type, OWL.AllDisjointClasses))
lst = BNode()
from rdflib.collection import Collection
Collection(g, lst, [NS["Asset"], NS["Liability"], NS["Equity"]])
g.add((dj, OWL.members, lst))

# explanation layer (composed by the backend from inferred classes)
cls("FinancialDiagnosis", comment="Diagnosis record composed by the backend from the classes the reasoner inferred.")
cls("ReasoningEvidence")
cls("Explanation", "ReasoningEvidence")
cls("ReasoningPath", "ReasoningEvidence")
cls("ReasoningStep", "ReasoningEvidence")
cls("Advisory")

# ------------------------------------------------------------------ object properties
oprop("hasState", "Business", "MonthlyFinancialState", "Business has a monthly state.", inverse="stateOf")
oprop("stateOf", "MonthlyFinancialState", "Business", functional=True)
oprop("hasCurrentState", "Business", "MonthlyFinancialState", "Current active monthly state of the business.", functional=True)
oprop("forPeriod", "MonthlyFinancialState", "Period", "Month that the state describes.", functional=True)
oprop("previousPeriod", "Period", "Period", "The month before this one.", functional=True)

# Transitive temporal ordering between Periods
p_lt = NS["isLaterThan"]
OPROPS.add("isLaterThan")
g.add((p_lt, RDF.type, OWL.ObjectProperty))
g.add((p_lt, RDF.type, OWL.TransitiveProperty))
g.add((p_lt, RDFS.domain, NS["Period"]))
g.add((p_lt, RDFS.range, NS["Period"]))
lab(p_lt, "is Later Than")

p_prec = NS["precedes"]
OPROPS.add("precedes")
g.add((p_prec, RDF.type, OWL.ObjectProperty))
g.add((p_prec, RDF.type, OWL.TransitiveProperty))
g.add((p_prec, OWL.inverseOf, p_lt))
g.add((p_prec, RDFS.domain, NS["Period"]))
g.add((p_prec, RDFS.range, NS["Period"]))
lab(p_prec, "precedes")

g.add((NS["previousPeriod"], RDFS.subPropertyOf, p_lt))

oprop("comparedWith", "MonthlyFinancialState", "MonthlyFinancialState", "The previous month's state used as comparison.", functional=True)
oprop("hasIndicator", "MonthlyFinancialState", "FinancialIndicator", "Amounts kept as evidence.")
oprop("hasAccount", "Business", "BalanceSheetAccount")
oprop("hasDataQuality", "MonthlyFinancialState", "DataQualityStatus", functional=True)
oprop("hasCategoryMovement", "MonthlyFinancialState", "CategoryMovement")
oprop("hasCostDriver", "MonthlyFinancialState", "CostDriverMovement", "Inferred: categories that drive the profit decrease.")
oprop("recommendsInvestigation", "MonthlyFinancialState", "InvestigationArea",
      "Inferred from class-level knowledge: each finding class carries a hasValue restriction to the areas worth checking.")
oprop("hasDiagnosis", "MonthlyFinancialState", "FinancialDiagnosis")
oprop("derivedFrom", "FinancialDiagnosis", "FinancialIndicator")
oprop("hasEvidence", "FinancialDiagnosis", "ReasoningEvidence")
oprop("hasExplanation", "FinancialDiagnosis", "Explanation")
oprop("hasReasoningStep", "ReasoningPath", "ReasoningStep")
oprop("hasAdvisory", "FinancialDiagnosis", "Advisory")

# ------------------------------------------------------------------ data properties
D = XSD.decimal
state_nums = [
    ("hasRevenueGrowth", "Total revenue growth vs previous month (0.10 = +10%)."),
    ("hasCOGSGrowth", "Total COGS growth vs previous month."),
    ("hasOPEXGrowth", "OPEX growth, excluding marketing."),
    ("hasMarketingGrowth", "Marketing growth."),
    ("hasGrossMargin", "Gross margin this month (fraction)."),
    ("hasGrossMarginLowerBound", "Backend: own-history baseline minus tolerance. Omit when history is insufficient; the rule then stays silent."),
    ("hasNetProfit", "Net profit (Rupiah)."),
    ("hasNetMargin", "Net profit / revenue."),
    ("hasNetMarginLowerBound", "Backend: own-history baseline minus tolerance."),
    ("hasOperatingCashFlow", "Cash-basis operating cash flow = net profit + depreciation (Rupiah)."),
    ("hasChangeInCash", "Ending cash minus opening cash (Rupiah)."),
    ("hasEndingCash", "Ending cash balance (Rupiah)."),
    ("hasOwnerDrawAmount", "Owner draw (prive) this month (Rupiah)."),
    ("hasPreviousOwnerDrawAmount", "Owner draw previous month (Rupiah)."),
    ("hasCapexAmount", "Cash spent on facilities this month (Rupiah)."),
    ("hasLoanPrincipalPaid", "Loan principal repaid this month (Rupiah)."),
    ("hasCashRunwayMonths", "Ending cash / essential monthly outflow."),
    ("hasRunwayMinimumMonths", None, "Policy parameter set by the owner/accountant, not a universal constant."),
    ("hasEquity", "Total equity amount at closing (assets - liabilities)."),
]
for item in state_nums:
    if len(item) == 2:
        n, c = item
        dom = "MonthlyFinancialState"
    else:
        n, dom, c = item
    dprop(n, dom, D, c)

cls("PolicyParameter", comment="Configuration policy parameters (thresholds and tolerances) for financial diagnosis.")
dprop("hasGrossMarginTolerance", "PolicyParameter", D, "Allowed gross margin drop threshold below baseline.")
dprop("hasNetMarginTolerance", "PolicyParameter", D, "Allowed net margin drop threshold below baseline.")
dprop("hasCashMaterialityThreshold", "PolicyParameter", D, "Materiality threshold for cash decline (Rupiah).")

p_def = ind("Policy_Default", "PolicyParameter", "Default Financial Policy Parameters", target_graph=g)
g.add((p_def, NS["hasGrossMarginTolerance"], dec(0.03)))
g.add((p_def, NS["hasNetMarginTolerance"], dec(0.03)))
g.add((p_def, NS["hasCashMaterialityThreshold"], dec(1000000.0)))
g.add((p_def, NS["hasRunwayMinimumMonths"], dec(2.0)))

dprop("hasCategoryName", "CategoryMovement", XSD.string, "Category label, e.g. COGS, Marketing, Listrik.")
dprop("hasCategoryAmount", "CategoryMovement", D)
dprop("hasCategoryGrowth", "CategoryMovement", D)
dprop("hasProfitContribution", "CategoryMovement", D, "Effect on profit change (negative = reduces profit).")
dprop("hasContributionRank", "CategoryMovement", XSD.integer)
dprop("isTopContributor", "CategoryMovement", XSD.boolean, "Backend flag: among the largest contributors to the profit change.")
dprop("hasPeriodStart", "Period", XSD.date)
dprop("hasAmount", "FinancialIndicator", D)
dprop("hasSource", "FinancialIndicator", XSD.string)
dprop("hasPeriodLabel", "FinancialIndicator", XSD.string)
dprop("hasDepreciationPerMonth", "CapexAmount", D)
dprop("hasUsefulLifeMonths", "CapexAmount", XSD.integer)
dprop("hasResidualValue", "CapexAmount", D)
dprop("hasPaybackMonths", "PaybackAmount", D)
dprop("hasIncrementalProfit", "InvestmentMetric", D)
dprop("hasROIPercentage", "ROIPercentage", D)
dprop("hasDiagnosisMessage", "FinancialDiagnosis", XSD.string)
dprop("hasConfidenceNote", "FinancialDiagnosis", XSD.string)
dprop("hasReasoningText", "ReasoningStep", XSD.string)
dprop("hasAdvisoryText", "Advisory", XSD.string)

# ------------------------------------------------------------------ investigation areas + class-level advice
AREAS = {
    "Area_SupplierPrice": "Harga dari supplier",
    "Area_MaterialPrice": "Harga bahan baku",
    "Area_ProductionWaste": "Bahan terbuang / waste",
    "Area_ProductMix": "Komposisi penjualan: apakah porsi produk bermargin rendah naik",
    "Area_OperatingExpenseDetail": "Rincian biaya operasional",
    "Area_MarketingEfficiency": "Hasil promosi/iklan terhadap penjualan",
    "Area_CostBreakdown": "Rincian kenaikan biaya per kategori (profit bridge)",
    "Area_OwnerDrawPolicy": "Besar dan pola pengambilan kas pribadi (prive)",
    "Area_FacilityPurchase": "Pembelian fasilitas/peralatan",
    "Area_LoanRepayment": "Cicilan pokok pinjaman",
    "Area_CashPosition": "Posisi dan arus kas",
    "Area_CashRunway": "Berapa bulan kas bisa menutup biaya wajib",
}
for k, v in AREAS.items():
    ind(k, "InvestigationArea", v)

ADVICE = {
    "CostEscalation": ["Area_SupplierPrice", "Area_MaterialPrice", "Area_ProductionWaste", "Area_ProductMix"],
    "MarginPressure": ["Area_SupplierPrice", "Area_MaterialPrice", "Area_ProductionWaste", "Area_ProductMix"],
    "OPEXPressure": ["Area_OperatingExpenseDetail"],
    "MarketingEfficiencyReview": ["Area_MarketingEfficiency"],
    "ProfitPressure": ["Area_CostBreakdown"],
    "ProfitCashGap": ["Area_OwnerDrawPolicy", "Area_FacilityPurchase", "Area_LoanRepayment", "Area_CashPosition"],
    "LiquidityPressure": ["Area_CashPosition"],
    "OwnerDrawLiquidityPressure": ["Area_OwnerDrawPolicy", "Area_CashPosition"],
    "LiquidityCritical": ["Area_CashRunway", "Area_CashPosition"],
}
for c, areas in ADVICE.items():
    for a in areas:
        r = BNode()
        g.add((r, RDF.type, OWL.Restriction))
        g.add((r, OWL.onProperty, NS["recommendsInvestigation"]))
        g.add((r, OWL.hasValue, NS[a]))
        g.add((NS[c], RDFS.subClassOf, r))

for q in ["Complete", "Partial", "Missing"]:
    ind("Data_" + q, "DataQualityStatus", q)

# ------------------------------------------------------------------ Finding Knowledge & Explanations (TBox Annotations)
FINDING_KNOWLEDGE = {
    "CostEscalation": {
        "title": "Eskalasi Biaya Bahan Baku (Cost Escalation)",
        "domain": "Efisiensi Biaya",
        "severity": "Waspada",
        "rule": "F01_CostEscalation",
        "explanation": "Pertumbuhan biaya bahan baku (COGS) melampaui pertumbuhan omzet penjualan.",
        "chain": [
            "Hitung pertumbuhan omzet dan COGS",
            "COGS tumbuh lebih cepat dari pendapatan",
            "Indikasi eskalasi biaya bahan",
            "Tinjau harga supplier & porsi resep",
        ],
        "advice": "Periksa fluktuasi harga bahan dari supplier, pantau waste/bahan terbuang di bar/kitchen, dan evaluasi porsi resep menu.",
    },
    "MarginPressure": {
        "title": "Tekanan Margin Kotor (Margin Pressure)",
        "domain": "Profitabilitas",
        "severity": "Waspada",
        "rule": "F02_MarginPressure",
        "explanation": "Gross profit margin berada di bawah baseline historis bersamaan dengan kenaikan biaya bahan yang melebihi pendapatan.",
        "chain": [
            "Bandingkan gross margin dengan baseline",
            "COGS tumbuh lebih cepat dari omzet",
            "Gross margin turun di bawah ambang batas",
            "Evaluasi harga jual menu & product mix",
        ],
        "advice": "Tinjau harga jual menu, periksa apakah terjadi pergeseran penjualan ke menu ber-margin rendah (product mix), dan audit harga pembelian bahan.",
    },
    "OPEXPressure": {
        "title": "Beban Operasional Tumbuh Melebihi Omzet (OPEX Pressure)",
        "domain": "Efisiensi Biaya",
        "severity": "Waspada",
        "rule": "F03_OPEXPressure",
        "explanation": "Beban operasional (di luar pemasaran) bertumbuh lebih cepat daripada pendapatan usaha.",
        "chain": [
            "Hitung pertumbuhan OPEX non-marketing",
            "Pertumbuhan beban > pertumbuhan omzet",
            "Rasio beban operasional berpotensi meningkat",
            "Audit pos beban operasional terbesar",
        ],
        "advice": "Tinjau rincian beban pegawai, utilitas (listrik/air/gas), dan supplies. Pastikan kenaikan biaya sejalan dengan peningkatan kapasitas usaha.",
    },
    "MarketingEfficiencyReview": {
        "title": "Evaluasi Efisiensi Biaya Pemasaran (Marketing Efficiency)",
        "domain": "Efisiensi Biaya",
        "severity": "Waspada",
        "rule": "F04_MarketingEfficiencyReview",
        "explanation": "Biaya pemasaran/promosi tumbuh lebih cepat daripada pertumbuhan omzet penjualan.",
        "chain": [
            "Hitung pengeluaran iklan, promo & MDR",
            "Biaya marketing tumbuh lebih cepat dari omzet",
            "Tinjau efektivitas pengembalian promosi",
            "Optimalkan kanal promosi berkonversi tinggi",
        ],
        "advice": "Evaluasi kanal promosi (iklan medsos, potongan fee MDR/QRIS, diskon menu). Alihkan anggaran ke kanal promosi yang terbukti menghasilkan penjualan langsung.",
    },
    "ProfitPressure": {
        "title": "Tekanan Margin Laba Bersih (Profit Pressure)",
        "domain": "Profitabilitas",
        "severity": "Waspada",
        "rule": "F05_ProfitPressure",
        "explanation": "Margin laba bersih (net profit margin) berada di bawah batas wajar historis usaha.",
        "chain": [
            "Bandingkan net margin dengan baseline",
            "Porsi laba bersih terhadap omzet tertekan",
            "Beban usaha menggerus profitabilitas",
            "Audit pos pengeluaran & kebocoran biaya",
        ],
        "advice": "Telusuri pemicu penurunan laba bersih dari pos HPP, beban operasional, dan penyusutan; periksa apakah ada pengeluaran insidental yang tidak proporsional.",
    },
    "ProfitCashGap": {
        "title": "Kesenjangan Laba dan Kas (Profit-Cash Gap)",
        "domain": "Likuiditas",
        "severity": "Waspada",
        "rule": "F06_ProfitCashGap",
        "explanation": "Usaha mencatat laba bersih positif, namun saldo uang kas justru berkurang.",
        "chain": [
            "Laba bersih tercatat positif",
            "Perubahan kas periode ini negatif",
            "Kas keluar lewat pos non-laba-rugi",
            "Periksa prive, pembelian aset & pokok utang",
        ],
        "advice": "Laba bukan kas: periksa arus kas keluar untuk prive pemilik, pembelian aset tetap (peralatan), atau pembayaran pokok cicilan pinjaman.",
    },
    "LiquidityPressure": {
        "title": "Penurunan Saldo Kas (Liquidity Pressure)",
        "domain": "Likuiditas",
        "severity": "Waspada",
        "rule": "F07_LiquidityPressure",
        "explanation": "Total saldo kas dan rekening bank mengalami penurunan bersih sepanjang periode ini.",
        "chain": [
            "Hitung saldo awal kas dan penerimaan",
            "Arus kas keluar melampaui arus kas masuk",
            "Penurunan saldo kas bersih",
            "Kendalikan jadwal pengeluaran kas",
        ],
        "advice": "Pantau arus kas harian secara ketat, tunda pengeluaran non-prioritas, dan pastikan penerimaan omzet disetor ke rekening/kas secara disiplin.",
    },
    "OwnerDrawLiquidityPressure": {
        "title": "Prive Menekan Likuiditas Usaha (Owner Draw Pressure)",
        "domain": "Struktur Modal",
        "severity": "Waspada",
        "rule": "F08_OwnerDrawLiquidityPressure",
        "explanation": "Penarikan prive pemilik meningkat dan tidak tertutup oleh arus kas operasi, sehingga menguras cadangan kas.",
        "chain": [
            "Prive pemilik meningkat dari bulan lalu",
            "Arus kas operasi lebih kecil dari total prive",
            "Kas usaha mengalami penurunan",
            "Disiplinkan kebijakan penarikan kas pribadi",
        ],
        "advice": "Batasi penarikan prive pemilik agar tidak melebihi kemampuan arus kas operasional riil usaha. Jangan menggunakan kas operasional sebagai cadangan pribadi.",
    },
    "LiquidityCritical": {
        "title": "Krisis Likuiditas / Cadangan Kas Kritis (Liquidity Critical)",
        "domain": "Likuiditas",
        "severity": "Kritis",
        "rule": "F09_LiquidityCritical",
        "explanation": "Kas terus menurun dan cadangan kas (cash runway) kurang dari ambang batas aman (di bawah 2 bulan biaya wajib).",
        "chain": [
            "Saldo kas mengalami penurunan",
            "Sisa cadangan kas < ambang batas aman (2 bulan)",
            "Risiko gagal bayar operasional wajib",
            "Ambil tindakan pengamanan kas darurat",
        ],
        "advice": "Tindakan darurat: Moratorium penarikan prive, tunda seluruh pembelian aset baru, negosiasikan termin pembayaran, dan prioritaskan kas hanya untuk gaji dan bahan baku pokok.",
    },
    "MultidimensionalDistress": {
        "title": "Distres Multidimensi / Komplikasi Operasional (Multidimensional Distress)",
        "domain": "Kesehatan Menyeluruh",
        "severity": "Kritis",
        "rule": "F11_MultidimensionalDistress",
        "explanation": "Terjadi komplikasi simultan: margin kotor tertekan, beban operasional melonjak, dan cadangan kas mengalami penurunan.",
        "chain": [
            "Margin kotor tertekan di bawah batas historis",
            "Beban operasional (OPEX) tumbuh melebihi omzet",
            "Saldo kas mengalami penurunan bersih",
            "Simpulkan distres operasional multi-dimensi (Newton & Whitaker)",
        ],
        "advice": "Kondisi darurat komplikasi: Segera restrukturisasi biaya secara menyeluruh, negosiasikan ulang harga bahan baku, pangkas pos OPEX non-esensial, dan tahan seluruh pengeluaran kas non-operasional.",
    },
    "PersistentMarginPressure": {
        "title": "Tekanan Margin Berulang (Persistent Margin Pressure)",
        "domain": "Profitabilitas",
        "severity": "Waspada",
        "rule": "DL_PersistentMarginPressure",
        "explanation": "Gross profit margin tertekan selama minimal dua bulan berturut-turut.",
        "chain": [
            "Gross margin bulan ini tertekan di bawah baseline",
            "Gross margin bulan sebelumnya juga tertekan",
            "Deteksi persistensi tekanan margin antar-periode",
            "Ambil langkah korektif harga & struktur biaya menu",
        ],
        "advice": "Tekanan margin kronis: lakukan renegosiasi kontrak supplier jangka panjang, efisiensi resep menu, atau penyesuaian harga jual.",
    },
    "NegativeEquityState": {
        "title": "Ekuitas Negatif / Indikasi Defisit Modal (Negative Equity State)",
        "domain": "Solvabilitas",
        "severity": "Kritis",
        "rule": "DL_NegativeEquityState",
        "explanation": "Total kewajiban melebihi total aset usaha (ekuitas negatif / technically insolvent). Catatan: ini indikasi teknis akuntansi, bukan nasihat hukum.",
        "chain": [
            "Hitung total aset dan total kewajiban",
            "Total kewajiban melebihi total aset",
            "Ekuitas tercatat negatif (< 0)",
            "Rekomendasikan penguatan modal dan restrukturisasi utang",
        ],
        "advice": "Ekuitas negatif menandakan defisit modal akumulasi. Pemilik usaha disarankan melakukan injeksi modal atau restrukturisasi kewajiban operasional.",
    },
}

for fid, meta in FINDING_KNOWLEDGE.items():
    cls_uri = NS[fid]
    g.add((cls_uri, NS["hasTitle"], Literal(meta["title"])))
    g.add((cls_uri, NS["hasDomain"], Literal(meta["domain"])))
    g.add((cls_uri, NS["hasSeverity"], Literal(meta["severity"])))
    g.add((cls_uri, NS["hasRuleId"], Literal(meta["rule"])))
    g.add((cls_uri, NS["hasExplanationText"], Literal(meta["explanation"])))
    g.add((cls_uri, NS["hasAdviceText"], Literal(meta["advice"])))
    for idx, step in enumerate(meta["chain"], 1):
        g.add((cls_uri, NS["hasChainStep"], Literal(f"{idx}:{step}")))

# ------------------------------------------------------------------ DL Equivalent Classes (OWL 2 DL Axioms)
def dt_restriction(base_dt, facet, val):
    facet_node = BNode()
    g.add((facet_node, facet, dec(val) if base_dt == XSD.decimal else Literal(val, datatype=base_dt)))
    list_node = BNode()
    Collection(g, list_node, [facet_node])
    dt_node = BNode()
    g.add((dt_node, RDF.type, RDFS.Datatype))
    g.add((dt_node, OWL.onDatatype, base_dt))
    g.add((dt_node, OWL.withRestrictions, list_node))
    return dt_node


def some_dt_restriction(prop_name, base_dt, facet, val):
    r = BNode()
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, NS[prop_name]))
    g.add((r, OWL.someValuesFrom, dt_restriction(base_dt, facet, val)))
    return r


def some_class_restriction(prop_name, class_name):
    r = BNode()
    g.add((r, RDF.type, OWL.Restriction))
    g.add((r, OWL.onProperty, NS[prop_name]))
    g.add((r, OWL.someValuesFrom, NS[class_name]))
    return r


def set_equiv_intersection(class_name, member_nodes):
    c = NS[class_name]
    if len(member_nodes) == 1:
        g.add((c, OWL.equivalentClass, member_nodes[0]))
    else:
        lst = BNode()
        Collection(g, lst, member_nodes)
        anon = BNode()
        g.add((anon, RDF.type, OWL.Class))
        g.add((anon, OWL.intersectionOf, lst))
        g.add((c, OWL.equivalentClass, anon))


# 1. Datatype restrictions
# CashDecline ≡ hasChangeInCash some xsd:decimal[< 0]
g.add((NS["CashDecline"], OWL.equivalentClass, some_dt_restriction("hasChangeInCash", XSD.decimal, XSD.maxExclusive, 0)))

# PositiveProfit ≡ hasNetProfit some xsd:decimal[> 0]
g.add((NS["PositiveProfit"], OWL.equivalentClass, some_dt_restriction("hasNetProfit", XSD.decimal, XSD.minExclusive, 0)))

# NegativeEquityState ≡ MonthlyFinancialState and (hasEquity some xsd:decimal[< 0])
set_equiv_intersection("NegativeEquityState", [
    NS["MonthlyFinancialState"],
    some_dt_restriction("hasEquity", XSD.decimal, XSD.maxExclusive, 0)
])

# 2. Class conjunctions
# CostEscalation ≡ COGSGrowthExceedsRevenue
set_equiv_intersection("CostEscalation", [NS["COGSGrowthExceedsRevenue"]])

# MarginPressure ≡ GrossMarginDecline and COGSGrowthExceedsRevenue
set_equiv_intersection("MarginPressure", [NS["GrossMarginDecline"], NS["COGSGrowthExceedsRevenue"]])

# OPEXPressure ≡ OPEXGrowthExceedsRevenue
set_equiv_intersection("OPEXPressure", [NS["OPEXGrowthExceedsRevenue"]])

# MarketingEfficiencyReview ≡ MarketingGrowthExceedsRevenue
set_equiv_intersection("MarketingEfficiencyReview", [NS["MarketingGrowthExceedsRevenue"]])

# ProfitPressure ≡ NetMarginDecline
set_equiv_intersection("ProfitPressure", [NS["NetMarginDecline"]])

# LiquidityPressure ≡ CashDecline
set_equiv_intersection("LiquidityPressure", [NS["CashDecline"]])

# ProfitCashGap ≡ PositiveProfit and CashDecline
set_equiv_intersection("ProfitCashGap", [NS["PositiveProfit"], NS["CashDecline"]])

# MultidimensionalDistress ≡ MarginPressure and OPEXPressure and LiquidityPressure
set_equiv_intersection("MultidimensionalDistress", [NS["MarginPressure"], NS["OPEXPressure"], NS["LiquidityPressure"]])

# 3. Business level & temporal
# DistressedBusiness ≡ Business and (hasCurrentState some CriticalCondition)
set_equiv_intersection("DistressedBusiness", [
    NS["Business"],
    some_class_restriction("hasCurrentState", "CriticalCondition")
])

# PersistentMarginPressure ≡ MarginPressure and (comparedWith some MarginPressure)
set_equiv_intersection("PersistentMarginPressure", [
    NS["MarginPressure"],
    some_class_restriction("comparedWith", "MarginPressure")
])

# ------------------------------------------------------------------ SWRL rules
BUILTINS = {"greaterThan", "lessThan", "greaterThanOrEqual", "lessThanOrEqual", "equal"}


def var(n):
    v = NS["var_" + n]
    g.add((v, RDF.type, SWRL.Variable))
    return v


def arg(tok):
    tok = tok.strip()
    if tok.startswith("?"):
        return var(tok[1:])
    if tok in ("true", "false"):
        return Literal(tok == "true")
    return Literal(Decimal(tok), datatype=XSD.decimal)


def make_atom(text):
    m = re.match(r"\s*(\w+)\((.*)\)\s*$", text)
    name, args = m.group(1), [a.strip() for a in m.group(2).split(",")]
    a = BNode()
    if name in BUILTINS:
        g.add((a, RDF.type, SWRL.BuiltinAtom))
        g.add((a, SWRL.builtin, SWRLB[name]))
        l = BNode()
        Collection(g, l, [arg(x) for x in args])
        g.add((a, SWRL.arguments, l))
    elif name in CLASSES:
        g.add((a, RDF.type, SWRL.ClassAtom))
        g.add((a, SWRL.classPredicate, NS[name]))
        g.add((a, SWRL.argument1, arg(args[0])))
    elif name in DPROPS:
        g.add((a, RDF.type, SWRL.DatavaluedPropertyAtom))
        g.add((a, SWRL.propertyPredicate, NS[name]))
        g.add((a, SWRL.argument1, arg(args[0])))
        g.add((a, SWRL.argument2, arg(args[1])))
    elif name in OPROPS:
        g.add((a, RDF.type, SWRL.IndividualPropertyAtom))
        g.add((a, SWRL.propertyPredicate, NS[name]))
        g.add((a, SWRL.argument1, arg(args[0])))
        g.add((a, SWRL.argument2, arg(args[1])))
    else:
        raise ValueError("unknown predicate " + name)
    return a


def atom_list(texts):
    atoms = [make_atom(t) for t in re.split(r"\s*,\s*(?=\w+\()", texts.strip())]
    head = BNode()
    cur = head
    for i, a in enumerate(atoms):
        g.add((cur, RDF.type, SWRL.AtomList))
        g.add((cur, RDF.first, a))
        if i == len(atoms) - 1:
            g.add((cur, RDF.rest, RDF.nil))
        else:
            nxt = BNode()
            g.add((cur, RDF.rest, nxt))
            cur = nxt
    return head


RULES = []


def rule(rid, text, comment, note):
    body, head = text.split("->")
    imp = BNode()
    g.add((imp, RDF.type, SWRL.Imp))
    g.add((imp, SWRL.body, atom_list(body)))
    g.add((imp, SWRL.head, atom_list(head)))
    g.add((imp, RDFS.label, Literal(rid)))
    g.add((imp, RDFS.comment, Literal(comment)))
    g.add((imp, SWRLA.isRuleEnabled, Literal(True)))
    g.add((imp, NS["sourceStatus"], Literal("Draft-unvalidated")))
    g.add((imp, NS["sourceNote"], Literal(note)))
    RULES.append(rid)


S = "MonthlyFinancialState(?s)"
# --- observations
rule("O01_COGSGrowthExceedsRevenue",
     f"{S}, hasCOGSGrowth(?s,?c), hasRevenueGrowth(?s,?r), greaterThan(?c,?r) -> COGSGrowthExceedsRevenue(?s)",
     "Total COGS growth > revenue growth.", "md 20.1, 20.6")
rule("O02_OPEXGrowthExceedsRevenue",
     f"{S}, hasOPEXGrowth(?s,?o), hasRevenueGrowth(?s,?r), greaterThan(?o,?r) -> OPEXGrowthExceedsRevenue(?s)",
     "OPEX growth > revenue growth.", "md 20.3")
rule("O03_MarketingGrowthExceedsRevenue",
     f"{S}, hasMarketingGrowth(?s,?m), hasRevenueGrowth(?s,?r), greaterThan(?m,?r) -> MarketingGrowthExceedsRevenue(?s)",
     "Marketing growth > revenue growth.", "md 20.4")
rule("O04_GrossMarginDecline",
     f"{S}, hasGrossMargin(?s,?g), hasGrossMarginLowerBound(?s,?lb), lessThan(?g,?lb) -> GrossMarginDecline(?s)",
     "Gross margin below own-history lower bound (baseline of the last ~3 months, computed by backend).", "md 14, 20.1")
rule("O05_NetMarginDecline",
     f"{S}, hasNetMargin(?s,?n), hasNetMarginLowerBound(?s,?lb), lessThan(?n,?lb) -> NetMarginDecline(?s)",
     "Net margin below own-history lower bound (covers 'same revenue, lower profit').", "User example: revenue flat, profit 30jt -> 15jt")

# Note: O06, O07, F01-F07, F11 have been replaced by OWL 2 DL Equivalent Classes (DL Axioms).
# Only rules requiring comparison of two numeric data properties remain in SWRL.

rule("F08_OwnerDrawLiquidityPressure",
     f"{S}, hasOwnerDrawAmount(?s,?d), hasPreviousOwnerDrawAmount(?s,?pd), greaterThan(?d,?pd), CashDecline(?s), "
     f"hasOperatingCashFlow(?s,?ocf), lessThan(?ocf,?d) -> OwnerDrawLiquidityPressure(?s)",
     "Owner draw rose, cash fell, and operating cash flow was smaller than the draw.",
     "md 20.7; 'OCF not strong enough' interpreted as OCF < owner draw; needs accountant validation")
rule("F09_LiquidityCritical",
     f"{S}, LiquidityPressure(?s), hasCashRunwayMonths(?s,?r), hasRunwayMinimumMonths(?s,?m), lessThan(?r,?m) -> LiquidityCritical(?s)",
     "Cash falling and runway below configured minimum.", "Draft; minimum is a policy parameter")
rule("F10_CostDriver",
     f"{S}, hasCategoryMovement(?s,?m), hasCategoryGrowth(?m,?g), hasRevenueGrowth(?s,?r), greaterThan(?g,?r), "
     f"isTopContributor(?m,true) -> CostDriverMovement(?m), hasCostDriver(?s,?m)",
     "A top-contributing cost category that outgrows revenue is a cost driver (profit bridge).", "Draft; ranking computed by backend")

# ------------------------------------------------------------------ demo data (F&B, [DEMO]) in Finance_Health_Demo.owl
onto_demo = URIRef(BASE + "-demo")
g_demo.add((onto_demo, RDF.type, OWL.Ontology))
g_demo.add((onto_demo, OWL.imports, URIRef(BASE)))

b = ind("Demo_WarkopKusuma", "Business", "[DEMO] Warkop Kusuma", target_graph=g_demo)
p_aug = ind("Demo_Period_2026_08", "Period", "[DEMO] Agustus 2026", target_graph=g_demo)
p_sep = ind("Demo_Period_2026_09", "Period", "[DEMO] September 2026", target_graph=g_demo)
g_demo.add((p_sep, NS["previousPeriod"], p_aug))
g_demo.add((p_aug, NS["hasPeriodStart"], Literal("2026-08-01", datatype=XSD.date)))
g_demo.add((p_sep, NS["hasPeriodStart"], Literal("2026-09-01", datatype=XSD.date)))

# Aug (Rp juta -> rupiah penuh): rev 90, COGS 38, OPEX 30, Mkt 4, Dep 1 => NP 17
# Sep: rev 100, COGS 46.5, OPEX 32, Mkt 6.5, Dep 1 => NP 14
M = 1_000_000
aug = {"rev": 90, "cogs": 38, "opex": 30, "mkt": 4, "dep": 1}
sep = {"rev": 100, "cogs": 46.5, "opex": 32, "mkt": 6.5, "dep": 1}
np_aug = aug["rev"] - aug["cogs"] - aug["opex"] - aug["mkt"] - aug["dep"]
np_sep = sep["rev"] - sep["cogs"] - sep["opex"] - sep["mkt"] - sep["dep"]
assert (np_aug, np_sep) == (17, 14), (np_aug, np_sep)

s_aug = ind("Demo_State_2026_08", "MonthlyFinancialState", "[DEMO] Kondisi Agustus 2026", target_graph=g_demo)
s_sep = ind("Demo_State_2026_09", "MonthlyFinancialState", "[DEMO] Kondisi September 2026", target_graph=g_demo)
for s_, per, a_ in [(s_aug, p_aug, "Demo_State_2026_08"), (s_sep, p_sep, "")]:
    g_demo.add((b, NS["hasState"], s_))
    g_demo.add((s_, NS["forPeriod"], per))
g_demo.add((s_sep, NS["comparedWith"], s_aug))
g_demo.add((s_aug, NS["hasDataQuality"], NS["Data_Complete"]))
g_demo.add((s_sep, NS["hasDataQuality"], NS["Data_Complete"]))


def setn(s_, name, val):
    g_demo.add((s_, NS[name], dec(val)))


# August: a "normal" month; none of the rules should fire
for k, v in [("hasRevenueGrowth", 0.05), ("hasCOGSGrowth", 0.04), ("hasOPEXGrowth", 0.02), ("hasMarketingGrowth", 0.0),
             ("hasGrossMargin", 52 / 90), ("hasGrossMarginLowerBound", 0.56),
             ("hasNetProfit", np_aug * M), ("hasNetMargin", np_aug / 90), ("hasNetMarginLowerBound", 0.17),
             ("hasOperatingCashFlow", 18 * M), ("hasChangeInCash", 13 * M), ("hasEndingCash", 30 * M),
             ("hasOwnerDrawAmount", 3 * M), ("hasPreviousOwnerDrawAmount", 3 * M),
             ("hasCapexAmount", 0), ("hasLoanPrincipalPaid", 2 * M),
             ("hasCashRunwayMonths", 30 / 8), ("hasRunwayMinimumMonths", 2.0)]:
    setn(s_aug, k, v)

# September: cost escalation + margin pressure + profit pressure + marketing + profit-cash gap
for k, v in [("hasRevenueGrowth", 100 / 90 - 1), ("hasCOGSGrowth", 46.5 / 38 - 1),
             ("hasOPEXGrowth", 32 / 30 - 1), ("hasMarketingGrowth", 6.5 / 4 - 1),
             ("hasGrossMargin", 53.5 / 100), ("hasGrossMarginLowerBound", 0.56),
             ("hasNetProfit", np_sep * M), ("hasNetMargin", np_sep / 100), ("hasNetMarginLowerBound", 0.17),
             ("hasOperatingCashFlow", (np_sep + 1) * M),
             ("hasChangeInCash", ((np_sep + 1) - 12 - 8 - 2) * M), ("hasEndingCash", 23 * M),
             ("hasOwnerDrawAmount", 8 * M), ("hasPreviousOwnerDrawAmount", 3 * M),
             ("hasCapexAmount", 12 * M), ("hasLoanPrincipalPaid", 2 * M),
             ("hasCashRunwayMonths", 23 / 8), ("hasRunwayMinimumMonths", 2.0)]:
    setn(s_sep, k, v)

# evidence amounts (September)
for nm, typ, val in [("Demo_Sep_Revenue", "Revenue", sep["rev"]), ("Demo_Sep_COGS", "COGS", sep["cogs"]),
                     ("Demo_Sep_OPEX", "FixedOPEX", sep["opex"]), ("Demo_Sep_Marketing", "MarketingOPEX", sep["mkt"]),
                     ("Demo_Sep_Depreciation", "DepreciationExpense", sep["dep"]), ("Demo_Sep_NetProfit", "NetProfit", np_sep)]:
    i = ind(nm, typ, "[DEMO] " + nm.replace("Demo_Sep_", "") + " Sep 2026", target_graph=g_demo)
    g_demo.add((i, NS["hasAmount"], dec(val * M)))
    g_demo.add((i, NS["hasPeriodLabel"], Literal("2026-09")))
    g_demo.add((i, NS["hasSource"], Literal("demo data")))
    g_demo.add((s_sep, NS["hasIndicator"], i))

# profit bridge categories (September): cost increases vs August
for nm, name, cur, prev, rank, top in [("Demo_Sep_Move_COGS", "COGS", 46.5, 38, 1, True),
                                       ("Demo_Sep_Move_Marketing", "Marketing", 6.5, 4, 2, True),
                                       ("Demo_Sep_Move_OPEX", "OPEX (non-marketing)", 32, 30, 3, False)]:
    i = ind(nm, "CategoryMovement", "[DEMO] " + name + " Sep 2026", target_graph=g_demo)
    g_demo.add((i, NS["hasCategoryName"], Literal(name)))
    g_demo.add((i, NS["hasCategoryAmount"], dec(cur * M)))
    g_demo.add((i, NS["hasCategoryGrowth"], dec(cur / prev - 1)))
    g_demo.add((i, NS["hasProfitContribution"], dec(-(cur - prev) * M)))
    g_demo.add((i, NS["hasContributionRank"], Literal(rank, datatype=XSD.integer)))
    g_demo.add((i, NS["isTopContributor"], Literal(top)))
    g_demo.add((s_sep, NS["hasCategoryMovement"], i))

# diagnosis record composed by the backend (not by rules)
dg = ind("Demo_Sep_Diagnosis", "FinancialDiagnosis", "[DEMO] Diagnosis September 2026", target_graph=g_demo)
g_demo.add((s_sep, NS["hasDiagnosis"], dg))
g_demo.add((dg, NS["hasDiagnosisMessage"], Literal(
    "Omzet naik 11,1% tetapi untung bersih turun dari Rp17 juta ke Rp14 juta. Biaya bahan (COGS) naik 22,4%, lebih cepat dari omzet, "
    "sehingga margin kotor turun di bawah kebiasaan usaha ini; promosi juga naik 62,5%. Kenaikan harga bahan atau pergeseran produk yang "
    "terjual perlu dicek karena sistem belum membedakan keduanya. "
    "Kas turun Rp7 juta walau untung positif karena pembelian fasilitas Rp12 juta, prive Rp8 juta, dan cicilan pokok Rp2 juta.")))
g_demo.add((dg, NS["hasConfidenceNote"], Literal("Indikasi dari data yang dicatat; bukan nasihat keuangan resmi.")))
g_demo.add((dg, NS["derivedFrom"], NS["Demo_Sep_NetProfit"]))
ex = ind("Demo_Sep_Explanation", "Explanation", target_graph=g_demo)
g_demo.add((ex, RDFS.comment, Literal("Reasoning path: GrossMarginDecline + COGSGrowthExceedsRevenue -> MarginPressure")))
g_demo.add((dg, NS["hasExplanation"], ex))
ad = ind("Demo_Sep_Advisory", "Advisory", target_graph=g_demo)
g_demo.add((ad, NS["hasAdvisoryText"], Literal("Periksa harga bahan dari supplier, bahan terbuang, dan komposisi penjualan; tinjau hasil promosi; periksa pengambilan prive, pembelian fasilitas, dan cicilan.")))
g_demo.add((dg, NS["hasAdvisory"], ad))

from pathlib import Path

out_path = Path(__file__).resolve().with_name("Finance_Health_Expert_System_v2.owl")
g.serialize(str(out_path), format="xml")

demo_out_path = Path(__file__).resolve().with_name("Finance_Health_Demo.owl")
g_demo.serialize(str(demo_out_path), format="xml")
print("OK classes", len(CLASSES), "oprops", len(OPROPS), "dprops", len(DPROPS), "rules", len(RULES), "wrote", out_path, "and", demo_out_path)
