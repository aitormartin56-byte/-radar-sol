#!/usr/bin/env python3
"""
Radar SOL v2.1 — radar multi-fuente + publica data.json para la interfaz.

Vigila a la vez:
  • Superteam Earn: bounties + projects + hackathons (lo que de verdad paga)
  • Superteam Earn: grants (financiación abierta)
  • Noticias de airdrops de Solana (varios feeds RSS)

Hace dos cosas cada ciclo:
  1) Avisa por Telegram de lo NUEVO que encaja contigo.
  2) Escribe data.json con el snapshot actual de oportunidades, para que el panel
     web (dashboard) lo lea en directo desde raw.githubusercontent.com.

Filosofía: DETECTAR Y AVISAR. No reclama airdrops ni farmea solo (eso te banea por
anti-Sybil y casi todo "auto-claim SOL" es un drainer). El trabajo que paga lo
haces tú; el radar te dice dónde y cuándo.
"""

import os
import sys
import json
import html
import datetime
import requests
import xml.etree.ElementTree as ET

STATE_FILE = "seen.json"
CONFIG_FILE = "config.json"
DATA_FILE = "data.json"
MAX_SEEN_PER_SOURCE = 3000
MAX_PER_RUN = 12
MAX_NEWS_PER_FEED = 40
SNAP_BOUNTIES = 50
SNAP_GRANTS = 50
SNAP_NEWS = 25
UA = {"User-Agent": "RadarSOL/2.1 (+personal opportunity notifier)"}

LIVE = "https://earn.superteam.fun/api/listings/live"
GRANTS = "https://earn.superteam.fun/api/grants/"
LISTING_URL = "https://superteam.fun/earn/listing/{slug}"
GRANT_URL = "https://superteam.fun/earn/grants/{slug}"


# ---------------- io ----------------
def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": False},
        timeout=30,
    )
    r.raise_for_status()


# ------------- helpers -------------
def reward_value(it):
    ct = it.get("compensationType")
    if ct == "fixed":
        return it.get("rewardAmount")
    if ct == "range":
        return it.get("maxRewardAsk")
    return None


def reward_text(it):
    ct = it.get("compensationType")
    tok = it.get("token") or ""
    if ct == "fixed":
        amt = it.get("rewardAmount")
        return f"{amt:g} {tok}" if amt is not None else f"? {tok}"
    if ct == "range":
        return f"{it.get('minRewardAsk')}–{it.get('maxRewardAsk')} {tok}"
    return "variable"


def time_left(deadline):
    try:
        dl = datetime.datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        secs = (dl - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        if secs < 0:
            return "cerrado"
        d = int(secs // 86400)
        if d >= 1:
            return f"cierra en {d} día" + ("s" if d != 1 else "")
        h = int(secs // 3600)
        return f"cierra en {h}h" if h >= 1 else "cierra en <1h"
    except Exception:
        return ""


def competition_tag(it):
    subs = (it.get("_count") or {}).get("Submission", 0) or 0
    if subs <= 5:
        return f"🟢 {subs} entregas · poca competencia"
    if subs <= 20:
        return f"🟡 {subs} entregas · competencia media"
    return f"🔴 {subs} entregas · alta competencia"


def match_reward_kw(title, sponsor, reward_val, scfg):
    title = (title or "").lower()
    sponsor = (sponsor or "").lower()
    kws = [k.lower() for k in scfg.get("keywords", [])]
    if kws and not any(k in title or k in sponsor for k in kws):
        return False
    minr = scfg.get("min_reward", 0) or 0
    if minr and reward_val is not None and reward_val < minr:
        return False
    return True


# ------------- mensajes Telegram -------------
def fmt_listing(it):
    title = html.escape(it.get("title", "(sin título)"))
    sponsor = html.escape((it.get("sponsor") or {}).get("name", "?"))
    star = "⭐ " if it.get("isFeatured") else ""
    return (
        f"{star}💰 <b>{reward_text(it)}</b> · {it.get('type','')}\n"
        f"<b>{title}</b>\n"
        f"🏷 {sponsor} · {time_left(it.get('deadline',''))}\n"
        f"{competition_tag(it)}\n"
        f"{LISTING_URL.format(slug=it.get('slug',''))}"
    )


def fmt_grant(g):
    title = html.escape(g.get("title", "(grant)"))
    sponsor = html.escape((g.get("sponsor") or {}).get("name", "?"))
    lo, hi, tok = g.get("minReward"), g.get("maxReward"), g.get("token") or ""
    if lo is not None and hi is not None:
        rew = f"{lo:g} {tok}" if lo == hi else f"{lo:g}–{hi:g} {tok}"
    else:
        rew = f"hasta {hi or lo} {tok}"
    return (
        f"🎁 <b>{rew}</b> · grant\n<b>{title}</b>\n"
        f"🏷 {sponsor} · solicitudes abiertas\n"
        f"{GRANT_URL.format(slug=g.get('slug',''))}"
    )


def fmt_news(title, link):
    return f"📰 <b>Airdrop/Solana</b>\n<b>{html.escape(title)}</b>\n{link}"


# ------------- tarjetas para data.json (interfaz) -------------
def card_listing(it):
    return {
        "kind": "bounty", "title": it.get("title", ""), "reward": reward_text(it),
        "type": it.get("type", ""), "sponsor": (it.get("sponsor") or {}).get("name", ""),
        "deadline": it.get("deadline", ""), "time_left": time_left(it.get("deadline", "")),
        "submissions": (it.get("_count") or {}).get("Submission", 0) or 0,
        "url": LISTING_URL.format(slug=it.get("slug", "")), "featured": bool(it.get("isFeatured")),
    }


def card_grant(g):
    lo, hi, tok = g.get("minReward"), g.get("maxReward"), g.get("token") or ""
    if lo is not None and hi is not None:
        rew = f"{lo:g} {tok}" if lo == hi else f"{lo:g}–{hi:g} {tok}"
    else:
        rew = f"hasta {hi or lo} {tok}"
    return {"kind": "grant", "title": g.get("title", ""), "reward": rew,
            "sponsor": (g.get("sponsor") or {}).get("name", ""),
            "applications": g.get("historicalApplications") or 0,
            "url": GRANT_URL.format(slug=g.get("slug", ""))}


def card_news(title, link):
    return {"kind": "news", "title": title, "url": link}


# ------------- FUENTES -------------
def src_superteam(scfg):
    types = scfg.get("types", ["bounty", "project", "hackathon"])
    take = scfg.get("take", 50)
    by_id = {}
    for t in types:
        try:
            r = requests.get(LIVE, params={"type": t, "take": take, "deadline": now_iso()},
                             headers=UA, timeout=30)
            r.raise_for_status()
            for it in (r.json() or []):
                if it.get("id"):
                    by_id[it["id"]] = it
        except Exception as e:
            print(f"  ⚠️ superteam[{t}]: {e}")
    items = []
    for it in by_id.values():
        matched = match_reward_kw(it.get("title"), (it.get("sponsor") or {}).get("name"),
                                  reward_value(it), scfg)
        items.append({"key": f"st:{it['id']}", "matched": matched,
                      "text": fmt_listing(it), "card": card_listing(it),
                      "deadline": it.get("deadline", "")})
    return items


def src_grants(scfg):
    try:
        r = requests.get(GRANTS, headers=UA, timeout=30)
        r.raise_for_status()
        data = r.json() or []
    except Exception as e:
        print("  ⚠️ grants:", e)
        return []
    items = []
    for g in data:
        slug = g.get("slug")
        if not slug:
            continue
        rv = g.get("maxReward") if g.get("maxReward") is not None else g.get("minReward")
        matched = match_reward_kw(g.get("title"), (g.get("sponsor") or {}).get("name"), rv, scfg)
        items.append({"key": f"grant:{slug}", "matched": matched,
                      "text": fmt_grant(g), "card": card_grant(g)})
    return items


EARN_WORDS = ["airdrop", "snapshot", "tge", "token launch", "points program", "points campaign",
              "incentive", "retroactive", "distribution", "eligib", "free token", "claim your",
              "rewards program", "farming"]
SOL_WORDS = ["solana", "$sol", " sol ", "jupiter", "jito", "kamino", "marginfi", "drift protocol",
             "meteora", "phantom wallet", "backpack", "magic eden", "pyth network", "tensor",
             "sanctum", "jupuary", "solana mobile"]


def news_match(title, extra_kw):
    t = " " + (title or "").lower() + " "
    if extra_kw and any(k.lower() in t for k in extra_kw):
        return True
    return any(e in t for e in EARN_WORDS) and any(s in t for s in SOL_WORDS)


def src_news(scfg):
    feeds = scfg.get("feeds", [])
    extra = scfg.get("keywords", [])
    items = []
    for url in feeds:
        try:
            r = requests.get(url, headers=UA, timeout=25)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            count = 0
            for it in root.iter("item"):
                if count >= MAX_NEWS_PER_FEED:
                    break
                count += 1
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                if not link:
                    continue
                items.append({"key": f"news:{link}", "matched": news_match(title, extra),
                              "text": fmt_news(title, link), "card": card_news(title, link)})
        except Exception as e:
            print(f"  ⚠️ news[{url}]: {e}")
    return items


SOURCES = {"superteam": src_superteam, "grants": src_grants, "news": src_news}
SOURCE_NAMES = {"superteam": "Superteam (bounties/projects/hackathons)",
                "grants": "Superteam Grants", "news": "Noticias de airdrops"}


# ------------- motor -------------
def run_source(name, scfg, state, token, chat_id, dry):
    order = list(state["seen"].get(name, []))
    seen = set(order)
    try:
        items = SOURCES[name](scfg)
    except Exception as e:
        print(f"  ❌ fuente {name} falló entera: {e}")
        return {"seeded": False, "total": 0, "matched": 0, "sent": 0, "cards": []}

    matched_cards = [i["card"] for i in items if i["matched"]]
    matched_n = len(matched_cards)

    if not state["init"].get(name, False):
        for i in items:
            if i["key"] not in seen:
                seen.add(i["key"]); order.append(i["key"])
        state["seen"][name] = order[-MAX_SEEN_PER_SOURCE:]
        state["init"][name] = True
        print(f"  🌱 {name}: sembrado ({len(items)} vistos, {matched_n} encajan).")
        return {"seeded": True, "total": len(items), "matched": matched_n, "sent": 0,
                "cards": matched_cards}

    sent = 0
    for i in items:
        if i["key"] in seen:
            continue
        if i["matched"]:
            ok = True
            try:
                if dry:
                    print(f"\n--- AVISO [{name}] ---\n{i['text']}")
                else:
                    send_telegram(token, chat_id, i["text"])
            except Exception as e:
                ok = False
                print(f"  ⚠️ envío falló (reintenta luego): {e}")
            if ok:
                seen.add(i["key"]); order.append(i["key"]); sent += 1
        else:
            seen.add(i["key"]); order.append(i["key"])
        if sent >= MAX_PER_RUN:
            print(f"  ⏸ {name}: tope de {MAX_PER_RUN} avisos/ciclo; el resto en el próximo.")
            break

    state["seen"][name] = order[-MAX_SEEN_PER_SOURCE:]
    print(f"  ✅ {name}: {len(items)} vistos, {sent} avisos nuevos.")
    return {"seeded": False, "total": len(items), "matched": matched_n, "sent": sent,
            "cards": matched_cards}


def write_snapshot(by_source):
    bounties = by_source.get("superteam", [])
    bounties = sorted(bounties, key=lambda c: c.get("deadline") or "9999")[:SNAP_BOUNTIES]
    grants = by_source.get("grants", [])[:SNAP_GRANTS]
    news = by_source.get("news", [])[:SNAP_NEWS]
    snapshot = {
        "updated_at": now_iso(),
        "counts": {"bounties": len(bounties), "grants": len(grants), "news": len(news)},
        "bounties": bounties,
        "grants": grants,
        "news": news,
    }
    save_json(DATA_FILE, snapshot)
    print(f"🗂  data.json escrito ({len(bounties)} bounties, {len(grants)} grants, {len(news)} noticias).")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    dry = not (token and chat_id)
    if dry:
        print("⚠️  Sin TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID -> modo prueba (imprime por pantalla).")

    cfg = load_json(CONFIG_FILE, {})
    sources_cfg = cfg.get("sources", {})
    state = load_json(STATE_FILE, {"seen": {}, "init": {}})
    state.setdefault("seen", {})
    state.setdefault("init", {})

    seeded = []
    by_source = {}
    print("📡 Radar SOL v2.1 — pasando por las fuentes…")
    for name in ["superteam", "grants", "news"]:
        scfg = sources_cfg.get(name, {})
        if not scfg.get("enabled", False):
            print(f"  ⤫ {name}: desactivada en config.")
            by_source[name] = []
            continue
        res = run_source(name, scfg, state, token, chat_id, dry)
        by_source[name] = res["cards"]
        if res["seeded"]:
            seeded.append((name, res["total"], res["matched"]))

    if seeded:
        lines = ["🐀📡 <b>Radar SOL activado</b>", "Vigilando estas fuentes:"]
        for name, total, matched in seeded:
            lines.append(f"• {SOURCE_NAMES.get(name, name)}: {total} activos, {matched} encajan")
        lines.append("Te avisaré aquí en cuanto salga algo NUEVO.")
        msg = "\n".join(lines)
        if dry:
            print("\n=== MENSAJE DE ACTIVACIÓN ===\n" + msg)
        else:
            try:
                send_telegram(token, chat_id, msg)
            except Exception as e:
                print("  ⚠️ no se pudo enviar el resumen de activación:", e)

    # Snapshot para la interfaz (siempre, sembrando o no).
    write_snapshot(by_source)

    save_json(STATE_FILE, state)
    print("💾 Estado guardado.")


if __name__ == "__main__":
    main()
