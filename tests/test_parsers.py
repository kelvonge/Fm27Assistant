"""Parseurs testés sur des mots positionnés à la main (pas besoin d'OCR)."""
from fm_assistant import config
from fm_assistant.analysis.knowledge import load_kb
from fm_assistant.capture.calibration import Calibration
from fm_assistant.capture.ocr import Token
from fm_assistant.capture.parsers import Knowledge4Parse, parse_frame

W, H = 1920, 1080


def kp():
    cfg, _ = config.load_json("ecrans.json")
    return Knowledge4Parse(load_kb().raw, cfg)


def words(rows):
    """rows : [(y, [(x, texte), ...])] → mots de 9 px par caractère, hauteur 20."""
    out = []
    for y, cells in rows:
        for x, text in cells:
            cx = x
            for w in text.split(" "):
                out.append(Token(w, cx, y, 9 * len(w), 20))
                cx += 9 * len(w) + 6
    return out


def parse(rows, **kw):
    return parse_frame(words(rows), None, W, H, kp(), Calibration(), {"periode_salaire": "semaine"}, **kw)


def test_squad_table():
    r = parse([
        (20, [(40, "Effectif"), (1600, "Ven. 13 nov. 2026")]),
        (150, [(60, "Nom"), (420, "Poste"), (640, "Âge"), (1010, "Valeur"), (1210, "Salaire"), (1400, "Contrat")]),
        (190, [(60, "Rémi Barbier"), (420, "M (C)"), (640, "27"), (1010, "850 k €"), (1210, "8 200 € p/s"), (1400, "31/3/2027")]),
        (224, [(60, "N'Golo Sané"), (420, "MO (DG), BT (C)"), (640, "19"), (1010, "1,2 M €"), (1210, "2 000 € p/s"), (1400, "30/6/2030")]),
        (258, [(60, "Total"), (1010, "illisible")]),
    ])
    assert r["screen"] == "effectif" and r["game_date"] == "2026-11-13"
    assert [p["name"] for p in r["players"]] == ["Rémi Barbier", "N'Golo Sané"]
    p = r["players"][0]
    assert (p["age"], p["pos"], p["value"], p["wage"], p["contract_end"]) == (27, ["MC"], 850_000, 8_200, "2027-03-31")
    assert r["players"][1]["pos"] == ["AMR", "AML", "ST"]


def test_unreadable_cell_stays_unknown():
    r = parse([
        (20, [(40, "Effectif")]),
        (150, [(60, "Nom"), (420, "Poste"), (640, "Âge"), (1010, "Valeur")]),
        (190, [(60, "Jean Dupont"), (420, "D (C)"), (640, "??"), (1010, "Inconnue")]),
    ])
    p = r["players"][0]
    assert "age" not in p and "value" not in p and p["pos"] == ["DC"]


def test_profile_attributes_and_info():
    r = parse([
        (20, [(40, "Profil")]),
        (120, [(60, "Rémi Barbier")]),
        (230, [(60, "Âge"), (360, "Valeur"), (660, "Expirele")]),
        (254, [(60, "27 ans"), (360, "850 k €"), (660, "31/3/2027")]),
        (376, [(60, "Centres"), (390, "11"), (520, "Agressivité"), (850, "12"), (980, "Accélération"), (1310, "12")]),
        (414, [(60, "Corners"), (390, "8"), (520, "Anticipation"), (850, "15"), (980, "Agilité"), (1310, "13")]),
        (452, [(60, "Dribbles"), (390, "13"), (520, "Courage"), (850, "13"), (980, "Endurance"), (1310, "16")]),
        (490, [(60, "Finition"), (390, "7"), (520, "Décisions"), (850, "l6"), (980, "Vitesse"), (1310, "11")]),
        (528, [(60, "Passes 16"), (520, "Placement"), (850, "12-15"), (980, "Puissance"), (1310, "42")]),
    ])
    assert r["screen"] == "profil"
    p = r["players"][0]
    a = p["attributes"]
    assert p["name"] == "Rémi Barbier" and p["age"] == 27 and p["contract_end"] == "2027-03-31"
    assert a["crossing"] == 11 and a["decisions"] == 16 and a["passing"] == 16
    assert a["positioning"] == 14 and p["attr_source"]["positioning"] == "plage"
    assert "strength" not in a  # 42 n'est pas un attribut valable : ignoré, pas arrondi


def test_league_table_and_fixtures():
    r = parse([
        (20, [(40, "Classement")]),
        (150, [(60, "Pos"), (140, "Équipe"), (700, "J"), (770, "G"), (840, "N"), (910, "P"), (980, "BP"), (1050, "BC"), (1210, "Pts")]),
        (190, [(60, "1"), (140, "FC Valmont"), (700, "14"), (770, "9"), (840, "3"), (910, "2"), (980, "27"), (1050, "12"), (1210, "30")]),
        (224, [(60, "2"), (140, "AS Brévanne"), (700, "14"), (770, "8"), (840, "4"), (910, "2"), (980, "22"), (1050, "11"), (1210, "28")]),
    ])
    kind, rows = r["doc"]
    assert kind == "classement" and rows[1] == {"rank": 2, "team": "AS Brévanne", "played": 14, "won": 8, "drawn": 4, "lost": 2, "goals_for": 22, "goals_against": 11, "points": 28}
    r = parse([
        (20, [(40, "Calendrier")]),
        (150, [(60, "Date"), (320, "Adversaire"), (760, "Lieu"), (1300, "Résultat")]),
        (190, [(60, "Sam. 14 nov."), (320, "AS Brévanne"), (760, "Ext")]),
        (224, [(60, "Sam. 9 janv."), (320, "US Montclar"), (760, "Dom")]),
    ], ref_date="2026-11-13")
    kind, rows = r["doc"]
    assert rows[0] == {"date": "2026-11-14", "opponent": "AS Brévanne", "venue": "exterieur"}
    assert rows[1]["date"] == "2027-01-09"  # la saison passe l'année suivante


def test_unknown_screen_is_reported():
    r = parse([(300, [(100, "Boîte de réception"), (400, "Message du président")])])
    assert r["screen"] is None and r["players"] == [] and r["doc"] is None
