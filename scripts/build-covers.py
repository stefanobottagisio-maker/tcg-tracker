
#!/usr/bin/env python3
"""
Genera covers-op.json e covers-lor.json leggendo le box art ufficiali da TCGCSV
(mirror pubblico dei dati TCGplayer). Eseguito da GitHub Actions: gira lato server,
quindi NON incontra il muro CORS che blocca il browser.

Output (nella cartella del repo):
  covers-op.json   ->  { "OP01": "https://.../..._in_1000x1000.jpg", ... }
  covers-lor.json  ->  { "1": "https://...", "2": "https://...", ... }

La pagina legge questi file dalla propria origine (nessun CORS) e usa TCGCSV
solo come ripiego. Se TCGCSV cambia struttura, lo script fallisce in modo
evidente nei log dell'Action senza rompere la pagina (che continua coi JSON esistenti).
"""

import json
import re
import sys
import time
import urllib.request

BASE = "https://tcgcsv.com/tcgplayer"
# Uno User-Agent da browser evita il 403 che alcuni edge di TCGCSV restituiscono
# a client "automatici". Confermati il 2026-07: One Piece = 68, Lorcana = 71.
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
KNOWN_CATEGORIES = {"one piece": 68, "lorcana": 71}

# Espansioni One Piece che vogliamo mappare (stesso elenco della pagina).
OP_SETS = [
    ("OP01", "Romance Dawn"), ("OP02", "Paramount War"), ("OP03", "Pillars of Strength"),
    ("OP04", "Kingdoms of Intrigue"), ("OP05", "Awakening of the New Era"),
    ("OP06", "Wings of the Captain"), ("OP07", "500 Years into the Future"),
    ("OP08", "Two Legends"), ("OP09", "Emperors in the New World"), ("OP10", "Royal Blood"),
    ("OP11", "A Fist of Divine Speed"), ("OP12", "Legacy of the Master"),
    ("OP13", "Carrying On His Will"), ("OP14", "The Azure Sea's Seven"),
    ("OP15", "Adventure on Kami's Island"), ("OP16", "The Time of Battle"),
    ("EB01", "Memorial Collection"), ("EB02", "Anime 25th Collection"),
    ("EB03", "Heroines Edition"), ("EB04", "Egghead Crisis"),
    ("PRB01", "The Best Vol.1"), ("PRB02", "The Best Vol.2"),
]


def get_json(url, tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def find_category(needle):
    needle = needle.lower()
    # Scorciatoia sui categoryId noti (evita una chiamata e regge cambi di ordine).
    if needle in KNOWN_CATEGORIES:
        return KNOWN_CATEGORIES[needle]
    cats = get_json(f"{BASE}/categories").get("results", [])
    for c in cats:
        blob = f"{c.get('name','')} {c.get('displayName','')}".lower()
        if needle in blob:
            return c["categoryId"]
    raise SystemExit(f"Categoria non trovata: {needle}")


def best_cover(products):
    """Sceglie l'immagine migliore: prima un Booster Box, poi un booster, poi qualsiasi."""
    for pattern in (r"booster box", r"booster", r".*"):
        for p in products:
            if re.search(pattern, p.get("name", ""), re.I) and p.get("imageUrl"):
                return p["imageUrl"].replace("_200w", "_in_1000x1000")
    return ""


def build_op(cat_id):
    groups = get_json(f"{BASE}/{cat_id}/groups").get("results", [])
    out = {}
    for code, name in OP_SETS:
        g = None
        for grp in groups:
            abbr = (grp.get("abbreviation") or "").upper().replace("-", "")
            if abbr == code or name.lower() in (grp.get("name") or "").lower():
                g = grp
                break
        if not g:
            print(f"  [OP] nessun gruppo per {code} ({name})")
            continue
        prods = get_json(f"{BASE}/{cat_id}/{g['groupId']}/products").get("results", [])
        url = best_cover(prods)
        if url:
            out[code] = url
            print(f"  [OP] {code} -> ok")
        time.sleep(0.3)
    return out


def build_lor(cat_id):
    groups = get_json(f"{BASE}/{cat_id}/groups").get("results", [])
    out = {}
    # I set Lorcana su TCGplayer hanno nomi tipo "The First Chapter": mappiamo per
    # posizione cronologica (codice numerico Lorcast) usando l'ordine dei gruppi.
    # Prendiamo la box art di ogni gruppo che sembra un set principale.
    lor_groups = [g for g in groups if g.get("name")]
    # Ordina per data se presente, altrimenti lascia l'ordine dato.
    lor_groups.sort(key=lambda g: g.get("publishedOn") or "")
    idx = 1
    for g in lor_groups:
        nm = g.get("name", "")
        # Salta prodotti accessori (gift set, puzzle, ecc.) tenendo i set principali.
        if re.search(r"gift|puzzle|playmat|sleeve|deck box|accessor", nm, re.I):
            continue
        prods = get_json(f"{BASE}/{cat_id}/{g['groupId']}/products").get("results", [])
        url = best_cover(prods)
        if url:
            out[str(idx)] = url
            print(f"  [LOR] set {idx} ({nm}) -> ok")
            idx += 1
        time.sleep(0.3)
    return out


def main():
    print("Categoria One Piece...")
    op_cat = find_category("one piece")
    op = build_op(op_cat)
    with open("covers-op.json", "w", encoding="utf-8") as f:
        json.dump(op, f, ensure_ascii=False, indent=1)
    print(f"covers-op.json: {len(op)} copertine")

    print("Categoria Lorcana...")
    lor_cat = find_category("lorcana")
    lor = build_lor(lor_cat)
    with open("covers-lor.json", "w", encoding="utf-8") as f:
        json.dump(lor, f, ensure_ascii=False, indent=1)
    print(f"covers-lor.json: {len(lor)} copertine")

    if not op and not lor:
        sys.exit("Nessuna copertina generata: probabile cambiamento in TCGCSV.")


if __name__ == "__main__":
    main()
