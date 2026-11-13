"""Chaîne complète sur de fausses captures : OCR réel → reconnaissance → base → API."""
import cv2
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

import synth
from fm_assistant.api import State, create_app
from fm_assistant.capture.ocr import Ocr

needs_ocr = pytest.mark.skipif(not Ocr().available, reason="aucun moteur OCR installé")

PLAYERS = [
    dict(name="Kylian Théo-Müller", positions="D (C), MD", age=23, ability_stars=3.5, potential_stars=4.5, value_txt="4,5 M €", wage_txt="12 500 € p/s", contract_txt="30/6/2028", morale="Très bon"),
    dict(name="Rémi Barbier", positions="M (C)", age=27, ability_stars=4, potential_stars=4, value_txt="850 k €", wage_txt="8 200 € p/s", contract_txt="31/3/2027", morale="Bon"),
    dict(name="N'Golo Sané", positions="MO (DG), BT (C)", age=19, ability_stars=2, potential_stars=5, value_txt="1,2 M € - 1,8 M €", wage_txt="2 000 € p/s", contract_txt="30/6/2030", morale="Excellent"),
]
TECH = [("Centres", 11), ("Corners", 8), ("Coups francs", 9), ("Dribbles", 13), ("Finition", 7), ("Jeu de tête", 12), ("Marquage", 14), ("Passes", 16), ("Penalty", 10), ("Contrôle de balle", 15), ("Tacles", 14), ("Technique", 15), ("Tirs de loin", 11), ("Touches longues", 6)]
MENT = [("Agressivité", 12), ("Anticipation", 15), ("Appels de balle", 12), ("Concentration", 14), ("Courage", 13), ("Décisions", 16), ("Détermination", 17), ("Inspiration", 12), ("Jeu collectif", 16), ("Leadership", 11), ("Placement", 15), ("Sang-froid", 14), ("Vision du jeu", 15), ("Volume de jeu", 16)]
PHYS = [("Accélération", 12), ("Agilité", 13), ("Détente verticale", 10), ("Endurance", 16), ("Équilibre", 14), ("Puissance", 12), ("Qualités physiques naturelles", 15), ("Vitesse", 11)]
INFO = [("Âge", "27 ans"), ("Valeur", "850 k €"), ("Salaire", "8 200 € p/s"), ("Expire le", "31/3/2027"), ("Pied préféré", "Droit")]


@pytest.fixture(scope="module")
def state():
    return State()


@needs_ocr
@pytest.mark.parametrize("size", [(1920, 1080), (1366, 768), (2560, 1440)])
def test_squad_screen_at_several_resolutions(state, size):
    r = state.watcher.process_image(synth.squad_screen(PLAYERS, *size), save=False)
    assert r["screen"] == "effectif" and r["game_date"] == "2026-11-13"
    got = {p["name"]: p for p in r["players"]}
    assert set(got) == {"Kylian Théo-Müller", "Rémi Barbier", "N'Golo Sané"}
    assert got["Rémi Barbier"]["wage"] == 8200 and got["Rémi Barbier"]["contract_end"] == "2027-03-31"
    assert got["N'Golo Sané"]["pos"] == ["AMR", "AML", "ST"] and got["N'Golo Sané"]["value_max"] == 1_800_000
    assert [(p["ability_stars"], p["potential_stars"]) for p in r["players"]] == [(3.5, 4.5), (4.0, 4.0), (2.0, 5.0)]


@needs_ocr
@pytest.mark.parametrize("bars", [False, True])
def test_profile_numbers_and_bars(state, bars):
    img = synth.profile_screen("Rémi Barbier", "M (C), MD", [("Technique", TECH), ("Mental", MENT), ("Physique", PHYS)], INFO, bars=bars)
    r = state.watcher.process_image(img, save=False)
    p = r["players"][0]
    assert r["screen"] == "profil" and p["name"] == "Rémi Barbier" and p["age"] == 27 and p["foot"] == "Droit"
    assert len(p["attributes"]) == 36
    expected = {"passing": 16, "finishing": 7, "determination": 17, "pace": 11, "stamina": 16}
    for k, v in expected.items():
        assert abs(p["attributes"][k] - v) <= (1 if bars else 0), k
    assert set(p["attr_source"].values()) == ({"barres"} if bars else {"exact"})


@needs_ocr
def test_full_flow_through_api(state):
    client = TestClient(create_app(state))
    client.put("/api/settings", json={"club": "FC Valmont", "division": "Ligue 2"})
    ok, png = cv2.imencode(".png", synth.squad_screen(PLAYERS))
    assert client.post("/api/capture/upload", content=png.tobytes()).status_code == 200
    img = synth.profile_screen("Rémi Barbier", "M (C), MD", [("Technique", TECH), ("Mental", MENT), ("Physique", PHYS)], INFO)
    client.post("/api/capture/upload", content=cv2.imencode(".png", img)[1].tobytes())
    lineup = [("Barbier", "Meneur de jeu reculé", .4, .42), ("Sané", "Attaquant intérieur", .12, .68), ("Théo-Müller", "Défenseur central", .4, .2), ("Morel", "Ailier", .88, .68)]
    client.post("/api/capture/upload", content=cv2.imencode(".png", synth.tactic_screen("4-2-3-1", "Positive", ["Ligne défensive plus haute", "Contre-pressing"], lineup))[1].tobytes())
    client.post("/api/capture/upload", content=cv2.imencode(".png", synth.finances_screen([("Solde", "3,4 M €"), ("Budget transferts", "1,25 M €"), ("Budget salaires", "165 000 € p/s")]))[1].tobytes())
    status = client.get("/api/status").json()
    assert status["compteurs"]["effectif"] == 3 and status["date_jeu"] == "2026-11-13"
    players = client.get("/api/players").json()["joueurs"]
    barbier = next(p for p in players if p["name"] == "Rémi Barbier")
    assert barbier["n_attributs"] == 36 and barbier["analyse"]["source"] == "attributs" and barbier["scope"] == "effectif"
    detail = client.get(f"/api/players/{barbier['id']}").json()
    assert "Rémi Barbier" in detail["analyse"]["explication"]
    tac = client.get("/api/tactics").json()["coherence"]
    assert tac["lue"] and tac["formation"] == "4-2-3-1" and "Ligne défensive plus haute" in tac["instructions"]
    assert any(r["joueur"] == "Rémi Barbier" and r["role_nom"] == "Meneur de jeu reculé" for r in tac["roles"])
    con = client.get("/api/contracts").json()
    assert con["finances"]["transfer_budget"] == 1_250_000 and con["finances"]["wage_budget"] == 165_000
    guide = client.get("/api/scan-guide").json()
    assert {e["ecran"] for e in guide["etapes"] if e["fait"]} >= {"effectif", "tactique", "finances"}
    # Correction de calibrage : la fiche mal nommée est renommée, pas dupliquée
    client.post("/api/calibration/correction", json={"type": "texte", "lu": "N'Golo Sané", "correct": "N'Golo Sanné"})
    names = [p["name"] for p in client.get("/api/players").json()["joueurs"]]
    assert "N'Golo Sanné" in names and "N'Golo Sané" not in names and len(names) == 3
    client.post("/api/calibration/correction", json={"type": "texte", "lu": "N'Golo Sané", "correct": ""})


def test_demo_endpoints():
    client = TestClient(create_app(State()))
    assert client.post("/api/demo/load").json()["joueurs"] == 26
    for url in ["/api/dashboard", "/api/players", "/api/squad/analysis", "/api/tactics", "/api/recruitment/needs", "/api/youth",
                "/api/contracts", "/api/ideas", "/api/search?q=bar", "/api/overlay", "/api/scan-guide", "/api/knowledge", "/"]:
        assert client.get(url).status_code == 200, url
    d = client.get("/api/dashboard").json()
    assert d["niveau"]["onze_type"] and d["alertes"] and d["classement"]["team"] == "FC Valmont"
    assert client.post("/api/recruitment/search", json={"poste": "ST"}).json()["total"] > 0
    assert client.get("/api/players/99999").status_code == 404
