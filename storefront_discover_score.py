"""
Storefront Index - self-seeding discovery + scoring, single file.
Only input is PSI_API_KEY. Seeds candidates from the free Tranco list,
keeps UK/US online stores (any platform), classifies niche, ranks, scores.
Non-Shopify => Migrate. Shopify-standard that is big enough => Plus-ready.
"""
from __future__ import annotations
import os, sys, csv, json

# ===== fingerprints.py =====
"""
Fingerprint a storefront's HTML for the app/tech signals that map to the five
non-speed dimensions in the proposal:

  trust    - reviews, ratings, guarantees, trust badges
  upsell   - bundles, cross-sell, cart upsell, "frequently bought"
  value    - loyalty, rewards, subscriptions, offers
  ux       - search, wishlist, mega-nav, quick view, currency/geo
  friction - express checkout, cart drawer, guest checkout signals

Each signal is a known vendor script marker or a robust on-page pattern. These
are deliberately conservative: a hit is real evidence the capability exists.
Absence is weaker evidence, so scores lean on presence.
"""

import re

# dimension -> {signal_name: [substrings that, if any present, count as a hit]}
SIGNATURES = {
    "trust": {
        "reviews_app": ["judge.me", "yotpo", "okendo", "loox", "stamped.io",
                        "reviews.io", "trustpilot", "feefo", "reviewsio", "kudobuzz",
                        "opinew", "fera.ai", "junip", "shopper-approved", "reviewscouk",
                        "trustspot", "reviewbit", "ali-reviews", "growave-reviews",
                        "rivyo", "helpfulcrowd", "verified-reviews", "bazaarvoice",
                        "powerreviews", "reviewsapp", "trustpulse", "judgeme"],
        "star_rating": ["aggregateRating", "star-rating", "jdgm-prev-badge",
                        "yotpo-stars", "okeReviews", "loox-rating", "stamped-badge",
                        "spr-badge", "jdgm-widget", "star-rating__count", "ruk_rating",
                        "review-stars", "rating-star"],
        "guarantee": ["money-back", "money back guarantee", "satisfaction guarantee",
                      "30-day", "60-day", "90-day", "risk-free", "lifetime warranty",
                      "lifetime guarantee", "warranty", "guaranteed"],
        "trust_badge": ["trust-badge", "secure checkout", "norton", "mcafee",
                        "trustbadge", "trust badges", "ssl secure", "verified by",
                        "trust-seal", "secure-payment", "as seen in", "as-seen-in",
                        "featured in"],
        "returns": ["free returns", "free return", "easy returns", "hassle-free returns",
                    "30 day returns", "free exchanges", "no-quibble", "returns policy"],
    },
    "upsell": {
        "upsell_app": ["rebuy", "reconvert", "zipify", "bold-upsell", "selleasy",
                       "aftersell", "candyrack", "upsellplus", "in-cart-upsell",
                       "frequently-bought", "honeycomb-upsell", "unlimitedupsell",
                       "vitals", "carthook", "monster-upsells", "kaching", "corner-upsell",
                       "personalizer", "wiser", "limespot", "nosto", "rebuyengine",
                       "product-recommendations", "adoric"],
        "cross_sell_ui": ["frequently bought", "you may also like", "complete the look",
                          "pairs well with", "goes well with", "recommended for you",
                          "customers also bought", "complete-the-look", "you might also",
                          "shop the look", "pairs-with", "related products",
                          "you-may-also-like", "recently viewed", "more from"],
        "bundles": ["bundle", "buy-the-set", "shop the set", "build-a-bundle",
                    "fast-bundle", "bundle-builder", "buy-more-save", "build-your-own",
                    "mix and match", "kit-builder", "set & save", "starter kit",
                    "buy 2 get", "multibuy"],
        "cart_upsell": ["cart-upsell", "cart-drawer-upsell", "rebuy-cart",
                        "cart-recommendations", "add-on", "you're almost there",
                        "free-shipping-bar", "cart-goal", "spend-x-more", "gift-with-purchase"],
    },
    "value": {
        "loyalty_app": ["smile.io", "smile-ui", "loyaltylion", "swell", "yotpo-loyalty",
                        "okendo-loyalty", "loyalty-rewards", "growave", "rivo",
                        "stamped-loyalty", "marsello", "joy-loyalty", "bon-loyalty",
                        "loyaltylion.io", "smileio", "yotpo.com/loyalty", "loyalty-lion",
                        "influence.io"],
        "rewards_ui": ["rewards", "earn points", "loyalty program", "points balance",
                       "refer a friend", "referral", "vip tier", "reward points",
                       "join rewards", "loyalty-rewards", "earn-points", "member-perks"],
        "subscription": ["recharge", "rechargepayments", "bold-subscriptions",
                         "ordergroove", "appstle", "seal-subscriptions", "skio",
                         "subscribe & save", "subscribe and save", "subscription",
                         "loop-subscriptions", "smartrr", "recurring", "subscribe-save",
                         "stay-ai", "subify", "subscribe now", "auto-renew"],
        "offers": ["announcement-bar", "welcome offer", "10% off", "15% off",
                   "sign up and save", "first order", "student discount", "20% off",
                   "newsletter-signup", "email-signup", "spin-to-win", "klaviyo-form",
                   "privy", "sign up for", "first-order-discount", "unlock 10"],
    },
    "ux": {
        "predictive_search": ["predictive-search", "searchanise", "algolia",
                              "boost-pfs", "instant-search", "search-drawer",
                              "klevu", "findify", "searchspring", "fast-simon",
                              "instant-search-plus", "predictive_search", "search-modal",
                              "autocomplete-search", "typesense"],
        "wishlist": ["wishlist", "wishlist-hero", "swym", "add to wishlist",
                     "wishlist-king", "growave-wishlist", "save for later", "favourites",
                     "add-to-wishlist", "wishlisthero"],
        "mega_nav": ["mega-menu", "megamenu", "mega_menu", "header__submenu",
                     "mega-nav", "nav-dropdown", "header-menu__submenu", "dropdown-menu"],
        "quick_view": ["quick-view", "quickview", "quick-add", "quick shop", "quick-shop",
                       "quickshop", "quick_add", "product-quick", "quickbuy"],
        "geo_currency": ["currency-selector", "geolocation", "country-selector",
                         "localization-form", "shopify-currency", "market-selector",
                         "currency-picker", "country-currency", "geo-redirect",
                         "localisation", "shopify-payment-terms"],
    },
    "friction": {
        "express_checkout": ["shop-pay", "shopify-payment-button", "apple-pay",
                             "google-pay", "paypal", "amazon-pay", "dynamic-checkout",
                             "shoppay", "gpay", "shop_pay", "klarna", "clearpay",
                             "afterpay", "installments", "shop-pay-installments"],
        "cart_drawer": ["cart-drawer", "js-drawer", "mini-cart", "ajax-cart",
                        "slide-cart", "side-cart", "drawer-cart", "cart-slideout",
                        "cart__drawer", "slideout-cart", "cart-popup"],
        "sticky_atc": ["sticky-atc", "sticky-add-to-cart", "sticky-buy", "buybar",
                       "sticky-product-form", "sticky-cart", "floating-atc",
                       "product-sticky", "sticky-purchase"],
        "guest_checkout": ["guest checkout", "checkout as guest", "continue as guest",
                           "guest-checkout"],
        "accelerated": ["accelerated-checkout", "one-click", "express-checkout",
                        "one-page-checkout", "buy-now", "buy-it-now", "buy_now"],
    },
}


def fingerprint(html: str) -> dict:
    """Return {dimension: {signal: bool}} for one HTML document."""
    text = (html or "").lower()
    out: dict[str, dict] = {}
    for dim, sigs in SIGNATURES.items():
        out[dim] = {}
        for name, needles in sigs.items():
            out[dim][name] = any(n.lower() in text for n in needles)
    return out


def merge_signals(*fingerprints: dict) -> dict:
    """OR-merge several page fingerprints into one (a capability seen on any page counts)."""
    merged: dict[str, dict] = {}
    for fp in fingerprints:
        if not fp:
            continue
        for dim, sigs in fp.items():
            merged.setdefault(dim, {})
            for name, hit in sigs.items():
                merged[dim][name] = merged[dim].get(name, False) or bool(hit)
    return merged

# ===== psi.py =====
"""
PageSpeed Insights client. Runs Lighthouse (lab) and returns CrUX (field) data
for a URL on mobile or desktop.

Get a free API key: https://developers.google.com/speed/docs/insights/v5/get-started
Free quota is generous (25,000 queries/day, 240/min). A full 300-store run at
3 pages x 2 strategies = ~1,800 calls, well inside a single day's quota.
"""

import time
import requests

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class PSIError(Exception):
    pass


def _audit_ms(audits: dict, key: str):
    a = audits.get(key) or {}
    v = a.get("numericValue")
    return round(float(v), 1) if v is not None else None


def _field(loading: dict):
    """Extract CrUX field metrics + overall category from loadingExperience."""
    if not loading:
        return {"lcp_ms": None, "inp_ms": None, "cls": None, "overall": None}
    m = loading.get("metrics", {}) or {}

    def p(metric):
        d = m.get(metric) or {}
        return d.get("percentile")

    lcp = p("LARGEST_CONTENTFUL_PAINT_MS")
    inp = p("INTERACTION_TO_NEXT_PAINT") or p("EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT")
    cls_raw = p("CUMULATIVE_LAYOUT_SHIFT_SCORE")
    cls = round(cls_raw / 100.0, 3) if cls_raw is not None else None  # CrUX CLS is x100
    return {
        "lcp_ms": lcp, "inp_ms": inp, "cls": cls,
        "overall": loading.get("overall_category"),
    }


def measure(url: str, strategy: str = "mobile", api_key: str | None = None,
            max_retries: int = 3, pause: float = 0.6) -> dict:
    """Return a speed block for one URL. Raises PSIError on hard failure."""
    params = {
        "url": url,
        "strategy": strategy,
        "category": "performance",
    }
    if api_key:
        params["key"] = api_key
    last = None
    for attempt in range(max_retries):
        try:
            r = requests.get(ENDPOINT, params=params, timeout=90)
            if r.status_code == 200:
                return _parse(r.json(), strategy)
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            # 429/500-class: back off and retry
            if r.status_code in (429, 500, 502, 503):
                time.sleep(pause * (2 ** attempt))
                continue
            raise PSIError(last)
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(pause * (2 ** attempt))
    raise PSIError(last or "unknown PSI error")


def _parse(data: dict, strategy: str) -> dict:
    lh = data.get("lighthouseResult", {}) or {}
    cats = lh.get("categories", {}) or {}
    audits = lh.get("audits", {}) or {}
    perf = cats.get("performance", {}).get("score")
    # Prefer page-level field data, fall back to origin-level.
    field = _field(data.get("loadingExperience"))
    if field["overall"] is None:
        field = _field(data.get("originLoadingExperience"))
    return {
        "strategy": strategy,
        "performance": round(perf * 100) if perf is not None else None,
        "lcp_ms": _audit_ms(audits, "largest-contentful-paint"),
        "cls": (lambda a: round(float(a["numericValue"]), 3)
                if a.get("numericValue") is not None else None)(audits.get("cumulative-layout-shift", {})),
        "tbt_ms": _audit_ms(audits, "total-blocking-time"),
        "si_ms": _audit_ms(audits, "speed-index"),
        "fcp_ms": _audit_ms(audits, "first-contentful-paint"),
        "field": field,
    }

# ===== resolve.py =====
"""
Resolve a domain to a live storefront, detect the platform, and pick the three
page types to measure (home, a real collection, a real PDP).

Network-touching. Requires outbound HTTPS to the target sites. Will not run
inside a locked-down sandbox; runs fine locally or in CI.
"""

import json
import re
import time
from urllib.parse import urljoin, urlparse

import requests

UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1 "
    "StorefrontIndexBot/0.1 (+benchmark; contact rainycityagency.com)"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9"}
# (connect, read) timeout. Short, so dead/slow domains fail fast during the
# high-volume discovery sweep instead of tying up a worker for 20s each.
TIMEOUT = (5, 9)


def _get(url: str, **kw):
    return requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True, **kw)


def resolve_base(domain: str) -> tuple[str | None, requests.Response | None, list[str]]:
    """Return (final_url, response, errors). Tries https, then bare, follows redirects."""
    errors: list[str] = []
    candidates = []
    d = domain.strip().lower().rstrip("/")
    if not d.startswith("http"):
        candidates = [f"https://{d}", f"https://www.{d}"]
    else:
        candidates = [d]
    for url in candidates:
        try:
            r = _get(url)
            if r.status_code < 400 and r.text:
                return r.url, r, errors
            errors.append(f"{url} -> HTTP {r.status_code}")
        except requests.RequestException as e:
            errors.append(f"{url} -> {type(e).__name__}")
    return None, None, errors


SHOPIFY_HTML_MARKERS = (
    "cdn.shopify.com",
    "/cdn/shop/",
    "Shopify.theme",
    "shopify-section",
    "window.Shopify",
    "myshopify.com",
)


def detect_platform(resp: requests.Response) -> tuple[str, float]:
    """Return (platform, confidence)."""
    html = resp.text or ""
    headers = {k.lower(): v for k, v in resp.headers.items()}
    score = 0
    if any(h in headers for h in ("x-shopify-stage", "x-shopid", "x-sorting-hat-podid", "x-shardid")):
        score += 3
    if "powered-by" in headers and "shopify" in headers["powered-by"].lower():
        score += 3
    for m in SHOPIFY_HTML_MARKERS:
        if m in html:
            score += 1
    is_shopify = score >= 2
    if not is_shopify:
        # quick non-shopify platform hints (for the migrate flag)
        return ("other", 0.6 if score == 0 else 0.4)
    # Plus heuristic from externally-visible signals. Checkout extensibility is
    # Plus-native, so it's the strongest tell; explicit plus markers confirm.
    hl = html.lower()
    plus = 0
    if "checkout.shopifycs.com" in hl or "checkout-extensibility" in hl or '"extensibility"' in hl:
        plus += 2
    if re.search(r'"plus"\s*:\s*true', html):
        plus += 2
    if "shopify_plus" in hl or "shopifyplus" in hl or "shopify plus" in hl:
        plus += 2
    if "/apps/checkout" in hl or "checkout_ui_extensions" in hl:
        plus += 1
    if plus >= 2:
        return ("shopify_plus", min(0.9, 0.6 + 0.1 * plus))
    return ("shopify", min(1.0, 0.5 + 0.1 * score))


def _first_handle(url: str, key: str) -> str | None:
    try:
        r = _get(url)
        if r.status_code >= 400:
            return None
        data = r.json()
        items = data.get(key) or []
        for it in items:
            h = it.get("handle")
            if not h:
                continue
            if key == "collections" and h in ("frontpage", "all"):
                # skip the default catch-all if a real one exists later
                continue
            return h
        # fall back to first even if default
        if items and items[0].get("handle"):
            return items[0]["handle"]
    except (requests.RequestException, ValueError):
        return None
    return None


def discover_pages(base_url: str, platform: str) -> dict:
    """Pick home, collection and PDP URLs. Shopify exposes JSON endpoints we use."""
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    pages = {"home": {"url": root}, "collection": {"url": None}, "pdp": {"url": None}}

    if platform.startswith("shopify"):
        col = _first_handle(urljoin(root + "/", "collections.json?limit=10"), "collections")
        if col:
            pages["collection"]["url"] = f"{root}/collections/{col}"
        prod = _first_handle(urljoin(root + "/", "products.json?limit=10"), "products")
        if prod:
            pages["pdp"]["url"] = f"{root}/products/{prod}"

    # Fallbacks via sitemap or on-page links
    if not pages["collection"]["url"] or not pages["pdp"]["url"]:
        col, pdp = _scan_links_for_pages(root)
        pages["collection"]["url"] = pages["collection"]["url"] or col
        pages["pdp"]["url"] = pages["pdp"]["url"] or pdp

    # Last resort: measure the homepage for any missing slot, flagged by caller.
    for k in ("collection", "pdp"):
        if not pages[k]["url"]:
            pages[k]["url"] = root
            pages[k]["fallback_to_home"] = True
    return pages


def _scan_links_for_pages(root: str) -> tuple[str | None, str | None]:
    col = pdp = None
    try:
        r = _get(root)
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', r.text or "")
        for h in hrefs:
            full = urljoin(root + "/", h)
            if urlparse(full).netloc != urlparse(root).netloc:
                continue
            if not col and re.search(r"/(collections|shop|category|product-category)/", full):
                col = full.split("?")[0]
            if not pdp and re.search(r"/(products|product)/", full):
                pdp = full.split("?")[0]
            if col and pdp:
                break
    except requests.RequestException:
        pass
    return col, pdp


def resolve_store(brand: str, sector: str, domain: str) -> dict:
    """Full resolve step. Returns a partial StoreResult (no speed/scores yet)."""
    result = {
        "brand": brand, "sector": sector, "domain": domain,
        "resolved_url": None, "reachable": False, "platform": "unknown",
        "plan_confidence": 0.0, "pages": {}, "signals": {}, "errors": [], "flags": [],
    }
    final_url, resp, errors = resolve_base(domain)
    result["errors"].extend(errors)
    if not final_url or resp is None:
        return result
    result["resolved_url"] = final_url
    result["reachable"] = True
    platform, conf = detect_platform(resp)
    result["platform"] = platform
    result["plan_confidence"] = round(conf, 2)
    if platform == "other":
        result["flags"].append("non-shopify:migrate")
    elif platform == "shopify":
        result["flags"].append("non-plus:upgrade")
    result["pages"] = discover_pages(final_url, platform)
    # Keep the homepage HTML around for fingerprinting so we don't refetch.
    result["_home_html"] = resp.text
    return result

# ===== score.py =====
"""
Turn raw measurements and signals into six dimension scores (0..100), a composite
Storefront Score, and sector + benchmark rankings.

Scoring is transparent and defensible on purpose: every number traces back to a
Lighthouse metric or a detected capability, and the weights are declared here.
"""


# ---- composite weights (must sum to 1.0) --------------------------------------
DIMENSION_WEIGHTS = {
    "speed": 0.22,
    "friction": 0.20,
    "trust": 0.16,
    "upsell": 0.16,
    "value": 0.13,
    "ux": 0.13,
}

# page weighting for the speed dimension (PDP and collection matter most for revenue)
PAGE_WEIGHTS = {"pdp": 0.40, "collection": 0.35, "home": 0.25}

# per-signal weights inside each non-speed dimension
SIGNAL_WEIGHTS = {
    "trust": {"reviews_app": 3, "star_rating": 3, "guarantee": 2, "trust_badge": 1, "returns": 1},
    "upsell": {"upsell_app": 3, "cross_sell_ui": 3, "bundles": 2, "cart_upsell": 2},
    "value": {"loyalty_app": 3, "rewards_ui": 2, "subscription": 3, "offers": 2},
    "ux": {"predictive_search": 3, "wishlist": 2, "mega_nav": 2, "quick_view": 2, "geo_currency": 1},
    "friction": {"express_checkout": 3, "cart_drawer": 2, "sticky_atc": 2,
                 "guest_checkout": 2, "accelerated": 1},
}


# Core Web Vitals p75 thresholds (mobile field data): (good, poor), lower better.
CWV_THRESHOLDS = {"lcp_ms": (2500, 4000), "inp_ms": (200, 500), "cls": (0.1, 0.25)}
# Field metric weights (INP replaced FID; LCP is the headline load metric).
CWV_WEIGHTS = {"lcp_ms": 0.5, "inp_ms": 0.3, "cls": 0.2}


def _cwv_points(value, good, poor) -> float:
    """Map one lower-is-better metric to 0..100 against its good/poor thresholds."""
    if value is None:
        return None
    v = float(value)
    if v <= good:
        return 90 + 10 * (good - v) / good          # 90..100 within 'good'
    if v <= poor:
        return 50 + 40 * (poor - v) / (poor - good)  # 50..90 across the middle
    return max(0.0, 50 * (1 - (v - poor) / poor))    # 0..50 when 'poor'


def field_score(field: dict) -> float | None:
    """Real-user (CrUX) score 0..100 from LCP/INP/CLS, or None if no field data."""
    if not field:
        return None
    num = w = 0.0
    for metric, (good, poor) in CWV_THRESHOLDS.items():
        pts = _cwv_points(field.get(metric), good, poor)
        if pts is None:
            continue
        weight = CWV_WEIGHTS[metric]
        num += pts * weight
        w += weight
    return round(num / w, 1) if w else None


def score_speed(pages: dict) -> float | None:
    """Weighted speed across the three page types. Leads with CrUX field data
    (real users) where present; falls back to mobile Lighthouse lab score when a
    page has no field coverage. Returns 0..100 or None if no data at all."""
    total_w = 0.0
    acc = 0.0
    for ptype, weight in PAGE_WEIGHTS.items():
        page = pages.get(ptype) or {}
        speed = page.get("speed") or {}
        fs = field_score(speed.get("field") or {})
        if fs is not None:
            val = fs                       # real-user data leads
        else:
            perf = speed.get("performance")
            if perf is None:
                continue
            val = float(perf)              # lab fallback when no CrUX coverage
        acc += val * weight
        total_w += weight
    if total_w == 0:
        return None
    return round(acc / total_w, 1)


def score_signal_dimension(signals: dict, dim: str) -> float:
    """0..100 for a signal-based dimension from merged fingerprints."""
    weights = SIGNAL_WEIGHTS[dim]
    got = signals.get(dim, {}) or {}
    max_w = sum(weights.values())
    earned = sum(w for sig, w in weights.items() if got.get(sig))
    return round(100.0 * earned / max_w, 1) if max_w else 0.0


def score_store(store: dict) -> dict:
    """Fill store['dimensions'] and store['score']. Mutates and returns store."""
    dims: dict[str, float | None] = {}
    dims["speed"] = score_speed(store.get("pages", {}))
    for dim in ("trust", "upsell", "value", "ux", "friction"):
        dims[dim] = score_signal_dimension(store.get("signals", {}), dim)
    store["dimensions"] = dims

    # composite: renormalise over dimensions that actually have data
    num = 0.0
    wsum = 0.0
    for dim, w in DIMENSION_WEIGHTS.items():
        v = dims.get(dim)
        if v is None:
            continue
        num += v * w
        wsum += w
    store["score"] = round(num / wsum, 1) if wsum else None
    return store


def _rank(items, key):
    """Return dict id->(rank, size) ranking items desc by key (None sorts last)."""
    ranked = sorted(items, key=lambda s: (s.get(key) is not None, s.get(key) or -1), reverse=True)
    size = len(ranked)
    out = {}
    for i, s in enumerate(ranked, 1):
        out[s["domain"]] = (i, size)
    return out


def rank_all(stores: list[dict], previous: dict | None = None) -> list[dict]:
    """Add sector_rank, benchmark_rank, percentile and quarter-movement to each store.

    `previous` is an optional {domain: {"score":..,"sector_rank":..,"benchmark_rank":..}}
    from a prior run, enabling year-over-year movement and 'overtaken by' logic.
    """
    scored = [s for s in stores if s.get("score") is not None]
    # benchmark-wide
    bench = _rank(scored, "score")
    # per sector
    sectors: dict[str, list] = {}
    for s in scored:
        sectors.setdefault(s["sector"], []).append(s)
    sector_ranks: dict[str, tuple] = {}
    for sec, group in sectors.items():
        sector_ranks.update(_rank(group, "score"))

    # per-dimension percentile + quartile WITHIN each sector, so a store can see
    # exactly where it's strong or weak against direct competitors.
    dim_pct: dict[str, dict] = {}
    dim_q: dict[str, dict] = {}
    for sec, group in sectors.items():
        n = len(group)
        for dim in DIMENSION_WEIGHTS:
            vals = sorted((s["dimensions"].get(dim) for s in group
                           if s["dimensions"].get(dim) is not None))
            for s in group:
                v = s["dimensions"].get(dim)
                if v is None or not vals:
                    continue
                # percentile = share of sector at or below this value
                below = sum(1 for x in vals if x <= v)
                pct = round(100 * below / len(vals), 1)
                dim_pct.setdefault(s["domain"], {})[dim] = pct
                dim_q.setdefault(s["domain"], {})[dim] = min(4, int(pct // 25) + 1)

    for s in stores:
        d = s["domain"]
        if d in bench:
            br, bsize = bench[d]
            s["benchmark_rank"] = br
            s["benchmark_size"] = bsize
            s["percentile"] = round(100 * (bsize - br) / (bsize - 1), 1) if bsize > 1 else 100.0
        else:
            s["benchmark_rank"] = s["benchmark_size"] = None
            s["percentile"] = None
        if d in sector_ranks:
            sr, ssize = sector_ranks[d]
            s["sector_rank"] = sr
            s["sector_size"] = ssize
        else:
            s["sector_rank"] = s["sector_size"] = None
        s["dim_percentiles"] = dim_pct.get(d, {})
        s["dim_quartiles"] = dim_q.get(d, {})
        # movement
        s["movement"] = None
        if previous and d in previous and s.get("sector_rank") and previous[d].get("sector_rank"):
            s["movement"] = previous[d]["sector_rank"] - s["sector_rank"]  # +ve = moved up

    # who overtook whom within each sector (needs previous ranks)
    if previous:
        for sec, group in sectors.items():
            for s in group:
                d = s["domain"]
                prev_rank = previous.get(d, {}).get("sector_rank")
                if not prev_rank or not s.get("sector_rank"):
                    continue
                overtakers = []
                for other in group:
                    od = other["domain"]
                    o_prev = previous.get(od, {}).get("sector_rank")
                    if not o_prev or od == d:
                        continue
                    # other was behind us and is now ahead
                    if o_prev > prev_rank and other["sector_rank"] < s["sector_rank"]:
                        overtakers.append(other["brand"])
                s["overtaken_by"] = overtakers
    return stores


def sector_benchmarks(stores: list[dict]) -> dict:
    """Per-sector averages for each dimension + composite, for the whitepaper."""
    out: dict[str, dict] = {}
    by_sector: dict[str, list] = {}
    for s in stores:
        if s.get("score") is None:
            continue
        by_sector.setdefault(s["sector"], []).append(s)
    for sec, group in by_sector.items():
        agg = {"n": len(group), "score": _avg([s["score"] for s in group])}
        for dim in DIMENSION_WEIGHTS:
            agg[dim] = _avg([s["dimensions"].get(dim) for s in group])
        out[sec] = agg
    return out


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None

# ===== emails.py =====
"""
Generate the two outbound assets:

1. Benchmark email  - the quarterly unsolicited note: "You're 14th of 27 in
   Beauty. Trinny London is one place ahead. Here's your weakest area."
2. Comparison email - the booth output: a named store vs two named rivals across
   the six dimensions, with the gap and a clear next step.

Copy is written in Rainy City's register: direct, specific, no hype. Edit the
templates freely; the logic that selects the numbers is the valuable part.
"""


DIM_LABELS = {
    "speed": "Site speed",
    "friction": "Conversion friction",
    "trust": "Trust and social proof",
    "upsell": "Upsell and cross-sell",
    "value": "Added value (loyalty and offers)",
    "ux": "UX best practice",
}

# a concrete fix keyed to the weakest dimension
DIM_FIXES = {
    "speed": "Your mobile pages are slower than the sector median. The usual cause is unoptimised hero imagery and third-party scripts firing before content. Fixing it lifts conversion on paid traffic.",
    "friction": "You're missing express checkout paths that the leaders in your sector run as standard. Adding Shop Pay and accelerated checkout shortens the path to purchase.",
    "trust": "Reviews and ratings are thin or not surfaced on the product page. Stores above you display social proof at the point of decision.",
    "upsell": "No meaningful cross-sell or bundle mechanics detected. The leaders lift average order value with 'complete the look' and cart upsells.",
    "value": "No loyalty or subscription mechanic detected. In your sector, repeat purchase is where margin lives.",
    "ux": "Core storefront UX (predictive search, quick view, clear navigation) is behind the sector leaders, adding friction before the product page.",
}


def _rank_word(store):
    return f"{store['sector_rank']}{_ord(store['sector_rank'])} of {store['sector_size']}"


def _ord(n):
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def weakest_dimension(store):
    dims = {k: v for k, v in store.get("dimensions", {}).items() if v is not None}
    if not dims:
        return None
    return min(dims, key=dims.get)


def brand_above(store, all_stores):
    """The brand one place above this store in its sector, or None if top."""
    if not store.get("sector_rank") or store["sector_rank"] <= 1:
        return None
    target_rank = store["sector_rank"] - 1
    for s in all_stores:
        if s["sector"] == store["sector"] and s.get("sector_rank") == target_rank:
            return s
    return None


def build_benchmark_email(store: dict, all_stores: list[dict]) -> dict:
    """Return {subject, body} for the quarterly benchmark outreach."""
    sector = store["sector"]
    rank = _rank_word(store)
    above = brand_above(store, all_stores)
    weak = weakest_dimension(store)
    lines = []
    lines.append(f"Hi {{first_name}},")
    lines.append("")
    lines.append(
        f"We benchmarked {store['sector_size']} {sector.lower()} Shopify storefronts "
        f"for The State of Shopify Storefronts, our report with Shopify. "
        f"{store['brand']} came {rank}."
    )
    if above:
        gap = round((above["score"] or 0) - (store["score"] or 0), 1)
        lines.append("")
        if gap >= 0.1:
            lines.append(f"{above['brand']} sits one place above you, {gap} points "
                         f"ahead on the composite score.")
        else:
            lines.append(f"{above['brand']} sits one place above you, all but level "
                         f"on the composite score. One fix closes it.")
    # movement (year two+)
    mv = store.get("movement")
    if mv is not None and mv != 0:
        direction = "up" if mv > 0 else "down"
        lines.append("")
        lines.append(f"Since last quarter you moved {direction} {abs(mv)} "
                     f"place{'s' if abs(mv) != 1 else ''} in the sector.")
    if store.get("overtaken_by"):
        who = ", ".join(store["overtaken_by"])
        lines.append(f"{who} overtook you.")
    if weak:
        lines.append("")
        lines.append(f"Where you're losing ground: {DIM_LABELS[weak]}.")
        lines.append(DIM_FIXES[weak])
    lines.append("")
    lines.append(
        "Full sector breakdown and your line-by-line scores are in the report. "
        "Reply and I'll send your store's card."
    )
    lines.append("")
    lines.append("James")
    lines.append("Rainy City Agency")
    subject = f"{store['brand']}: {rank} in {sector} (Shopify storefront benchmark)"
    return {"subject": subject, "body": "\n".join(lines), "to_brand": store["brand"]}


def build_comparison_email(target: dict, rivals: list[dict]) -> dict:
    """Return {subject, body, table} for the booth 'you vs two rivals' output."""
    stores = [target] + rivals
    order = sorted(stores, key=lambda s: s.get("score") or -1, reverse=True)
    winner = order[0]
    dims = ["speed", "friction", "trust", "upsell", "value", "ux"]

    # build a compact comparison table (list of rows)
    header = ["Dimension"] + [s["brand"] for s in stores]
    rows = [header]
    for dim in dims:
        row = [DIM_LABELS[dim]]
        vals = [s["dimensions"].get(dim) for s in stores]
        best = max([v for v in vals if v is not None], default=None)
        for v in vals:
            mark = " *" if (v is not None and v == best) else ""
            row.append(f"{v if v is not None else '-'}{mark}")
        rows.append(row)
    rows.append(["Overall"] + [str(s.get("score") if s.get("score") is not None else "-") for s in stores])

    tpos = order.index(target) + 1
    lines = [f"Hi {{first_name}},", ""]
    lines.append(
        f"Here's how {target['brand']} scored against {rivals[0]['brand']} and "
        f"{rivals[1]['brand']}, live at the Shopify stand."
    )
    lines.append("")
    if winner["domain"] == target["domain"]:
        second = order[1]
        gap = round((target["score"] or 0) - (second["score"] or 0), 1)
        lines.append(f"You came out on top, {gap} points clear of {second['brand']}.")
    else:
        gap = round((winner["score"] or 0) - (target["score"] or 0), 1)
        lines.append(f"{winner['brand']} leads the three, {gap} points ahead of you. "
                     f"You placed {tpos} of 3.")
    weak = weakest_dimension(target)
    if weak:
        lines.append("")
        lines.append(f"Your biggest gap is {DIM_LABELS[weak].lower()}. {DIM_FIXES[weak]}")
    if "non-shopify:migrate" in target.get("flags", []):
        lines.append("")
        lines.append("Note: your store isn't on Shopify. The leaders here are. "
                     "That's the first conversation worth having.")
    elif "non-plus:upgrade" in target.get("flags", []):
        lines.append("")
        lines.append("You're on Shopify but not Plus. Several capabilities behind "
                     "the leaders are Plus-native.")
    lines.append("")
    lines.append("The full comparison and the sector report are attached.")
    lines.append("")
    lines.append("James, Rainy City Agency")
    subject = f"{target['brand']} vs {rivals[0]['brand']} and {rivals[1]['brand']} — your storefront comparison"
    return {"subject": subject, "body": "\n".join(lines), "table": rows, "to_brand": target["brand"]}


def render_table_text(rows: list[list[str]]) -> str:
    """ASCII table for plain-text email / console."""
    widths = [max(len(str(r[i])) for r in rows) for i in range(len(rows[0]))]
    out = []
    for idx, r in enumerate(rows):
        out.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)))
        if idx == 0:
            out.append("  ".join("-" * widths[i] for i in range(len(r))))
    return "\n".join(out)

# ===== render.py =====
"""
Render the benchmark to a single self-contained HTML dashboard, styled to the
Rainy City brand system (Instrument Serif headings, DM Mono body, Electric Blue
primary, Warm Amber complement, light surfaces). Co-branded Rainy City x Shopify.

No browser storage. Opens anywhere (fonts load from Google Fonts when online,
with system fallbacks).
"""

from jinja2 import Environment, BaseLoader



DIM_ORDER = ["speed", "friction", "trust", "upsell", "value", "ux"]
DIM_SHORT = {"speed": "Speed", "friction": "Friction", "trust": "Trust",
             "upsell": "Upsell", "value": "Value", "ux": "UX"}

TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The State of Shopify Storefronts — {{ meta.quarter }}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Mono:wght@400;500&display=swap');
  :root{
    --blue:#2563EB; --blue-hover:#1D4ED8; --blue-active:#1E40AF;
    --blue-light:#DBEAFE; --blue-muted:#93C5FD; --blue-subtle:#EFF6FF;
    --amber:#D97706; --amber-light:#FEF3C7; --amber-subtle:#FFFBEB; --amber-active:#B45309;
    --green:#16A34A; --green-subtle:#E7F6ED; --red:#DC2626; --red-subtle:#FDECEA;
    --ink:#0A0F1A; --navy:#1B2E5C; --body:#4A5568; --muted:#6B7686;
    --bg:#FAFBFC; --bg-2:#F0F2F5; --card:#FFFFFF; --line:#E6E9EF; --inverse:#0A0F1A;
    --serif:'Instrument Serif', Georgia, 'Times New Roman', serif;
    --mono:'DM Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:var(--mono);font-size:14px;line-height:1.6;color:var(--body);background:var(--bg);-webkit-font-smoothing:antialiased}
  .wrap{max-width:1200px;margin:0 auto;padding:40px 24px 72px}
  a{color:var(--blue);text-decoration:none}
  :focus-visible{outline:2px solid var(--blue);outline-offset:3px;border-radius:4px}

  header.top{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:28px}
  .lockup{display:flex;align-items:center;gap:9px;color:var(--ink)}
  .lockup svg{width:26px;height:21px;display:block}
  .wordmark{font-family:var(--serif);font-size:26px;line-height:1;letter-spacing:.01em}
  .cobrand{font-family:var(--mono);font-size:12px;color:var(--muted);margin-left:2px}
  .overline{font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:var(--blue);background:var(--blue-subtle);display:inline-block;padding:4px 10px;border-radius:99px;margin:18px 0 10px}
  h1{font-family:var(--serif);font-weight:400;font-size:44px;line-height:1.05;margin:6px 0 8px;color:var(--ink);letter-spacing:.005em}
  .sub{color:var(--body);max-width:680px;font-size:14px}
  .meta-right{font-family:var(--mono);font-size:12px;color:var(--muted);text-align:right}

  .stats{display:flex;gap:14px;flex-wrap:wrap;margin:26px 0 20px}
  .stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;min-width:150px;box-shadow:0 1px 2px rgba(10,15,26,.04)}
  .stat .n{font-family:var(--serif);font-size:34px;line-height:1;color:var(--ink)}
  .stat .l{color:var(--muted);font-size:11px;letter-spacing:.06em;text-transform:uppercase;margin-top:6px}

  .controls{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:10px 0 16px}
  label{font-size:12px;color:var(--muted)}
  select,input[type=search]{font-family:var(--mono);font-size:13px;padding:9px 11px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);min-height:40px}
  .legend{font-family:var(--mono);font-size:12px;color:var(--muted)}

  table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 1px 2px rgba(10,15,26,.04)}
  th,td{padding:11px 13px;text-align:left;border-bottom:1px solid var(--line);font-size:13px}
  th{background:#fff;cursor:pointer;user-select:none;white-space:nowrap;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--navy);font-weight:500}
  th.num,td.num{text-align:right}
  tbody tr:nth-child(even){background:#FCFCFD}
  tbody tr:hover{background:var(--blue-subtle)}
  tr:last-child td{border-bottom:none}
  .rankcell{font-weight:500;width:44px;color:var(--navy)}
  .brand{font-weight:500;color:var(--ink)}
  .dom{color:var(--muted);font-size:11px}
  .score{font-family:var(--serif);font-weight:400;font-size:20px;color:var(--ink)}
  .bar{position:relative;height:7px;background:var(--bg-2);border-radius:99px;min-width:64px}
  .bar > span{position:absolute;left:0;top:0;bottom:0;border-radius:99px;background:var(--blue)}
  .dimcell{min-width:80px}
  .dimval{font-size:11px;color:var(--muted);margin-bottom:4px}
  .dimval .pct{font-size:10px;opacity:.75}
  .dimcell.q1 .bar > span{background:var(--red)}
  .dimcell.q2 .bar > span{background:var(--amber)}
  .dimcell.q3 .bar > span{background:var(--blue)}
  .dimcell.q4 .bar > span{background:var(--green)}
  .flag{display:inline-block;font-size:11px;font-weight:500;padding:3px 9px;border-radius:99px;white-space:nowrap}
  .flag.migrate{background:var(--amber-subtle);color:var(--amber-active)}
  .flag.upgrade{background:var(--blue-subtle);color:var(--blue-active)}
  .flag.plus{background:var(--green-subtle);color:var(--green)}
  .mv-up{color:var(--green);font-weight:500}
  .mv-down{color:var(--red);font-weight:500}
  .mv-flat{color:var(--muted)}

  footer{margin-top:30px;color:var(--muted);font-size:12px}
  footer h3{font-family:var(--serif);font-weight:400;font-size:18px;color:var(--ink);margin:0 0 8px}
  .weightbar{display:flex;gap:0;height:24px;border-radius:8px;overflow:hidden;max-width:560px;margin-top:6px;border:1px solid var(--line)}
  .weightbar div{font-size:10px;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:500}
  .method{max-width:760px;line-height:1.7;margin-top:14px}
  .prepared{display:flex;align-items:center;gap:8px;margin-top:20px;color:var(--muted)}
  .prepared svg{width:18px;height:15px;color:var(--ink)}
</style></head>
<body><div class="wrap">
  <header class="top">
    <div>
      <div class="lockup">
        <svg viewBox="0 0 40 32" aria-hidden="true">
          <path fill="currentColor" d="M11 1s6 7 6 11a6 6 0 1 1-12 0C5 8 11 1 11 1Z"/>
          <path fill="currentColor" d="M29 1s6 7 6 11a6 6 0 1 1-12 0C23 8 29 1 29 1Z"/>
          <path fill="currentColor" d="M20 15s6 7 6 11a6 6 0 1 1-12 0C14 22 20 15 20 15Z"/>
        </svg>
        <span class="wordmark">rainy city</span>
        <span class="cobrand">× Shopify</span>
      </div>
      <div class="overline">The State of Shopify Storefronts</div>
      <h1>Six dimensions of the buying experience</h1>
      <div class="sub">How {{ meta.n_scored }} mid-market storefronts perform across speed, friction, trust, upsell, added value and UX. {{ meta.quarter }}.</div>
    </div>
    <div class="meta-right">Benchmark<br>{{ meta.generated }}</div>
  </header>

  <div class="stats">
    <div class="stat"><div class="n">{{ meta.n_scored }}</div><div class="l">Stores ranked</div></div>
    <div class="stat"><div class="n">{{ meta.n_sectors }}</div><div class="l">Sectors</div></div>
    <div class="stat"><div class="n">{{ meta.n_migrate }}</div><div class="l">Non-Shopify · migrate</div></div>
    <div class="stat"><div class="n">{{ meta.n_upgrade }}</div><div class="l">Non-Plus · upgrade</div></div>
    <div class="stat"><div class="n">{{ meta.median }}</div><div class="l">Median score</div></div>
  </div>

  <div class="controls">
    <label>Sector
      <select id="sector">
        <option value="">All sectors</option>
        {% for s in sectors %}<option value="{{ s }}">{{ s }}</option>{% endfor %}
      </select>
    </label>
    <label>Country
      <select id="country">
        <option value="">All</option>
        {% for c in countries %}<option value="{{ c }}">{{ c }}</option>{% endfor %}
      </select>
    </label>
    <input type="search" id="q" placeholder="Search brand…" aria-label="Search brand">
    <span class="legend">Composite = weighted mean of six dimensions. Dimension % = sector percentile; bar colour = quartile vs sector.</span>
  </div>

  <table id="tbl"><thead><tr>
    <th data-k="rank" class="num">#</th>
    <th data-k="brand">Brand</th>
    <th data-k="sector">Sector</th>
    <th data-k="country">Country</th>
    <th data-k="score" class="num">Score</th>
    {% for d in dim_order %}<th data-k="{{ d }}" class="num">{{ dim_short[d] }}</th>{% endfor %}
    <th data-k="mv" class="num">Δ</th>
    <th data-k="flag">Flag</th>
  </tr></thead><tbody>
  {% for s in stores %}
    <tr data-sector="{{ s.sector }}" data-brand="{{ s.brand|lower }}" data-country="{{ s.country }}">
      <td class="num rankcell">{{ s.benchmark_rank }}</td>
      <td><div class="brand">{{ s.brand }}</div><div class="dom">{{ s.domain }} · {{ s.sector_rank }}/{{ s.sector_size }} in sector</div></td>
      <td>{{ s.sector }}</td>
      <td>{{ s.country }}</td>
      <td class="num"><span class="score">{{ s.score }}</span></td>
      {% for d in dim_order %}
        {% set v = s.dimensions.get(d) %}
        {% set p = s.dim_percentiles.get(d) if s.dim_percentiles else none %}
        {% set q = s.dim_quartiles.get(d) if s.dim_quartiles else none %}
        <td class="num dimcell{{ ' q'~q if q else '' }}" data-v="{{ v if v is not none else -1 }}"
            title="{% if p is not none %}{{ p }}th percentile in {{ s.sector }} (Q{{ q }}){% else %}no sector comparison{% endif %}">
          <div class="dimval">{{ v if v is not none else '—' }}{% if p is not none %} <span class="pct">{{ p|round(0)|int }}%</span>{% endif %}</div>
          <div class="bar"><span style="width:{{ (v if v is not none else 0) }}%"></span></div>
        </td>
      {% endfor %}
      <td class="num" data-v="{{ s.movement if s.movement is not none else 0 }}">
        {% if s.movement is none %}<span class="mv-flat">—</span>
        {% elif s.movement > 0 %}<span class="mv-up">▲{{ s.movement }}</span>
        {% elif s.movement < 0 %}<span class="mv-down">▼{{ -s.movement }}</span>
        {% else %}<span class="mv-flat">–</span>{% endif %}
      </td>
      <td>
        {% if 'non-shopify:migrate' in s.flags %}<span class="flag migrate">Migrate</span>
        {% elif 'non-plus:upgrade' in s.flags %}<span class="flag upgrade">Plus-ready</span>
        {% elif s.platform == 'shopify_plus' %}<span class="flag plus">Plus</span>{% endif %}
      </td>
    </tr>
  {% endfor %}
  </tbody></table>

  <footer>
    <h3>Weighting</h3>
    <div class="weightbar">
      {% for d, w in weights.items() %}
        <div style="width:{{ (w*100)|round(0,'floor') }}%;background:{{ dim_colors[d] }}">{{ dim_short[d] }} {{ (w*100)|round(0,'floor')|int }}%</div>
      {% endfor %}
    </div>
    <p class="method">Speed leads with Google CrUX real-user field data (LCP, INP, CLS) where a store has coverage, falling back to mobile Lighthouse lab scores otherwise, weighted across homepage, collection and product pages. The other five dimensions are detected from each storefront's technology and on-page signals. Each dimension also shows the store's percentile against its own sector. Non-Shopify stores are flagged Migrate; Shopify-standard stores of sufficient scale are flagged Plus-ready.</p>
    <div class="prepared">
      <svg viewBox="0 0 40 32" aria-hidden="true">
        <path fill="currentColor" d="M11 1s6 7 6 11a6 6 0 1 1-12 0C5 8 11 1 11 1Z"/>
        <path fill="currentColor" d="M29 1s6 7 6 11a6 6 0 1 1-12 0C23 8 29 1 29 1Z"/>
        <path fill="currentColor" d="M20 15s6 7 6 11a6 6 0 1 1-12 0C14 22 20 15 20 15Z"/>
      </svg>
      Prepared by Rainy City Agency · rainycityagency.com
    </div>
  </footer>
</div>
<script>
(function(){
  var tbl=document.getElementById('tbl'), tb=tbl.tBodies[0];
  var rows=[].slice.call(tb.rows);
  var sector=document.getElementById('sector'), q=document.getElementById('q'), country=document.getElementById('country');
  function apply(){
    var sv=sector.value, qv=q.value.trim().toLowerCase(), cv=country.value;
    rows.forEach(function(r){
      var ok=(!sv||r.dataset.sector===sv)&&(!cv||r.dataset.country===cv)&&(!qv||r.dataset.brand.indexOf(qv)>-1);
      r.style.display=ok?'':'none';
    });
  }
  sector.addEventListener('change',apply); q.addEventListener('input',apply); country.addEventListener('change',apply);
  var dir={};
  [].forEach.call(tbl.tHead.rows[0].cells,function(th,ci){
    th.addEventListener('click',function(){
      var k=th.dataset.k; dir[k]=!dir[k]; var d=dir[k]?1:-1;
      var vis=rows.slice();
      vis.sort(function(a,b){
        var av=cell(a,ci), bv=cell(b,ci);
        if(av<bv)return -1*d; if(av>bv)return 1*d; return 0;
      });
      vis.forEach(function(r){tb.appendChild(r)});
    });
  });
  function cell(r,ci){
    var td=r.cells[ci];
    if(td.dataset.v!==undefined) return parseFloat(td.dataset.v);
    var t=td.textContent.trim(); var n=parseFloat(t);
    return isNaN(n)?t.toLowerCase():n;
  }
})();
</script>
</body></html>"""

# Brand-aligned dimension colours for the weighting bar (blue-led, amber accents).
DIM_COLORS = {
    "speed": "#2563EB", "friction": "#1E40AF", "trust": "#60A5FA",
    "upsell": "#D97706", "value": "#FBBF24", "ux": "#94A3B8",
}


def render_dashboard(stores: list[dict], meta: dict) -> str:
    ranked = sorted([s for s in stores if s.get("score") is not None],
                    key=lambda s: s["benchmark_rank"] or 9999)
    sectors = sorted({s["sector"] for s in ranked})
    countries = sorted({s.get("country") for s in ranked if s.get("country")})
    env = Environment(loader=BaseLoader(), autoescape=True)
    tpl = env.from_string(TEMPLATE)
    return tpl.render(
        stores=ranked, sectors=sectors, countries=countries, meta=meta,
        dim_order=DIM_ORDER, dim_short=DIM_SHORT,
        weights=DIMENSION_WEIGHTS, dim_colors=DIM_COLORS,
    )

# ===== discover.py =====
"""
Discovery + enrichment layer: turn a raw list of domains into a sector-tagged,
traffic-ranked, named universe — no paid data source.

The analysis only needs a domain. Everything a paid database would have handed
you, the pipeline derives from the store itself:

- niche      : classify_sector() reads the homepage text and buckets it.
- "top"      : Tranco (free global top-sites list) gives a popularity rank.
- brand name : extract_brand() reads og:site_name / <title>.
- country    : country_of() from the TLD, refined by on-page currency.

Input:  data/domains.txt  (one domain per line — from myip.ms, a public
        Shopify dump, or a BuiltWith export).
Output: data/brands.csv   (sector, brand, domain, country, rank) — the same
        format the scoring engine already consumes, now built automatically.

Network-touching (fetches each homepage + the Tranco list). Runs on CI or
locally, not in a locked-down sandbox.
"""

import io
import json
import re
import zipfile

import requests



# --- ICP rank window (Tranco popularity) --------------------------------------
# The mid-market sits below the top-5,000 giants and above the long tail of
# sub-scale niche stores. A domain must fall inside this window to be kept.
RANK_MIN = 5_000      # tighter than this = a giant (out of ICP)
RANK_MAX = 300_000    # looser than this = too small / low-traffic to benchmark

# --- marketplace + giant blocklist --------------------------------------------
# Never treat these (or their obvious subdomains) as a single-brand storefront:
# marketplaces, retailers of other brands, and platforms. Matched on the root.
BLOCKLIST = {
    "amazon", "ebay", "etsy", "walmart", "aliexpress", "alibaba", "wish",
    "target", "bestbuy", "argos", "very", "next", "asos", "zalando",
    "shein", "temu", "wayfair", "overstock", "costco", "ikea",
    "notonthehighstreet", "wolfandbadger", "faire",
    "shopify", "myshopify", "bigcommerce", "squarespace", "wix", "godaddy",
    "google", "facebook", "instagram", "tiktok", "youtube", "pinterest",
    "paypal", "stripe", "klarna", "afterpay", "clearpay",
    "ebay", "depop", "vinted", "poshmark", "mercari", "stockx", "goat",
}

# --- niche classification ------------------------------------------------------
# Keywords that show up on a store's own homepage. Conservative and weighted:
# the first few in each list are strong signals.
SECTOR_KEYWORDS = {
    "Beauty & skincare": ["skincare", "serum", "moisturiser", "moisturizer", "cleanser",
                          "spf", "makeup", "cosmetics", "foundation", "lipstick",
                          "fragrance", "beauty", "complexion"],
    "Fashion & apparel": ["clothing", "dress", "denim", "knitwear", "outerwear", "shirt",
                          "trousers", "fashion", "apparel", "wardrobe", "jumper", "coat"],
    "Activewear & athleisure": ["activewear", "leggings", "gym", "workout", "running",
                               "training", "sportswear", "athleisure", "performance wear"],
    "Footwear & accessories": ["shoes", "trainers", "sneakers", "boots", "footwear",
                              "jewellery", "jewelry", "watches", "earrings", "necklace",
                              "handbag", "sunglasses", "accessories"],
    "Health, supplements & wellness": ["supplement", "vitamin", "protein", "gut health",
                                      "nootropic", "wellness", "greens", "collagen",
                                      "capsules", "nutrition", "probiotic"],
    "Food & drink": ["snack", "coffee", "chocolate", "granola", "cereal", "nut butter",
                    "tea", "popcorn", "sauce", "pantry", "breakfast"],
    "Drinks & alcohol": ["gin", "whisky", "whiskey", "beer", "wine", "cocktail", "spirits",
                        "non-alcoholic", "kombucha", "soda", "seltzer", "brewery", "distillery"],
    "Home & living": ["sofa", "bedding", "mattress", "homeware", "furniture", "cushion",
                     "rug", "kitchenware", "cookware", "duvet", "bed linen", "decor"],
    "Personal care & grooming": ["deodorant", "shaving", "razor", "grooming", "shampoo",
                               "body wash", "oral care", "period", "tampon", "intimate",
                               "haircare"],
    "Pet": ["dog food", "cat food", "puppy", "kibble", "dog treats", "pet food", "for dogs",
           "for cats", "your dog", "your pet"],
    "Baby & kids": ["baby", "toddler", "nappy", "nappies", "kids", "children", "pram",
                   "nursery", "newborn", "little ones"],
}


def classify_sector(text: str):
    """Return (sector, score). score is weighted keyword hits; 0 => unclassified."""
    t = (text or "").lower()
    best, best_score = None, 0
    for sector, kws in SECTOR_KEYWORDS.items():
        score = 0
        for i, kw in enumerate(kws):
            if kw in t:
                score += 3 if i < 3 else 1  # first few keywords weigh more
        if score > best_score:
            best, best_score = sector, score
    if best_score < 2:
        return ("Unclassified", best_score)
    return (best, best_score)


# --- products.json: sharper niche + a catalogue-size band ----------------------
# Shopify exposes /products.json publicly. Product types and tags are a far
# cleaner niche signal than homepage marketing copy, and the product count is a
# rough size band (a proxy, not revenue). Used to confirm/override the homepage
# guess and to add confidence.
def fetch_products_json(base_url: str, limit: int = 250) -> list | None:
    """Return the products list from /products.json, or None if unavailable."""
    url = base_url.rstrip("/") + "/products.json?limit=%d" % limit
    try:
        r = _get(url)
        if r.status_code >= 400:
            return None
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    prods = data.get("products") if isinstance(data, dict) else None
    return prods if isinstance(prods, list) else None


def catalogue_band(n: int | None) -> str:
    """Coarse size band from published product count. A weak proxy for scale."""
    if not n:
        return "unknown"
    if n < 10:
        return "micro"        # often sub-scale or single-hero-product
    if n < 60:
        return "small"
    if n < 300:
        return "mid"
    return "large"            # deep catalogue (could be a retailer, verify)


def classify_from_products(products: list | None):
    """Return (sector, score, n_products). Reads product_type + tags + titles,
    which are a cleaner niche signal than homepage copy."""
    if not products:
        return ("Unclassified", 0, 0)
    parts = []
    for p in products[:250]:
        if not isinstance(p, dict):
            continue
        parts.append(str(p.get("product_type") or ""))
        parts.append(str(p.get("title") or ""))
        tags = p.get("tags")
        if isinstance(tags, list):
            parts.append(" ".join(str(t) for t in tags))
        elif tags:
            parts.append(str(tags))
    sector, score = classify_sector(" ".join(parts))
    return (sector, score, len(products))


def is_blocked(domain: str) -> bool:
    """True if the domain's root label is a known marketplace, retailer or
    platform we never want in a single-brand storefront benchmark."""
    root = _root(domain)
    label = root.split(".")[0]
    if label in BLOCKLIST:
        return True
    # also catch marketplace tokens anywhere in the root (e.g. amazon.co.uk)
    return any(("." + b + ".") in ("." + root + ".") for b in BLOCKLIST)


# --- brand name ----------------------------------------------------------------
_SUFFIXES = re.compile(
    r"\s*[|\-–—:·»].*$|"  # drop everything after a separator
    r"\s*(official (online )?store|home ?page|shop online|uk|us).*$",
    re.I,
)


def extract_brand(html: str, domain: str) -> str:
    html = html or ""
    m = re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        name = _SUFFIXES.sub("", title).strip()
        if 1 < len(name) <= 40:
            return name
    # fallback: from the domain
    core = re.sub(r"^www\.", "", domain).split(".")[0]
    return core.replace("-", " ").title()


# --- country -------------------------------------------------------------------
def country_of(domain: str, html: str = "") -> tuple[str, str]:
    """Return (country, confidence). ccTLDs are high-confidence; generic TLDs are
    inferred from hreflang, an explicit currency/country selector, shipping copy
    and raw currency symbols, in that order of trust."""
    d = domain.lower()
    if d.endswith(".co.uk") or d.endswith(".uk"):
        return ("UK", "high")
    if d.endswith(".com.au") or d.endswith(".au"):
        return ("AU", "high")
    if d.endswith(".ca"):
        return ("CA", "high")
    if d.endswith(".ie"):
        return ("IE", "high")
    t = (html or "")
    tl = t.lower()

    # 1) hreflang default / x-default region is a strong, deliberate signal.
    hreflangs = re.findall(r'hreflang=["\']([a-z]{2}(?:-[a-z]{2})?)["\']', tl)
    regions = [h.split("-")[1] for h in hreflangs if "-" in h]
    if regions:
        if regions.count("gb") > regions.count("us"):
            return ("UK", "high")
        if regions.count("us") > regions.count("gb"):
            return ("US", "high")

    # 2) explicit currency / country selector value.
    if re.search(r'(selected[^>]*>\s*(gbp|£|united kingdom)|value=["\'](gb|gbp|uk)["\'][^>]*selected)', tl):
        return ("UK", "high")
    if re.search(r'(selected[^>]*>\s*(usd|\$\s*usd|united states)|value=["\'](us|usd)["\'][^>]*selected)', tl):
        return ("US", "high")

    # 3) shipping / returns copy naming a country.
    uk_copy = len(re.findall(r'(free uk (delivery|shipping)|uk returns|delivered across the uk|royal mail)', tl))
    us_copy = len(re.findall(r'(free us (delivery|shipping)|us returns|ships? (from|within) the us|usps)', tl))
    if uk_copy > us_copy:
        return ("UK", "medium")
    if us_copy > uk_copy:
        return ("US", "medium")

    # 4) raw currency symbols — weakest signal.
    gbp = t.count("£") + tl.count("gbp")
    usd = t.count("$") + tl.count("usd")
    if gbp and gbp >= usd:
        return ("UK", "low")
    if usd:
        return ("US", "low")
    return ("US", "low")  # default for generic TLDs when no signal


# --- Tranco popularity rank (free) --------------------------------------------
TRANCO_URL = "https://tranco-list.eu/top-1m.csv.zip"


def load_tranco(url: str = TRANCO_URL) -> dict:
    """Return {domain: rank} from the Tranco top-1M list (free research list)."""
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    ranks = {}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = z.namelist()[0]
        for line in z.open(name).read().decode("utf-8", "ignore").splitlines():
            parts = line.split(",")
            if len(parts) == 2:
                ranks[parts[1].strip().lower()] = int(parts[0])
    return ranks


def _root(domain: str) -> str:
    return re.sub(r"^www\.", "", domain.strip().lower())


# STRONG signals that a page is a real online store (not a blog/news/SaaS that
# merely mentions "checkout" or has a "cart" link). Two groups: a known
# ecommerce platform footprint, or an explicit add-to-cart control. Weak generic
# words are deliberately excluded to keep precision high.
PLATFORM_MARKERS = (
    "woocommerce", "wp-content/plugins/woocommerce",       # WooCommerce
    "mage/cookies", "magento", "mage-messages",            # Magento
    "cdn11.bigcommerce.com", "bigcommerce.com/stencil",    # BigCommerce
    "demandware", "dwstatic", "demandware.static",         # Salesforce Commerce
    "wixstores", "ecom-components", "squarespace-commerce", # Wix / Squarespace stores
    "cdn.shopify.com", "/cdn/shop/", "shopify-section",    # Shopify (also caught upstream)
    "prestashop", "commercejs", "snipcart", "ecwid",       # others
)
ADD_TO_CART_MARKERS = (
    "add to cart", "add-to-cart", "addtocart", "add_to_cart",
    "data-add-to-cart", "add to bag", "add to basket", "product-form__cart",
)

# Publisher / media / non-ecom fingerprints. If a page looks like a news or
# content site, reject it even if it has a stray "basket" or "subscribe" word.
NEWS_MARKERS = (
    'og:type" content="article', "og:type' content='article",
    "newsarticle", '"@type":"newsarticle"', '"@type": "newsarticle"',
    "/opinion/", "/politics/", "breaking news", "subscribe to our newsletter for the latest",
    "wp-content/themes/newspaper", "td-post-content", "article__body",
    "read more articles", "latest headlines", "editorial team", "press releases",
)


def looks_like_news(html: str) -> bool:
    t = (html or "").lower()
    return any(m in t for m in NEWS_MARKERS)


def is_store(html: str, headers=None) -> bool:
    """True only if the page shows a real store footprint: a known ecommerce
    platform, or an explicit add-to-cart control, and it does NOT read as a
    news/content site. Precision over recall."""
    t = (html or "").lower()
    if looks_like_news(t):
        return False
    if any(m in t for m in PLATFORM_MARKERS):
        return True
    return any(m in t for m in ADD_TO_CART_MARKERS)


def enrich_domain(domain: str, tranco: dict | None = None,
                  rank_window: bool = True) -> dict | None:
    """Fetch a domain and keep it if it's a real online store on any platform.
    Shopify stores are kept as-is; other platforms are kept and flagged at
    scoring time (non-shopify:migrate). Blogs, news, SaaS and marketplaces are
    dropped. Low-confidence classifications are kept but flagged 'review'."""
    d = _root(domain)
    if is_blocked(d):
        return None  # marketplace / retailer / platform — never a single brand

    rank = (tranco or {}).get(d)
    if rank_window and rank is not None and not (RANK_MIN < rank <= RANK_MAX):
        return None  # outside the mid-market traffic window (giant or too small)

    final_url, resp, _ = resolve_base(domain)
    if not final_url or resp is None:
        return None
    platform, _ = detect_platform(resp)
    html = resp.text
    if not platform.startswith("shopify") and not is_store(html, resp.headers):
        return None  # not an online store at all — skip blogs / news / SaaS

    # niche: homepage copy first, then confirm/override with products.json.
    home_sector, home_score = classify_sector(html)
    n_products = 0
    band = "unknown"
    prod_sector, prod_score = "Unclassified", 0
    if platform.startswith("shopify"):
        products = fetch_products_json(final_url)
        prod_sector, prod_score, n_products = classify_from_products(products)
        band = catalogue_band(n_products)

    # prefer the products.json verdict when it's confident; else homepage.
    if prod_score >= 2 and prod_score >= home_score:
        sector, score, basis = prod_sector, prod_score, "products"
    else:
        sector, score, basis = home_sector, home_score, "homepage"

    country, country_conf = country_of(domain, html)

    # review bucket: keep, but flag anything we're not confident about so it can
    # be checked before it goes into an outreach list or the public report.
    review = []
    if sector == "Unclassified" or score < 3:
        review.append("niche")
    if country_conf == "low":
        review.append("country")
    if band in ("micro", "large"):
        review.append("size")  # micro may be sub-scale; large may be a retailer

    return {
        "sector": sector,
        "brand": extract_brand(html, domain),
        "domain": d,
        "country": country,
        "country_confidence": country_conf,
        "rank": rank if rank is not None else 10_000_000,  # unranked sorts last
        "sector_score": score,
        "sector_basis": basis,
        "n_products": n_products,
        "catalogue_band": band,
        "review": review,          # empty list == clean; else reasons to check
        "needs_review": bool(review),
    }


def candidates_from_tranco(tranco: dict, pool: int = RANK_MAX, tlds=None,
                           rank_min: int = RANK_MIN, rank_max: int = RANK_MAX) -> list[str]:
    """Use Tranco itself as the domain pool, restricted to the mid-market rank
    window (rank_min < rank <= rank_max) and, optionally, certain TLDs. Blocked
    marketplaces/platforms are dropped up front so we never fetch them."""
    cap = min(pool, rank_max)
    items = sorted(((d, r) for d, r in tranco.items() if rank_min < r <= cap),
                   key=lambda x: x[1])
    doms = [d for d, _ in items if not is_blocked(d)]
    if tlds:
        doms = [d for d in doms if any(d.endswith(t) for t in tlds)]
    return doms


def build_universe(domains: list[str] | None = None, top_n: int = 200,
                   use_tranco: bool = True, seed_pool: int = RANK_MAX, tlds=None,
                   keep_review: bool = True) -> list[dict]:
    """Classify + rank a domain pool into top_n per sector.

    If `domains` is None, self-seed from Tranco's mid-market rank window, so the
    only input is a PSI/CrUX key. The store detector keeps only real stores;
    unclassified-but-real stores land in a 'Review' bucket instead of vanishing.
    """
    tranco = load_tranco() if use_tranco else {}
    if domains is None:
        domains = candidates_from_tranco(tranco, pool=seed_pool, tlds=tlds)
        print("Seeded %d candidate domains from Tranco window %d-%d"
              % (len(domains), RANK_MIN, min(seed_pool, RANK_MAX)))
    enriched = []
    for dom in domains:
        try:
            row = enrich_domain(dom, tranco)
        except requests.RequestException:
            row = None
        if not row:
            continue
        if row["sector"] == "Unclassified":
            if keep_review:
                row["sector"] = "Review"      # surface, don't silently drop
                enriched.append(row)
            continue
        enriched.append(row)
    # top_n per sector by popularity (lower Tranco rank = more popular)
    by_sector: dict[str, list] = {}
    for r in enriched:
        by_sector.setdefault(r["sector"], []).append(r)
    out = []
    for sector, group in by_sector.items():
        group.sort(key=lambda r: r["rank"])
        out.extend(group[:top_n])
    return out


# ===== self-seeding runner =====
import time, datetime as dt, statistics, argparse, threading
import requests as _rq
from concurrent.futures import ThreadPoolExecutor

# A Shopify-standard store is only a genuine Plus upgrade prospect if it is big
# enough to warrant Plus. Use traffic rank as the size gate: stores outside the
# top UPGRADE_RANK_MAX by Tranco are too small, so we drop the upgrade flag.
UPGRADE_RANK_MAX = 60000

def build_store(brand, sector, domain, country, rank, api_key, pause=0.4, extra=None):
    store = resolve_store(brand, sector, domain)
    store["country"] = country
    store["rank"] = rank
    for k, v in (extra or {}).items():
        store[k] = v
    if not store.get("reachable"):
        store["score"]=None; store["dimensions"]={}; return store
    home_html = store.pop("_home_html", None)
    page_html={"home":home_html}
    for ptype in ("home","collection","pdp"):
        page=store["pages"].get(ptype) or {}
        url=page.get("url")
        if not url: continue
        try:
            page["speed"]=measure(url,"mobile",api_key,pause=pause); time.sleep(pause)
        except Exception as e:
            store["errors"].append("psi %s: %s"%(ptype,e))
        if ptype=="pdp":
            try:
                rr=_rq.get(url,headers=HEADERS,timeout=TIMEOUT)
                page_html["pdp"]=rr.text if rr.status_code<400 else None
            except Exception: page_html["pdp"]=None
        store["pages"][ptype]=page
    store["signals"]=merge_signals(fingerprint(page_html.get("home") or ""),
                                   fingerprint(page_html.get("pdp") or ""))
    score_store(store)
    return store

def qualify_flags(store, max_rank):
    """Tighten the Plus-upgrade recommendation using store size (traffic rank)."""
    flags=store.get("flags",[])
    if "non-plus:upgrade" in flags:
        rank=store.get("rank") or 10**9
        if rank > max_rank:
            flags.remove("non-plus:upgrade")  # too small to be a real Plus prospect
    return store

def main():
    try: sys.stdout.reconfigure(line_buffering=True)  # live progress in CI logs
    except Exception: pass
    ap=argparse.ArgumentParser()
    ap.add_argument("--pool", type=int, default=20000)  # Tranco rank ceiling; window is 5,000..min(pool,300,000)
    ap.add_argument("--per-niche", type=int, default=200)
    ap.add_argument("--countries", default="UK,US")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--upgrade-rank-max", type=int, default=UPGRADE_RANK_MAX)
    ap.add_argument("--out", default="dashboard.html")
    a=ap.parse_args()
    max_rank=a.upgrade_rank_max
    key=os.environ.get("PSI_API_KEY")
    if not key: print("Set PSI_API_KEY first."); sys.exit(1)
    keep=set(c.strip().upper() for c in a.countries.split(","))

    print("Loading Tranco list...")
    tranco=load_tranco()
    cands=candidates_from_tranco(tranco, pool=a.pool)
    print("Discovery: scanning %d candidates for %s online stores (any platform)...\n"%(len(cands),"/".join(keep)))
    found=[]; review=[]; lock=threading.Lock(); seen=[0]
    def disc(dom):
        try: r=enrich_domain(dom, tranco)
        except Exception: r=None
        with lock:
            seen[0]+=1
            if seen[0]%500==0: print("  scanned %d/%d, kept %d"%(seen[0],len(cands),len(found)))
        if r and r["country"] in keep:
            if r["sector"]=="Unclassified":
                with lock: review.append(r)   # keep for a side file, NOT the dashboard
            else:
                with lock: found.append(r)
        return None
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(disc, cands))
    by_sector={}
    for r in found: by_sector.setdefault(r["sector"],[]).append(r)
    universe=[]
    for sec,g in by_sector.items():
        g.sort(key=lambda r:r["rank"]); universe.extend(g[:a.per_niche])
    print("\nDiscovered %d stores across %d niches. Scoring...\n"%(len(universe),len(by_sector)))

    stores=[]; done=[0]
    def work(r):
        extra={"catalogue_band":r.get("catalogue_band"),"n_products":r.get("n_products"),
               "country_confidence":r.get("country_confidence"),"sector_basis":r.get("sector_basis"),
               "needs_review":r.get("needs_review"),"review":r.get("review",[])}
        try: s=build_store(r["brand"],r["sector"],r["domain"],r["country"],r["rank"],key,extra=extra)
        except Exception as e: s=None; print("  score fail %s: %s"%(r["domain"],e))
        with lock:
            done[0]+=1
            if done[0]%25==0: print("  scored %d/%d"%(done[0],len(universe)))
        return s
    with ThreadPoolExecutor(max_workers=min(8, max(4, a.workers//4))) as ex:  # cap: respect PSI rate limit
        for s in ex.map(work, universe):
            if s: stores.append(qualify_flags(s, max_rank))
    rank_all(stores, None)
    scored=[s for s in stores if s.get("score") is not None]
    meta={"quarter":"Q%d %d"%((dt.date.today().month-1)//3+1, dt.date.today().year),
          "generated":dt.date.today().isoformat(),"n_scored":len(scored),
          "n_sectors":len(set(s["sector"] for s in scored)),
          "n_migrate":sum('non-shopify:migrate' in s.get('flags',[]) for s in scored),
          "n_upgrade":sum('non-plus:upgrade' in s.get('flags',[]) for s in scored),
          "median":round(statistics.median([s["score"] for s in scored]),1) if scored else 0}
    open(a.out,"w",encoding="utf-8").write(render_dashboard(stores, meta))
    with open("ranking.csv","w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["rank","brand","sector","country","country_conf","traffic_rank","catalogue_band","n_products","sector_rank","sector_size","score","speed","friction","trust","upsell","value","ux","platform","flags","needs_review","review_reasons","domain"])
        for s in sorted(scored,key=lambda s:s["benchmark_rank"]):
            dd=s["dimensions"]; w.writerow([s["benchmark_rank"],s["brand"],s["sector"],s.get("country",""),s.get("country_confidence",""),s.get("rank",""),s.get("catalogue_band",""),s.get("n_products",""),s.get("sector_rank"),s.get("sector_size"),s["score"],dd.get("speed"),dd.get("friction"),dd.get("trust"),dd.get("upsell"),dd.get("value"),dd.get("ux"),s["platform"],"|".join(s.get("flags",[])),"yes" if s.get("needs_review") else "no","|".join(s.get("review",[]) or []),s["domain"]])
    # lead lists: migrate (non-Shopify) and upgrade (Plus-ready), clean rows only
    for tag, flag in (("leads_migrate","non-shopify:migrate"),("leads_upgrade_plus","non-plus:upgrade")):
        rowsf=[s for s in scored if flag in s.get("flags",[]) and not s.get("needs_review")]
        rowsf.sort(key=lambda s:s.get("rank") or 10**9)
        with open(tag+".csv","w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["brand","domain","sector","country","traffic_rank","catalogue_band","score","platform"])
            for s in rowsf: w.writerow([s["brand"],s["domain"],s["sector"],s.get("country",""),s.get("rank",""),s.get("catalogue_band",""),s["score"],s["platform"]])
        print("  wrote %s.csv (%d rows)"%(tag,len(rowsf)))
    # side file: real stores we could not confidently classify (kept OUT of the dashboard)
    if review:
        review.sort(key=lambda r: r.get("rank") or 10**9)
        with open("review_unclassified.csv","w",newline="",encoding="utf-8") as f:
            w=csv.writer(f); w.writerow(["brand","domain","country","traffic_rank","catalogue_band","n_products"])
            for r in review: w.writerow([r.get("brand",""),r.get("domain",""),r.get("country",""),r.get("rank",""),r.get("catalogue_band",""),r.get("n_products","")])
        print("  wrote review_unclassified.csv (%d rows, not shown on dashboard)"%len(review))
    plat={}
    for s in scored: plat[s["platform"]]=plat.get(s["platform"],0)+1
    print("  platform split: "+", ".join("%s=%d"%(k,v) for k,v in sorted(plat.items())))
    print("\nDone. %d scored, %d migrate, %d Plus-ready. Wrote %s + ranking.csv + lead lists"%(len(scored),meta["n_migrate"],meta["n_upgrade"],a.out))

if __name__=="__main__":
    main()
