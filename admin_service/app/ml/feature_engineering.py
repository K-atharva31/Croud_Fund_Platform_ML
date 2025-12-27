# admin_service/app/ml/feature_engineering.py
from datetime import datetime, timezone
import math
import re

ISO_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"

def _safe_dt_from_iso(s):
    if not s:
        return None
    try:
        # Accept naive or Zulu timestamps
        if s.endswith("Z"):
            return datetime.strptime(s, ISO_FMT).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

def compute_rule_hits(campaign: dict, user: dict) -> list:
    """
    Returns list of rule hit dicts: {rule, severity, value (optional), reason}
    severity = 'critical'|'warning'|'info'
    """
    hits = []
    # Rapid multiple campaigns by same user (needs user.created_campaigns_last_24h in user doc)
    try:
        if user:
            cnt_24h = int(user.get("created_campaigns_last_24h", 0))
            if cnt_24h > 3:
                hits.append({"rule":"rapid_multiple_campaigns", "severity":"warning", "value":cnt_24h,
                             "reason": "user created {} campaigns in last 24h".format(cnt_24h)})
    except Exception:
        pass

    # New account large goal
    try:
        created_at = _safe_dt_from_iso(user.get("created_at")) if user else None
        acct_age_days = (datetime.now(timezone.utc) - created_at).days if created_at else None
        goal = float(campaign.get("goal", 0) or 0)
        if acct_age_days is not None and acct_age_days < 7 and goal > 100000:
            hits.append({"rule":"new_account_large_goal", "severity":"critical", "value": {"acct_age_days":acct_age_days,"goal":goal},
                         "reason":"very new account with large goal"})
    except Exception:
        pass

    # High refund rate (requires campaign.refunds_count and campaign.donations_count)
    try:
        refunds = int(campaign.get("refunds_count", 0) or 0)
        donations = int(campaign.get("donations_count", 0) or 0)
        if donations >= 5 and refunds / max(1, donations) > 0.25 and refunds > 3:
            hits.append({"rule":"high_refund_rate", "severity":"critical", "value": {"refunds":refunds,"donations":donations},
                         "reason":"refund rate >25%"})
    except Exception:
        pass

    # Duplicate content heuristic (very basic)
    try:
        description = (campaign.get("description") or "").strip().lower()
        title = (campaign.get("title") or "").strip().lower()
        # look for common scam phrases
        suspicious_phrases = ["urgent", "transfer to", "lottery", "wire", "claim your", "act now", "guarantee", "winner"]
        for p in suspicious_phrases:
            if p in description or p in title:
                hits.append({"rule":"suspicious_text_phrase", "severity":"warning", "value":p,
                             "reason":"found suspicious phrase"})
                break
    except Exception:
        pass

    # Payout country mismatch
    try:
        payout_country = campaign.get("payout_country")
        user_country = user.get("country") if user else None
        if payout_country and user_country and payout_country != user_country:
            hits.append({"rule":"payout_country_mismatch", "severity":"warning",
                         "value":{"payout_country":payout_country,"user_country":user_country},
                         "reason":"payout country differs from user country"})
    except Exception:
        pass

    # Suspicious email domain (disposable)
    try:
        email = (user.get("email") or "")
        if email:
            domain = email.split("@")[-1].lower()
            disposable_domains = {"mailinator.com","10minutemail.com","tempmail.com","guerrillamail.com"}
            if domain in disposable_domains:
                hits.append({"rule":"disposable_email", "severity":"warning", "value":domain,
                             "reason":"user email domain is disposable"})
    except Exception:
        pass

    return hits

def compute_features_for_campaign(campaign: dict, user: dict) -> dict:
    """
    Produce a deterministic set of numeric features used by models.
    Keys must be stable and numeric.
    """
    f = {}
    # basic numeric fields
    goal = float(campaign.get("goal", 0) or 0)
    amount = float(campaign.get("amount_raised", 0) or 0)
    f["goal"] = goal
    f["amount_raised"] = amount

    # days active
    created = _safe_dt_from_iso(campaign.get("created_at"))
    if created:
        days_active = max(1.0, (datetime.now(timezone.utc) - created).total_seconds() / (3600*24))
    else:
        days_active = 1.0
    f["days_active"] = days_active

    # velocity
    f["velocity"] = amount / days_active

    # percent funded
    f["percent_funded"] = amount / max(1.0, goal)

    # counts
    f["updates_count"] = float(campaign.get("updates_count", 0) or 0)
    f["images_count"] = float(len(campaign.get("images", []) or []))
    f["videos_count"] = 1.0 if campaign.get("video_url") else 0.0

    # refunds / donations
    f["donations_count"] = float(campaign.get("donations_count", 0) or 0)
    f["refunds_count"] = float(campaign.get("refunds_count", 0) or 0)
    f["refund_ratio"] = (f["refunds_count"] / max(1.0, f["donations_count"])) if f["donations_count"] >= 1.0 else 0.0

    # user properties
    try:
        acct_created = _safe_dt_from_iso(user.get("created_at")) if user else None
        acct_age_days = (datetime.now(timezone.utc) - acct_created).days if acct_created else 9999
    except Exception:
        acct_age_days = 9999
    f["user_account_age_days"] = float(acct_age_days)

    f["user_total_campaigns"] = float(user.get("total_campaigns", 0) or 0)
    f["user_num_cards"] = float(user.get("payment_sources_count", 0) or 0)

    # fill NaN / inf
    for k,v in list(f.items()):
        try:
            if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                f[k] = 0.0
            else:
                f[k] = float(v)
        except Exception:
            f[k] = 0.0

    return f
