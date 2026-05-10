"""
Agentic Commerce Studio
=======================
A working prototype that demonstrates an autonomous system for retail e-commerce.

Architecture (read this first):
    [Data Synthesis Layer]
        Product catalogue + image library + live customer signals
                │
                ▼
    [Merchandiser Agent]  → decides WHAT to promote, and WHY
                │
                ▼
    [Creative Agent]      → generates ad copy variants (Claude API)
                │
                ▼
    [Deployment Agent]    → simulates push to Meta / Google / Email / On-site
                │
                ▼
    [Metrics + Event Log]

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st

# Anthropic is optional at import time so the app still loads if the package
# isn't installed yet — we surface a friendly message in the sidebar instead.
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

MODEL_ID = "claude-sonnet-4-20250514"

CHANNELS = ["Meta", "Google", "Email", "On-site Banner"]

CATEGORIES = [
    "Outerwear", "Footwear", "Activewear", "Home & Living",
    "Electronics", "Beauty", "Kids", "Accessories",
]

SIGNAL_TYPES = [
    "trending_search", "abandoned_cart_spike", "weather_shift",
    "regional_demand", "low_stock_alert", "competitor_promo",
]

st.set_page_config(
    page_title="Agentic Commerce Studio",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Signal:
    """A live customer/market signal that agents react to."""
    signal_id: str
    type: str
    description: str
    affected_category: str
    intensity: float  # 0–1, how strong the signal is
    timestamp: datetime


@dataclass
class CreativeAsset:
    """Output of the Creative Agent — what the Deployment Agent ships."""
    sku_id: str
    sku_name: str
    headline: str
    body: str
    cta: str
    image_url: str
    triggering_signal: str
    channel: str
    deployed_at: datetime | None = None
    status: str = "draft"  # draft → approved → deployed
    simulated_ctr: float = 0.0
    simulated_conv_lift: float = 0.0


@dataclass
class LogEntry:
    """A single line in the live event log."""
    timestamp: datetime
    agent: str
    message: str
    reasoning: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# MOCK DATA GENERATORS
# ─────────────────────────────────────────────────────────────────────────────

PRODUCT_IMAGE_MAP: dict[str, str] = {
    # Outerwear
    "Stormline Waterproof Jacket": "https://images-na.ssl-images-amazon.com/images/I/51C-yNl+P2L.jpg",
    "Heritage Wool Overcoat": "https://preview.redd.it/wool-overcoat-recommendations-v0-3b1vq1sb70md1.jpeg?width=640&crop=smart&auto=webp&s=d96a0c77bd62d54d564d838df9275b08c62e6995",
    "Alpine Down Parka": "https://www.basicclothesco.com/cdn/shop/files/Men_sDownWinterJacket_Thick_Warm_andStylishHoodedParkagray.jpg?v=1738014137&width=800",
    "City Trench Coat": "https://hips.hearstapps.com/hmg-prod/images/guest-is-seen-wearing-a-belted-coach-trench-coat-black-news-photo-1760632867.pjpeg?crop=1xw:0.98061xh;center,top&resize=600:*",
    # Footwear
    "Trail Runner GTX": "https://i5.walmartimages.com/seo/Nike-Pegasus-Trail-3-Gore-Tex-DC8793-001-Men-s-Black-Running-Sneaker-Shoes-OF43-11_82101c5e-9fb8-4920-afa2-9280052f302f.39640292ba76ba57fa65d9ce2def395c.jpeg",
    "Studio Knit Trainer": "https://allyfashion.com/cdn/shop/products/shoes-white-knit-detail-lace-up-trainers-sneakers-33297563779265.jpg?v=1668745796",
    "Classic Leather Boot": "https://i.pinimg.com/originals/22/a2/8e/22a28ee350fe6855dc5dd9b330f5ae3c.jpg",
    "Court Sneaker": "https://images.quince.com/1goqOp4rZiRM96no4IH8H9/a71b70053ea180545992c3bc6816ba0b/W--392_Italian_Leather_and_Suede_Low_Profile_Sneaker_BLA_20402_CROPPED.jpg?w=800&q=80",
    # Activewear
    "Flex Performance Tee": "https://m.media-amazon.com/images/I/518pyWRbiXL.jpg",
    "Compression Run Tight": "https://images-na.ssl-images-amazon.com/images/I/51MBR4Wi1fL.jpg",
    "Yoga Studio Legging": "https://studiokyogawear.com/cdn/shop/files/Rib_Bralette_Leggings_Black_4_SL.jpg?v=1757647895&width=800",
    "Training Hoodie": "https://cdn.shopify.com/s/files/1/0156/6146/files/images-TrainingOversizedFleeceHoodieGSCherryPurpleB5A7N_PCDS_0064_0012_3840x.jpg?v=1752762591",
    # Home & Living
    "Linen Bedding Set": "https://www.soakandsleep.com/cdn/shop/files/light-grey-french-linen-lifestyle-add1_3.jpg?v=1749205173&width=800",
    "Ceramic Pour-Over Set": "https://m.media-amazon.com/images/I/81Ng2Qzu7-L.jpg",
    "Wool Throw Blanket": "https://m.media-amazon.com/images/I/817udNHKbiL.jpg",
    "Aroma Diffuser": "https://m.media-amazon.com/images/I/61RmRRbD6SL.jpg",
    # Electronics
    "Noise-Cancel Headphones": "https://m.media-amazon.com/images/S/aplus-media-library-service-media/32d5b783-d826-408d-8bdb-109908bb4c6f.__CR0,0,1464,600_PT0_SX1464_V1___.jpg",
    "Compact Mirrorless Camera": "https://mldvwwasb8tu.i.optimole.com/cb:7ZGO.6206b/w:1080/h:1080/q:90/f:best/ig:avif/https://travelaway.me/wp-content/uploads/2023/11/a-6700-compact-mirrorless-camera.jpg",
    "Smart Home Hub": "https://media.istockphoto.com/id/1214098172/photo/smart-home-hub-for-home-automation-on-wooden-desktop-with-copyspace.jpg?s=612x612&w=0&k=20&c=q2pbA6n-9vMArLJsg9tgpMBjW8GMc0oibViC94IGsoo=",
    "4K Streaming Stick": "https://m.media-amazon.com/images/I/61ZYTXa9DdL.jpg",
    # Beauty
    "Vitamin C Serum": "https://media.glamour.com/photos/69a86361bfdccf45556df222/3:4/w_748,c_limit/Product%20(2).png",
    "Hydrating Cleanser": "https://sonage.com/cdn/shop/files/CleanserComp1x1_648b212f-69da-4f90-8458-1f402f2dd470.jpg?v=1750290562&width=800",
    "SPF 50 Mineral Sunscreen": "https://bluelizardsunscreen.com/cdn/shop/files/Sheer_Face_Swatch.webp?v=1768398096&width=800",
    "Volumising Mascara": "https://americanculturebrands.com/cdn/shop/products/KLOR-WEB-IMAGES_0001s_0002_DSC_0029.png?v=1711644623&width=800",
    # Kids
    "Rainproof Kids Jacket": "https://images-na.ssl-images-amazon.com/images/I/51C-yNl+P2L.jpg",
    "Soft-Sole Toddler Shoe": "https://m.media-amazon.com/images/I/61ll6XbelGL.jpg",
    "Organic Cotton PJs": "https://images.squarespace-cdn.com/content/v1/5bb8cd5aa09a7e4c80cb9fd8/261ae1c0-8967-4f73-a3c8-752e759e5a1b/15+soft+organic+cotton+kids+pyjamas+(2).jpg",
    "Reusable Lunch Box": "https://images-na.ssl-images-amazon.com/images/I/81SdGysIzHL.jpg",
    # Accessories
    "Leather Card Holder": "https://m.media-amazon.com/images/I/71rMkmHxHAL.jpg",
    "Cashmere Scarf": "https://italoferretti.com/wp-content/uploads/2024/12/SCARF_416641-06-70X200-2-500x500.jpg",
    "Polarised Sunglasses": "https://m.media-amazon.com/images/I/61mtMYZYQlL.jpg",
    "Canvas Tote Bag": "https://img.freepik.com/free-photo/canvas-tote-bag-minimal-style_53876-111057.jpg?semt=ais_hybrid&w=740&q=80",
}

PRODUCT_TEMPLATES = {
    "Outerwear": [
        ("Stormline Waterproof Jacket", "Seam-sealed shell built for relentless rain.", ["waterproof", "rain", "outdoor"]),
        ("Heritage Wool Overcoat", "Tailored wool overcoat with a clean, timeless silhouette.", ["wool", "formal", "winter"]),
        ("Alpine Down Parka", "850-fill down for sub-zero comfort.", ["winter", "down", "cold-weather"]),
        ("City Trench Coat", "Lightweight trench for shoulder-season commutes.", ["spring", "lightweight", "urban"]),
    ],
    "Footwear": [
        ("Trail Runner GTX", "Gore-Tex trail shoe with aggressive lugs.", ["running", "trail", "waterproof"]),
        ("Studio Knit Trainer", "Recycled knit upper, all-day cushioning.", ["sustainable", "casual", "everyday"]),
        ("Classic Leather Boot", "Full-grain leather, Goodyear welted.", ["leather", "boots", "heritage"]),
        ("Court Sneaker", "Low-profile court silhouette in soft suede.", ["casual", "suede", "retro"]),
    ],
    "Activewear": [
        ("Flex Performance Tee", "4-way stretch, moisture-wicking technical tee.", ["gym", "performance", "stretch"]),
        ("Compression Run Tight", "Graduated compression for long runs.", ["running", "compression", "performance"]),
        ("Yoga Studio Legging", "Buttery-soft, squat-proof studio legging.", ["yoga", "studio", "soft"]),
        ("Training Hoodie", "Brushed-back fleece training hoodie.", ["training", "fleece", "warm"]),
    ],
    "Home & Living": [
        ("Linen Bedding Set", "Stonewashed French linen, breathable all year.", ["bedding", "linen", "natural"]),
        ("Ceramic Pour-Over Set", "Hand-thrown ceramic pour-over with carafe.", ["coffee", "ceramic", "kitchen"]),
        ("Wool Throw Blanket", "Lambswool throw, woven in Yorkshire.", ["blanket", "wool", "cozy"]),
        ("Aroma Diffuser", "Ultrasonic diffuser with ambient lighting.", ["wellness", "home", "ambient"]),
    ],
    "Electronics": [
        ("Noise-Cancel Headphones", "ANC over-ear with 40hr battery.", ["audio", "anc", "wireless"]),
        ("Compact Mirrorless Camera", "24MP APS-C mirrorless body.", ["camera", "photography", "compact"]),
        ("Smart Home Hub", "Matter-ready hub with voice control.", ["smart-home", "matter", "voice"]),
        ("4K Streaming Stick", "HDR streaming with Wi-Fi 6.", ["streaming", "4k", "tv"]),
    ],
    "Beauty": [
        ("Vitamin C Serum", "15% L-ascorbic acid brightening serum.", ["skincare", "vitamin-c", "brightening"]),
        ("Hydrating Cleanser", "pH-balanced gel cleanser.", ["skincare", "cleanser", "hydrating"]),
        ("SPF 50 Mineral Sunscreen", "Zinc-based daily mineral SPF.", ["spf", "mineral", "daily"]),
        ("Volumising Mascara", "Buildable lash-volume mascara.", ["makeup", "mascara", "volume"]),
    ],
    "Kids": [
        ("Rainproof Kids Jacket", "Lightweight rainproof jacket for school runs.", ["kids", "rain", "school"]),
        ("Soft-Sole Toddler Shoe", "Flexible soft-sole shoe for early walkers.", ["kids", "toddler", "soft-sole"]),
        ("Organic Cotton PJs", "GOTS-certified organic cotton pyjamas.", ["kids", "organic", "sleepwear"]),
        ("Reusable Lunch Box", "Leak-proof bento-style lunch box.", ["kids", "lunch", "reusable"]),
    ],
    "Accessories": [
        ("Leather Card Holder", "Slim full-grain leather card holder.", ["leather", "wallet", "slim"]),
        ("Cashmere Scarf", "Lightweight 2-ply cashmere scarf.", ["cashmere", "winter", "soft"]),
        ("Polarised Sunglasses", "Acetate frame with polarised lenses.", ["sunglasses", "polarised", "summer"]),
        ("Canvas Tote Bag", "Heavy-duty 16oz canvas tote.", ["bag", "canvas", "everyday"]),
    ],
}


def generate_catalogue(n_skus: int = 50, seed: int = 42) -> pd.DataFrame:
    """Produce a deterministic mock product catalogue."""
    rng = random.Random(seed)
    rows = []
    for i in range(n_skus):
        category = rng.choice(CATEGORIES)
        name, desc, tags = rng.choice(PRODUCT_TEMPLATES[category])
        sku_id = f"SKU-{1000 + i}"
        image_url = PRODUCT_IMAGE_MAP.get(
            name,
            f"https://picsum.photos/seed/{sku_id.replace('-', '')}/600/400",
        )
        rows.append({
            "sku_id": sku_id,
            "name": name,
            "category": category,
            "price": round(rng.uniform(15, 450), 2),
            "stock_level": rng.randint(0, 500),
            "image_url": image_url,
            "description": desc,
            "tags": ", ".join(tags),
            "margin_pct": round(rng.uniform(0.18, 0.62), 2),
        })
    return pd.DataFrame(rows)


def generate_signals(catalogue: pd.DataFrame, n: int = 6) -> list[Signal]:
    """Generate a fresh batch of live signals tied to real catalogue categories."""
    rng = random.Random()  # non-deterministic so 'refresh' actually changes things
    signals: list[Signal] = []
    descriptions = {
        "trending_search": [
            "Search volume for '{cat}' up {pct}% in last 6h",
            "'{cat}' rising in TikTok trends",
            "Google Trends spike on '{cat}' keywords",
        ],
        "abandoned_cart_spike": [
            "{pct}% abandoned-cart rate on {cat} SKUs",
            "Cart abandonment spike detected in {cat}",
        ],
        "weather_shift": [
            "Cold front incoming — {cat} demand expected to lift",
            "Heatwave forecast — {cat} demand expected to lift",
            "Heavy rain forecast — {cat} demand expected to lift",
        ],
        "regional_demand": [
            "London region showing {pct}% lift in {cat} interest",
            "Manchester traffic on {cat} category up {pct}%",
            "North-West regional demand surge in {cat}",
        ],
        "low_stock_alert": [
            "{cat} hero SKUs approaching 20% stock threshold",
            "Inventory risk: {cat} bestsellers below 14-day cover",
        ],
        "competitor_promo": [
            "Competitor running 25% off {cat} — defensive action recommended",
            "Major competitor promo live in {cat} category",
        ],
    }
    categories_in_play = list(catalogue["category"].unique())
    for i in range(n):
        sig_type = rng.choice(SIGNAL_TYPES)
        cat = rng.choice(categories_in_play)
        template = rng.choice(descriptions[sig_type])
        desc = template.format(cat=cat, pct=rng.randint(15, 85))
        signals.append(Signal(
            signal_id=f"SIG-{int(time.time() * 1000) % 100000}-{i}",
            type=sig_type,
            description=desc,
            affected_category=cat,
            intensity=round(rng.uniform(0.4, 1.0), 2),
            timestamp=datetime.now() - timedelta(minutes=rng.randint(0, 90)),
        ))
    return signals


# ─────────────────────────────────────────────────────────────────────────────
# CSV INGESTION (Bring Your Own Data)
# ─────────────────────────────────────────────────────────────────────────────

# Required columns for an uploaded catalogue. Missing optional ones are
# auto-filled with sensible defaults so partial PIM exports still work.
CATALOGUE_REQUIRED = {"sku_id", "name", "category"}
CATALOGUE_OPTIONAL_DEFAULTS = {
    "price": lambda rng: round(rng.uniform(15, 450), 2),
    "stock_level": lambda rng: rng.randint(50, 500),
    "image_url": None,  # filled per-row from sku_id
    "description": lambda rng: "",
    "tags": lambda rng: "",
    "margin_pct": lambda rng: round(rng.uniform(0.25, 0.55), 2),
}

SIGNALS_REQUIRED = {"type", "description", "affected_category"}


def ingest_catalogue_csv(file) -> tuple[pd.DataFrame | None, list[str]]:
    """
    Parse and validate an uploaded catalogue CSV.

    Returns (dataframe_or_None, messages). Messages are user-facing strings
    explaining what was loaded, defaulted, or rejected.
    """
    messages: list[str] = []
    try:
        df = pd.read_csv(file)
    except Exception as e:
        return None, [f"❌ Could not parse CSV: {e}"]

    # Normalise column names (strip whitespace, lowercase)
    df.columns = [c.strip().lower() for c in df.columns]

    missing_required = CATALOGUE_REQUIRED - set(df.columns)
    if missing_required:
        return None, [
            f"❌ Missing required columns: {sorted(missing_required)}. "
            f"Required: {sorted(CATALOGUE_REQUIRED)}."
        ]

    rng = random.Random(42)
    filled_cols: list[str] = []
    for col, default_fn in CATALOGUE_OPTIONAL_DEFAULTS.items():
        if col not in df.columns:
            if col == "image_url":
                df[col] = df.apply(
                    lambda row: PRODUCT_IMAGE_MAP.get(
                        str(row.get("name", "")),
                        f"https://picsum.photos/seed/{str(row['sku_id']).replace('-', '')}/600/400",
                    ),
                    axis=1,
                )
            else:
                df[col] = [default_fn(rng) for _ in range(len(df))]
            filled_cols.append(col)

    # Type coercion — be forgiving about what comes out of a PIM export
    df["sku_id"] = df["sku_id"].astype(str)
    df["name"] = df["name"].astype(str)
    df["category"] = df["category"].astype(str)
    df["description"] = df["description"].fillna("").astype(str)
    df["tags"] = df["tags"].fillna("").astype(str)
    df["image_url"] = df["image_url"].fillna("").astype(str)
    # Replace any blank image_urls with a deterministic placeholder
    blank_imgs = df["image_url"].str.strip() == ""
    if blank_imgs.any():
        df.loc[blank_imgs, "image_url"] = df.loc[blank_imgs].apply(
            lambda row: PRODUCT_IMAGE_MAP.get(
                str(row.get("name", "")),
                f"https://picsum.photos/seed/{str(row['sku_id']).replace('-', '')}/600/400",
            ),
            axis=1,
        )
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    df["stock_level"] = pd.to_numeric(df["stock_level"], errors="coerce").fillna(0).astype(int)
    df["margin_pct"] = pd.to_numeric(df["margin_pct"], errors="coerce").fillna(0.3)

    messages.append(f"✅ Loaded {len(df)} SKUs across {df['category'].nunique()} categories.")
    if filled_cols:
        messages.append(f"ℹ️ Filled missing columns with defaults: {', '.join(filled_cols)}.")
    if df["stock_level"].eq(0).any():
        zero_stock = int(df["stock_level"].eq(0).sum())
        messages.append(f"⚠️ {zero_stock} SKUs have zero stock — they'll be skipped by the Merchandiser.")

    return df, messages


def ingest_signals_csv(file, catalogue: pd.DataFrame) -> tuple[list[Signal] | None, list[str]]:
    """Parse an uploaded signals CSV. Optional intensity column."""
    messages: list[str] = []
    try:
        df = pd.read_csv(file)
    except Exception as e:
        return None, [f"❌ Could not parse signals CSV: {e}"]

    df.columns = [c.strip().lower() for c in df.columns]
    missing = SIGNALS_REQUIRED - set(df.columns)
    if missing:
        return None, [
            f"❌ Missing required signal columns: {sorted(missing)}. "
            f"Required: {sorted(SIGNALS_REQUIRED)}."
        ]

    if "intensity" not in df.columns:
        df["intensity"] = 0.7
        messages.append("ℹ️ No intensity column — defaulted all signals to 0.7.")
    df["intensity"] = pd.to_numeric(df["intensity"], errors="coerce").fillna(0.7).clip(0, 1)

    # Warn if signal categories don't match anything in the catalogue
    cat_set = set(catalogue["category"].unique())
    unknown_cats = set(df["affected_category"].unique()) - cat_set
    if unknown_cats:
        messages.append(
            f"⚠️ Signals reference categories not in catalogue: {sorted(unknown_cats)}. "
            f"They'll still load but the Merchandiser won't act on them."
        )

    signals = [
        Signal(
            signal_id=f"SIG-UPLOAD-{i}",
            type=str(row["type"]),
            description=str(row["description"]),
            affected_category=str(row["affected_category"]),
            intensity=float(row["intensity"]),
            timestamp=datetime.now() - timedelta(minutes=i * 5),
        )
        for i, row in df.iterrows()
    ]
    messages.append(f"✅ Loaded {len(signals)} signals.")
    return signals, messages


def catalogue_csv_template() -> str:
    """Downloadable template showing the expected catalogue CSV shape."""
    return (
        "sku_id,name,category,price,stock_level,image_url,description,tags,margin_pct\n"
        "SKU-1001,Stormline Waterproof Jacket,Outerwear,189.00,120,"
        "https://example.com/img/sku-1001.jpg,Seam-sealed shell built for relentless rain.,"
        '"waterproof, rain, outdoor",0.42\n'
        "SKU-1002,Trail Runner GTX,Footwear,159.99,80,"
        "https://example.com/img/sku-1002.jpg,Gore-Tex trail shoe with aggressive lugs.,"
        '"running, trail, waterproof",0.38\n'
    )


def signals_csv_template() -> str:
    """Downloadable template showing the expected signals CSV shape."""
    return (
        "type,description,affected_category,intensity\n"
        "trending_search,Search volume for Outerwear up 45% in last 6h,Outerwear,0.85\n"
        "weather_shift,Cold front incoming — Outerwear demand expected to lift,Outerwear,0.7\n"
        "abandoned_cart_spike,32% abandoned-cart rate on Footwear SKUs,Footwear,0.6\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# AGENT PROMPTS (editable in the Advanced expander)
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MERCHANDISER_PROMPT = """You are the Merchandiser Agent in an autonomous e-commerce system.

You are given:
1. A list of live customer/market signals
2. A product catalogue with stock, price, margin, and tags

Your job: pick the TOP {top_n} SKUs to promote RIGHT NOW, and explain why.

Rules:
- Prioritise SKUs whose category matches a high-intensity signal
- Avoid SKUs with stock_level < 20 (we can't promote what we can't fulfil)
- Prefer higher-margin SKUs when multiple options match a signal
- Each pick must cite the specific signal that triggered it

Return ONLY a JSON array, no prose, in this exact shape:
[
  {{"sku_id": "SKU-1023", "triggering_signal_id": "SIG-12345-0", "reasoning": "1-sentence why"}},
  ...
]
"""

DEFAULT_CREATIVE_PROMPT = """You are the Creative Agent in an autonomous e-commerce system.

For the SKU below, write ad creative tailored to the triggering signal and channel.

SKU: {sku_name}
Category: {category}
Description: {description}
Price: £{price}
Triggering signal: {signal_description}
Channel: {channel}

Channel rules:
- Meta: scroll-stopping, emotive, max 8-word headline
- Google: keyword-rich, benefit-led, max 30-character headline
- Email: warm and personal, can be longer
- On-site Banner: punchy, urgent, max 6-word headline

Return ONLY a JSON object, no prose:
{{"headline": "...", "body": "...", "cta": "..."}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# AGENTS
# ─────────────────────────────────────────────────────────────────────────────

def _claude_client(api_key: str) -> Any | None:
    """Build an Anthropic client, or None if unavailable."""
    if not ANTHROPIC_AVAILABLE or not api_key:
        return None
    try:
        return Anthropic(api_key=api_key)
    except Exception:
        return None


def _extract_json(text: str) -> str:
    """Strip code fences and isolate the JSON portion of a model response."""
    text = text.strip()
    if text.startswith("```"):
        # remove first fence line
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        # if it started with ```json
        text = text.lstrip("json").strip()
    return text


def merchandiser_agent(
    catalogue: pd.DataFrame,
    signals: list[Signal],
    top_n: int,
    client: Any | None,
    prompt_template: str,
    log: list[LogEntry],
) -> list[dict]:
    """Decide which SKUs to promote. Falls back to rule-based logic if no API key."""
    log.append(LogEntry(
        timestamp=datetime.now(),
        agent="Merchandiser",
        message=f"Scanning {len(catalogue)} SKUs against {len(signals)} live signals…",
    ))

    if client is None:
        # ── Rule-based fallback so the demo always works ─────────────────────
        scored = []
        for sig in signals:
            cat_skus = catalogue[
                (catalogue["category"] == sig.affected_category)
                & (catalogue["stock_level"] >= 20)
            ]
            if cat_skus.empty:
                continue
            # Score = margin * signal intensity (simple but defensible)
            top = cat_skus.assign(
                score=cat_skus["margin_pct"] * sig.intensity
            ).nlargest(2, "score")
            for _, row in top.iterrows():
                scored.append({
                    "sku_id": row["sku_id"],
                    "triggering_signal_id": sig.signal_id,
                    "reasoning": (
                        f"Category match on {sig.affected_category} "
                        f"signal '{sig.type}' (intensity {sig.intensity}); "
                        f"margin {int(row['margin_pct']*100)}%."
                    ),
                })
        # dedupe by sku_id, keep top_n
        seen = set()
        deduped = []
        for s in scored:
            if s["sku_id"] in seen:
                continue
            seen.add(s["sku_id"])
            deduped.append(s)
            if len(deduped) >= top_n:
                break
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Merchandiser",
            message=f"Selected {len(deduped)} SKUs (rule-based mode — add API key for LLM reasoning).",
            reasoning="Scoring: margin_pct × signal.intensity, filtered by stock ≥ 20.",
        ))
        return deduped

    # ── LLM-driven mode ──────────────────────────────────────────────────────
    catalogue_str = catalogue[
        ["sku_id", "name", "category", "price", "stock_level", "margin_pct", "tags"]
    ].to_csv(index=False)
    signals_str = "\n".join(
        f"- {s.signal_id} | {s.type} | {s.affected_category} | "
        f"intensity={s.intensity} | {s.description}"
        for s in signals
    )
    prompt = prompt_template.format(top_n=top_n) + (
        f"\n\nSIGNALS:\n{signals_str}\n\nCATALOGUE (CSV):\n{catalogue_str}"
    )

    try:
        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text
        import json
        picks = json.loads(_extract_json(raw))
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Merchandiser",
            message=f"Selected {len(picks)} SKUs via Claude.",
            reasoning=raw[:400],
        ))
        return picks
    except Exception as e:
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Merchandiser",
            message=f"LLM call failed ({e}); falling back to rule-based.",
        ))
        # Recurse with no client → fallback path
        return merchandiser_agent(catalogue, signals, top_n, None, prompt_template, log)


def creative_agent(
    pick: dict,
    catalogue: pd.DataFrame,
    signals: list[Signal],
    channel: str,
    client: Any | None,
    prompt_template: str,
    log: list[LogEntry],
) -> CreativeAsset | None:
    """Generate ad copy for one SKU on one channel."""
    sku_row = catalogue[catalogue["sku_id"] == pick["sku_id"]]
    if sku_row.empty:
        return None
    sku = sku_row.iloc[0]
    sig = next(
        (s for s in signals if s.signal_id == pick["triggering_signal_id"]),
        signals[0] if signals else None,
    )
    sig_desc = sig.description if sig else "general promotion"

    if client is None:
        # Templated fallback creative
        copy = {
            "Meta": {
                "headline": f"{sku['name']} — made for moments like this",
                "body": f"{sku['description']} Now in stock.",
                "cta": "Shop now",
            },
            "Google": {
                "headline": f"{sku['name'][:30]}",
                "body": f"{sku['description'][:90]}",
                "cta": "Buy online",
            },
            "Email": {
                "headline": f"We thought of you: {sku['name']}",
                "body": (
                    f"Because of {sig_desc.lower()}, we wanted to put this in front "
                    f"of you first. {sku['description']}"
                ),
                "cta": "See it now",
            },
            "On-site Banner": {
                "headline": f"New: {sku['name'].split()[0]}",
                "body": sku["description"],
                "cta": "Shop",
            },
        }[channel]
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Creative",
            message=f"Generated {channel} creative for {sku['sku_id']} (template mode).",
        ))
        return CreativeAsset(
            sku_id=sku["sku_id"],
            sku_name=sku["name"],
            headline=copy["headline"],
            body=copy["body"],
            cta=copy["cta"],
            image_url=sku["image_url"],
            triggering_signal=sig_desc,
            channel=channel,
            status="draft",
        )

    prompt = prompt_template.format(
        sku_name=sku["name"],
        category=sku["category"],
        description=sku["description"],
        price=sku["price"],
        signal_description=sig_desc,
        channel=channel,
    )
    try:
        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text
        import json
        copy = json.loads(_extract_json(raw))
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Creative",
            message=f"Generated {channel} creative for {sku['sku_id']} via Claude.",
            reasoning=f"Headline: {copy.get('headline', '')}",
        ))
        return CreativeAsset(
            sku_id=sku["sku_id"],
            sku_name=sku["name"],
            headline=copy["headline"],
            body=copy["body"],
            cta=copy["cta"],
            image_url=sku["image_url"],
            triggering_signal=sig_desc,
            channel=channel,
            status="draft",
        )
    except Exception as e:
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Creative",
            message=f"LLM call failed ({e}); using template fallback.",
        ))
        return creative_agent(pick, catalogue, signals, channel, None, prompt_template, log)


def deployment_agent(
    asset: CreativeAsset,
    log: list[LogEntry],
) -> CreativeAsset:
    """Simulate pushing the asset to the channel and synthesise performance numbers."""
    asset.deployed_at = datetime.now()
    asset.status = "deployed"
    # Simulated performance — scales with channel and a bit of randomness
    base_ctr = {"Meta": 1.8, "Google": 3.1, "Email": 2.4, "On-site Banner": 0.9}[asset.channel]
    asset.simulated_ctr = round(base_ctr * random.uniform(0.7, 1.4), 2)
    asset.simulated_conv_lift = round(random.uniform(2.5, 18.0), 1)
    log.append(LogEntry(
        timestamp=datetime.now(),
        agent="Deployment",
        message=f"Deployed {asset.sku_id} → {asset.channel} (sim CTR {asset.simulated_ctr}%).",
    ))
    return asset


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────

def init_state() -> None:
    if "catalogue" not in st.session_state:
        st.session_state.catalogue = generate_catalogue()
    if "signals" not in st.session_state:
        st.session_state.signals = generate_signals(st.session_state.catalogue)
    if "log" not in st.session_state:
        st.session_state.log = []
    if "deployed_assets" not in st.session_state:
        st.session_state.deployed_assets = []
    if "draft_assets" not in st.session_state:
        st.session_state.draft_assets = []
    if "cycles_run" not in st.session_state:
        st.session_state.cycles_run = 0
    if "merch_prompt" not in st.session_state:
        st.session_state.merch_prompt = DEFAULT_MERCHANDISER_PROMPT
    if "creative_prompt" not in st.session_state:
        st.session_state.creative_prompt = DEFAULT_CREATIVE_PROMPT
    if "pending_picks" not in st.session_state:
        st.session_state.pending_picks = []
    if "data_source" not in st.session_state:
        st.session_state.data_source = "synthetic"


# ─────────────────────────────────────────────────────────────────────────────
# CYCLE ORCHESTRATION
# ─────────────────────────────────────────────────────────────────────────────

def run_cycle(
    autonomy: str,
    top_n: int,
    channels_enabled: list[str],
    api_key: str,
) -> None:
    """End-to-end: signals → merchandise → create → (approve?) → deploy."""
    client = _claude_client(api_key)
    log = st.session_state.log

    log.append(LogEntry(
        timestamp=datetime.now(),
        agent="Orchestrator",
        message=f"=== Cycle {st.session_state.cycles_run + 1} starting (autonomy: {autonomy}) ===",
    ))

    # 1. Merchandiser
    picks = merchandiser_agent(
        st.session_state.catalogue,
        st.session_state.signals,
        top_n,
        client,
        st.session_state.merch_prompt,
        log,
    )
    if not picks:
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Orchestrator",
            message="No picks returned — ending cycle.",
        ))
        return

    # 2. Creative — one asset per (pick × channel)
    drafts: list[CreativeAsset] = []
    for pick in picks:
        for channel in channels_enabled:
            asset = creative_agent(
                pick,
                st.session_state.catalogue,
                st.session_state.signals,
                channel,
                client,
                st.session_state.creative_prompt,
                log,
            )
            if asset:
                drafts.append(asset)

    # 3. Deploy — gated by autonomy level
    if autonomy == "Fully autonomous":
        for a in drafts:
            deployment_agent(a, log)
            st.session_state.deployed_assets.append(a)
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Orchestrator",
            message=f"Auto-deployed {len(drafts)} assets across {len(channels_enabled)} channels.",
        ))
    else:
        # Park the drafts for human review on the Deployed tab
        st.session_state.draft_assets.extend(drafts)
        log.append(LogEntry(
            timestamp=datetime.now(),
            agent="Orchestrator",
            message=f"{len(drafts)} drafts awaiting approval (mode: {autonomy}).",
        ))

    st.session_state.cycles_run += 1


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

def sidebar() -> tuple[str, int, list[str], str]:
    st.sidebar.title("🛒 Agentic Commerce Studio")
    st.sidebar.caption("Autonomous retail orchestration prototype")

    st.sidebar.markdown("---")
    st.sidebar.subheader("API")
    api_key = st.sidebar.text_input(
        "Anthropic API Key",
        type="password",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        help="Without a key, agents run in deterministic rule-based mode (still fully functional).",
    )
    if not ANTHROPIC_AVAILABLE:
        st.sidebar.warning("`anthropic` package not installed — running in fallback mode.")
    elif not api_key:
        st.sidebar.info("No API key — running in rule-based fallback mode.")
    else:
        st.sidebar.success("Claude API ready.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Cycle Configuration")
    autonomy = st.sidebar.select_slider(
        "Autonomy level",
        options=["Manual", "Approve each step", "Fully autonomous"],
        value="Approve each step",
    )
    top_n = st.sidebar.slider("SKUs to promote per cycle", 1, 8, 3)
    channels_enabled = st.sidebar.multiselect(
        "Channels to deploy to",
        CHANNELS,
        default=["Meta", "Google", "Email"],
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Data")

    # Show what's currently loaded
    source = st.session_state.get("data_source", "synthetic")
    badge = "📦 Synthetic" if source == "synthetic" else "📤 Uploaded"
    st.sidebar.caption(
        f"{badge} · {len(st.session_state.catalogue)} SKUs · "
        f"{len(st.session_state.signals)} signals"
    )

    with st.sidebar.expander("📤 Bring your own data (CSV)"):
        st.caption(
            "Upload a real catalogue or signals feed. Required columns are "
            "validated; missing optional ones are auto-filled."
        )

        st.markdown("**Catalogue CSV**")
        st.caption(f"Required: `{', '.join(sorted(CATALOGUE_REQUIRED))}`")
        st.download_button(
            "📥 Template",
            data=catalogue_csv_template(),
            file_name="catalogue_template.csv",
            mime="text/csv",
            key="dl_cat_template",
            use_container_width=True,
        )
        cat_upload = st.file_uploader(
            "Upload catalogue",
            type=["csv"],
            key="cat_uploader",
            label_visibility="collapsed",
        )
        if cat_upload is not None:
            df, msgs = ingest_catalogue_csv(cat_upload)
            for m in msgs:
                st.caption(m)
            if df is not None and st.button("Use this catalogue", key="apply_cat"):
                st.session_state.catalogue = df
                st.session_state.data_source = "uploaded"
                # Re-generate signals against the new catalogue's categories
                st.session_state.signals = generate_signals(df)
                st.success("Catalogue replaced. Signals regenerated.")
                st.rerun()

        st.markdown("**Signals CSV** *(optional)*")
        st.caption(f"Required: `{', '.join(sorted(SIGNALS_REQUIRED))}`")
        st.download_button(
            "📥 Template",
            data=signals_csv_template(),
            file_name="signals_template.csv",
            mime="text/csv",
            key="dl_sig_template",
            use_container_width=True,
        )
        sig_upload = st.file_uploader(
            "Upload signals",
            type=["csv"],
            key="sig_uploader",
            label_visibility="collapsed",
        )
        if sig_upload is not None:
            sigs, msgs = ingest_signals_csv(sig_upload, st.session_state.catalogue)
            for m in msgs:
                st.caption(m)
            if sigs is not None and st.button("Use these signals", key="apply_sig"):
                st.session_state.signals = sigs
                st.success("Signals replaced.")
                st.rerun()

    if st.sidebar.button("🔄 Refresh signals"):
        st.session_state.signals = generate_signals(st.session_state.catalogue)
        st.sidebar.success("New signals generated.")
    if st.sidebar.button("♻️ Regenerate synthetic catalogue"):
        st.session_state.catalogue = generate_catalogue(seed=random.randint(0, 9999))
        st.session_state.signals = generate_signals(st.session_state.catalogue)
        st.session_state.data_source = "synthetic"
        st.sidebar.success("New synthetic catalogue + signals.")

    st.sidebar.markdown("---")
    run = st.sidebar.button("▶️ Run Cycle", type="primary", use_container_width=True)
    if run:
        if not channels_enabled:
            st.sidebar.error("Pick at least one channel.")
        else:
            with st.spinner("Agents working…"):
                run_cycle(autonomy, top_n, channels_enabled, api_key)
            st.sidebar.success("Cycle complete.")

    if st.sidebar.button("🗑️ Reset session", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    return autonomy, top_n, channels_enabled, api_key


def tab_live_state() -> None:
    st.subheader("Synthesised Live State")
    st.caption(
        "The Data Synthesis Layer joins product metadata, image library, and "
        "live customer signals into a single state that agents reason over."
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### Product Catalogue")
        st.dataframe(
            st.session_state.catalogue,
            use_container_width=True,
            height=400,
            column_config={
                "image_url": st.column_config.ImageColumn("image", width="small"),
                "price": st.column_config.NumberColumn("price", format="£%.2f"),
                "margin_pct": st.column_config.NumberColumn("margin", format="%.0f%%"),
            },
        )

    with col2:
        st.markdown("#### Live Signals")
        for sig in st.session_state.signals:
            intensity_bar = "🟥" * int(sig.intensity * 5) + "⬜" * (5 - int(sig.intensity * 5))
            st.markdown(
                f"**{sig.type}** — *{sig.affected_category}*  \n"
                f"{sig.description}  \n"
                f"{intensity_bar} `{sig.intensity}`"
            )
            st.markdown("---")

    st.markdown("#### Synthesised Priority View")
    st.caption("Categories ranked by aggregate signal intensity × in-stock SKU count.")
    if st.session_state.signals:
        sig_df = pd.DataFrame([
            {"category": s.affected_category, "intensity": s.intensity, "type": s.type}
            for s in st.session_state.signals
        ])
        agg = sig_df.groupby("category")["intensity"].sum().reset_index()
        stock = (
            st.session_state.catalogue[st.session_state.catalogue["stock_level"] >= 20]
            .groupby("category")
            .size()
            .reset_index(name="in_stock_skus")
        )
        priority = agg.merge(stock, on="category", how="left").fillna(0)
        priority["priority_score"] = (
            priority["intensity"] * priority["in_stock_skus"]
        ).round(2)
        priority = priority.sort_values("priority_score", ascending=False)
        st.dataframe(priority, use_container_width=True, hide_index=True)


def tab_agent_activity() -> None:
    st.subheader("Agent Activity")
    st.caption("Three agents, three responsibilities. Watch the handoff.")

    col_m, col_c, col_d = st.columns(3)

    with col_m:
        st.markdown("### 🧭 Merchandiser")
        st.caption("Decides what to promote.")
        merch_logs = [l for l in st.session_state.log if l.agent == "Merchandiser"]
        for entry in merch_logs[-10:][::-1]:
            with st.container(border=True):
                st.markdown(f"**{entry.timestamp.strftime('%H:%M:%S')}** — {entry.message}")
                if entry.reasoning:
                    with st.expander("reasoning"):
                        st.code(entry.reasoning, language="text")

    with col_c:
        st.markdown("### ✍️ Creative")
        st.caption("Writes the ads.")
        creative_logs = [l for l in st.session_state.log if l.agent == "Creative"]
        for entry in creative_logs[-10:][::-1]:
            with st.container(border=True):
                st.markdown(f"**{entry.timestamp.strftime('%H:%M:%S')}** — {entry.message}")
                if entry.reasoning:
                    st.caption(entry.reasoning)

    with col_d:
        st.markdown("### 🚀 Deployment")
        st.caption("Ships to channels.")
        deploy_logs = [l for l in st.session_state.log if l.agent == "Deployment"]
        for entry in deploy_logs[-10:][::-1]:
            with st.container(border=True):
                st.markdown(f"**{entry.timestamp.strftime('%H:%M:%S')}** — {entry.message}")

    st.markdown("---")
    st.markdown("### 📋 Full Event Log")
    if st.session_state.log:
        log_df = pd.DataFrame([
            {
                "time": l.timestamp.strftime("%H:%M:%S"),
                "agent": l.agent,
                "message": l.message,
            }
            for l in st.session_state.log[::-1]
        ])
        st.dataframe(log_df, use_container_width=True, hide_index=True, height=250)
    else:
        st.info("Run a cycle to populate the log.")


def tab_deployed() -> None:
    st.subheader("Creative Gallery")

    drafts = st.session_state.draft_assets
    if drafts:
        st.markdown(f"### ⏳ Drafts awaiting approval ({len(drafts)})")
        approve_all = st.button("✅ Approve & deploy all drafts", type="primary")
        if approve_all:
            for a in drafts:
                deployment_agent(a, st.session_state.log)
                st.session_state.deployed_assets.append(a)
            st.session_state.draft_assets = []
            st.rerun()

        cols = st.columns(3)
        for idx, asset in enumerate(drafts):
            with cols[idx % 3]:
                _render_creative_card(asset, draft=True, idx=idx)
        st.markdown("---")

    deployed = st.session_state.deployed_assets
    st.markdown(f"### ✅ Deployed ({len(deployed)})")
    if not deployed:
        st.info("No assets deployed yet.")
        return

    cols = st.columns(3)
    for idx, asset in enumerate(deployed[::-1]):
        with cols[idx % 3]:
            _render_creative_card(asset, draft=False, idx=idx)


def _render_creative_card(asset: CreativeAsset, draft: bool, idx: int) -> None:
    with st.container(border=True):
        st.image(asset.image_url, use_container_width=True)
        channel_emoji = {"Meta": "📘", "Google": "🔍", "Email": "📧", "On-site Banner": "🌐"}
        st.markdown(f"**{channel_emoji.get(asset.channel, '📡')} {asset.channel}** · `{asset.sku_id}`")
        st.markdown(f"### {asset.headline}")
        st.write(asset.body)
        st.markdown(f"**[ {asset.cta} ]**")
        st.caption(f"Triggered by: *{asset.triggering_signal}*")
        if draft:
            if st.button("Approve", key=f"approve-{idx}-{asset.sku_id}-{asset.channel}"):
                deployment_agent(asset, st.session_state.log)
                st.session_state.deployed_assets.append(asset)
                st.session_state.draft_assets.remove(asset)
                st.rerun()
        else:
            st.caption(
                f"Deployed {asset.deployed_at.strftime('%H:%M:%S') if asset.deployed_at else '—'} · "
                f"sim CTR {asset.simulated_ctr}% · conv lift {asset.simulated_conv_lift}%"
            )


def tab_metrics() -> None:
    st.subheader("Simulated Performance")
    deployed = st.session_state.deployed_assets

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cycles run", st.session_state.cycles_run)
    c2.metric("Assets deployed", len(deployed))
    c3.metric(
        "Avg simulated CTR",
        f"{sum(a.simulated_ctr for a in deployed) / len(deployed):.2f}%" if deployed else "—",
    )
    c4.metric(
        "Avg conv lift",
        f"{sum(a.simulated_conv_lift for a in deployed) / len(deployed):.1f}%" if deployed else "—",
    )

    if not deployed:
        st.info("Deploy some assets to see performance.")
        return

    st.markdown("---")
    perf_df = pd.DataFrame([
        {
            "channel": a.channel,
            "sku_id": a.sku_id,
            "ctr": a.simulated_ctr,
            "conv_lift": a.simulated_conv_lift,
            "deployed_at": a.deployed_at,
        }
        for a in deployed
    ])

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### CTR by channel")
        ctr_by_channel = perf_df.groupby("channel")["ctr"].mean().reset_index()
        st.bar_chart(ctr_by_channel, x="channel", y="ctr")
    with col_b:
        st.markdown("#### Conversion lift by channel")
        lift_by_channel = perf_df.groupby("channel")["conv_lift"].mean().reset_index()
        st.bar_chart(lift_by_channel, x="channel", y="conv_lift")

    st.markdown("#### All deployed assets")
    st.dataframe(perf_df, use_container_width=True, hide_index=True)


def advanced_panel() -> None:
    with st.expander("⚙️ Advanced — Edit agent prompts (architecture is inspectable)"):
        st.caption(
            "These prompts drive Claude when an API key is provided. "
            "Edit them to change agent behaviour without touching code."
        )
        st.session_state.merch_prompt = st.text_area(
            "Merchandiser Agent prompt",
            value=st.session_state.merch_prompt,
            height=200,
        )
        st.session_state.creative_prompt = st.text_area(
            "Creative Agent prompt",
            value=st.session_state.creative_prompt,
            height=200,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    init_state()
    sidebar()

    st.title("Agentic Commerce Studio")
    st.caption(
        "From product to purchase, autonomously. "
        "Three agents — Merchandiser, Creative, Deployment — coordinate to "
        "turn live signals into deployed creative at scale."
    )

    advanced_panel()

    tab1, tab2, tab3, tab4 = st.tabs([
        "🗂️ Live State",
        "🤖 Agent Activity",
        "🎨 Deployed Creative",
        "📊 Metrics",
    ])
    with tab1:
        tab_live_state()
    with tab2:
        tab_agent_activity()
    with tab3:
        tab_deployed()
    with tab4:
        tab_metrics()


if __name__ == "__main__":
    main()
