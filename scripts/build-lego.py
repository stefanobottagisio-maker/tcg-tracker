#!/usr/bin/env python3
"""
Genera il catalogo LEGO leggendo da Rebrickable (community database di tutti i set
LEGO mai usciti). Eseguito da GitHub Actions: gira lato server, quindi NON incontra
il muro CORS che blocca le chiamate dirette dal browser (confermato sul forum
Rebrickable: "Blocked by CORS policy").

Richiede la variabile d'ambiente REBRICKABLE_API_KEY (gratuita, vedi GUIDA-INSTALLAZIONE.md).

Le "categorie" corrispondono ai temi LEGO di primo livello (Star Wars, Technic,
City, Harry Potter...). Ogni set viene assegnato al suo tema di primo livello
risalendo la gerarchia parent_id, cosi' anche i sotto-temi (es. "Star Wars >
Ultimate Collector Series") confluiscono nella categoria principale.

Output (nella cartella del repo):
  lego-categories.json          -> [ {id, n, count, img}, ... ]
  lego-sets/<categoryId>.json   -> [ {n:set_num, t:nome, y:anno, p:pezzi, img}, ... ]
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

API_KEY = os.environ.get("REBRICKABLE_API_KEY", "").strip()
BASE = "https://rebrickable.com/api/v3/lego"
HEADERS = {"Authorization": "key " + API_KEY, "User-Agent": "collezionista-matto/1.0"}

# Filtro qualita': scarta temi troppo piccoli (bomboniere, ricambi, ecc.) e le
# linee non da collezione che intaserebbero le categorie senza valore per un collezionista.
MIN_SETS_PER_CATEGORY = 15
EXCLUDE_NAME_SUBSTRINGS = ("duplo", "education", "bulk", "supplemental", "gear", "book")


def get_json(url, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def fetch_all_pages(path, page_size=1000):
    """Segue i link 'next' della paginazione Rebrickable e concatena i risultati."""
    out = []
    url = f"{BASE}/{path}/?page_size={page_size}"
    page_n = 0
    while url:
        j = get_json(url)
        out.extend(j.get("results", []))
        url = j.get("next")
        page_n += 1
        print(f"  pagina {page_n}: {len(out)} elementi totali finora")
        time.sleep(0.25)  # gentile con il rate limit
    return out


def build_theme_maps(themes):
    """Ritorna: id->nome, id->parent_id, e una funzione per trovare l'antenato di primo livello."""
    name_of = {t["id"]: t["name"] for t in themes}
    parent_of = {t["id"]: t.get("parent_id") for t in themes}

    def top_ancestor(theme_id):
        seen = set()
        cur = theme_id
        while parent_of.get(cur) is not None and cur not in seen:
            seen.add(cur)
            cur = parent_of[cur]
        return cur

    return name_of, top_ancestor


def main():
    if not API_KEY:
        sys.exit("REBRICKABLE_API_KEY non impostata: aggiungila come secret del repository.")

    print("Scarico l'elenco dei temi...")
    themes = fetch_all_pages("themes")
    name_of, top_ancestor = build_theme_maps(themes)
    print(f"{len(themes)} temi totali")

    print("Scarico l'elenco dei set (puo' richiedere qualche minuto)...")
    sets = fetch_all_pages("sets")
    print(f"{len(sets)} set totali")

    # Raggruppa i set per categoria (tema di primo livello)
    by_cat = {}
    for s in sets:
        theme_id = s.get("theme_id")
        if theme_id is None:
            continue
        cat_id = top_ancestor(theme_id)
        cat_name = name_of.get(cat_id, str(cat_id))
        if any(bad in cat_name.lower() for bad in EXCLUDE_NAME_SUBSTRINGS):
            continue
        entry = by_cat.setdefault(cat_id, {"name": cat_name, "sets": []})
        entry["sets"].append({
            "n": s.get("set_num", ""),
            "t": (s.get("name") or "")[:80],
            "y": s.get("year"),
            "p": s.get("num_parts") or 0,
            "img": s.get("set_img_url") or "",
        })

    # Scarta categorie troppo piccole, ordina i set per anno decrescente
    categories = []
    os.makedirs("lego-sets", exist_ok=True)
    for cat_id, data in sorted(by_cat.items(), key=lambda kv: -len(kv[1]["sets"])):
        cat_sets = [s for s in data["sets"] if s["n"]]
        if len(cat_sets) < MIN_SETS_PER_CATEGORY:
            continue
        cat_sets.sort(key=lambda s: (-(s["y"] or 0), s["n"]))
        cover = next((s["img"] for s in cat_sets if s["img"]), "")
        categories.append({"id": cat_id, "n": data["name"], "count": len(cat_sets), "img": cover})
        with open(f"lego-sets/{cat_id}.json", "w", encoding="utf-8") as f:
            json.dump(cat_sets, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  categoria '{data['name']}': {len(cat_sets)} set -> lego-sets/{cat_id}.json")

    categories.sort(key=lambda c: c["n"].lower())
    with open("lego-categories.json", "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=1)

    print(f"\nFATTO: {len(categories)} categorie, {sum(c['count'] for c in categories)} set totali")
    if not categories:
        sys.exit("Nessuna categoria generata: controlla la API key o i filtri.")


if __name__ == "__main__":
    main()
