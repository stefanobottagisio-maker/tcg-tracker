#!/usr/bin/env python3
"""
Determina il numero REALE di carte di ogni espansione One Piece sondando il
CDN Limitless (lo stesso usato dalla pagina per le immagini), ma lato server
tramite GitHub Actions invece che dal browser dell'utente.

Perche' serve: nella pagina, il conteggio "carte trovate" veniva scoperto
sondando le immagini una per una nel browser di ogni singolo utente — un
processo soggetto a lentezza di rete, navigazione rapida tra i set e (prima
di un fix precedente) piccoli bug di stato condiviso. Il risultato erano
numeri diversi da un dispositivo all'altro. Eseguendo lo stesso sondaggio
UNA VOLTA sola qui, in un ambiente controllato, e salvando il risultato nel
repository, ogni utente vede sempre lo stesso numero corretto, anche per un
set che non ha ancora mai aperto.

Il sondaggio del CDN resta la fonte primaria (riflette esattamente quali
immagini l'app riesce davvero a mostrare). In aggiunta, lo script scarica
l'indice ufficiale di Limitless (limitlesstcg.com/bandai/op), che elenca il
conteggio carte per set, e lo usa SOLO come controllo incrociato stampato nei
log: se un numero discorda molto da quello sondato, lo si vede subito senza
che possa sovrascrivere silenziosamente il dato reale (l'indice Limitless,
verificato manualmente, non copre ancora OP16/OP17 e in un caso - PRB01 - ha
mostrato un valore chiaramente anomalo).

Output: op-set-totals.json  ->  { "OP01": 121, "OP02": 121, ... }
"""

import json
import re
import time
import urllib.request
import urllib.error

# Stesso elenco set e medesimo tetto di sondaggio usati in index.html (OP_SETS).
# Se in futuro esce un nuovo set, aggiungilo qui E in index.html.
OP_SETS = [
    ("OP01", 130), ("OP02", 130), ("OP03", 130), ("OP04", 130), ("OP05", 130),
    ("OP06", 130), ("OP07", 130), ("OP08", 130), ("OP09", 130), ("OP10", 130),
    ("OP11", 130), ("OP12", 135), ("OP13", 140), ("OP14", 145), ("OP15", 135),
    ("OP16", 140), ("OP17", 140),
    ("EB01", 75), ("EB02", 75), ("EB03", 80), ("EB04", 75),
    ("PRB01", 60), ("PRB02", 60),
]

# Stesso CDN usato come prima fonte immagini nella pagina (OP_HOSTS[0]).
URL_TMPL = "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/one-piece/{set}/{id}_EN.webp"
LIMITLESS_INDEX = "https://limitlesstcg.com/bandai/op"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) collezionista-matto-totals/1.0"}


def exists(url, tries=2):
    """True se l'URL risponde (200), False se 404. Altri errori: riprova."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status == 200
        except urllib.error.HTTPError as e:
            return e.code == 200
        except Exception:
            if attempt == tries - 1:
                return False
            time.sleep(1)
    return False


def count_set(code, max_n):
    found = 0
    misses_in_a_row = 0
    for n in range(1, max_n + 1):
        card_id = f"{code}-{n:03d}"
        url = URL_TMPL.format(set=code, id=card_id)
        if exists(url):
            found += 1
            misses_in_a_row = 0
        else:
            misses_in_a_row += 1
            # Dopo 15 mancanze consecutive assumiamo di aver superato la fine
            # del set (evita di scandire inutilmente fino al tetto massimo).
            if misses_in_a_row >= 15 and found > 0:
                break
    return found


def fetch_limitless_reference():
    """Elenco 'CODICE (N cards)' dall'indice ufficiale, solo per confronto nei log."""
    try:
        req = urllib.request.Request(LIMITLESS_INDEX, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", "ignore")
        return dict(re.findall(r">([A-Z]+\d*)\s*\((\d+)\s*cards?\)<", html))
    except Exception as e:
        print(f"  (controllo incrociato Limitless non disponibile: {e})")
        return {}


def main():
    reference = fetch_limitless_reference()
    if reference:
        print(f"Indice Limitless scaricato per controllo incrociato ({len(reference)} set elencati).\n")

    totals = {}
    for code, max_n in OP_SETS:
        print(f"Sondo {code} (fino a {max_n} carte)...")
        n = count_set(code, max_n)
        totals[code] = n
        ref = reference.get(code)
        flag = ""
        if ref is not None and abs(int(ref) - n) > 3:
            flag = f"  \u26A0 Limitless indica {ref}, differenza notevole: verificare a mano."
        print(f"  -> {code}: {n} carte trovate" + (f" (Limitless: {ref})" if ref else "") + flag)
        time.sleep(0.2)

    with open("op-set-totals.json", "w", encoding="utf-8") as f:
        json.dump(totals, f, ensure_ascii=False, indent=1, sort_keys=True)

    zero = [c for c, n in totals.items() if n == 0]
    print(f"\nFATTO: {len(totals)} set processati.")
    if zero:
        print(f"Attenzione, nessuna carta trovata per: {', '.join(zero)} "
              "(normale per un set non ancora uscito, es. OP17 prima del 28/08/2026).")


if __name__ == "__main__":
    main()

