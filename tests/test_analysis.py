import pytest

from fm_assistant.analysis import contracts, development, ratings, recruitment, squad, tactics
from fm_assistant.analysis.knowledge import load_kb
from fm_assistant.db import Database
from fm_assistant.demo import load_demo


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    db = Database(tmp_path_factory.mktemp("db") / "t.sqlite")
    kb = load_kb()
    load_demo(db, kb)
    enriched, ref = squad.enrich_all(db.players("effectif"), kb)
    return db, kb, enriched, ref


def test_knowledge_base_is_consistent():
    kb = load_kb()
    assert len(kb.roles) >= 40 and len(kb.attrs) == 47
    for r in kb.roles.values():
        assert set(r["cles"] + r["secondaires"]) <= set(kb.attrs), r["id"]
        assert not set(r["cles"]) & set(r["secondaires"]), r["id"]
    for f in kb.formations.values():
        assert len(f["postes"]) == 11


def test_role_score_and_explanation():
    kb = load_kb()
    p = {"name": "Test", "pos": ["DM", "MC"], "attributes": {"passing": 16, "vision": 15, "composure": 14, "first_touch": 15,
         "technique": 14, "decisions": 15, "teamwork": 13, "tackling": 8, "anticipation": 12, "positioning": 11,
         "balance": 12, "off_the_ball": 11, "concentration": 12}}
    sc = ratings.score_role(p["attributes"], "meneur_recule", kb)
    assert sc["fiable"] and 13 < sc["note"] < 15.5
    text = ratings.explain(p, sc)
    assert "Meneur de jeu reculé" in text and "Passes 16" in text


def test_partial_attributes_are_flagged_not_invented():
    kb = load_kb()
    sc = ratings.score_role({"passing": 15}, "meneur_recule", kb)
    assert sc is not None and not sc["fiable"] and sc["couverture"] < 0.3
    assert ratings.score_role({}, "meneur_recule", kb) is None
    e = ratings.enrich({"name": "X", "pos": ["ST"]}, kb, ref=12.0)
    assert e["analyse"]["note"] is None and e["analyse"]["source"] is None


def test_hungarian_is_optimal():
    assert tactics.hungarian([[4, 1, 3], [2, 0, 5], [3, 2, 2]]) == [1, 0, 2]
    assert tactics.hungarian([[1, 2, 3, 0.5], [2, 1, 9, 9]]) == [3, 1]


def test_best_xi_uses_each_player_once_and_skips_injured(ctx):
    db, kb, enriched, ref = ctx
    xi = tactics.best_xi(enriched, kb.formations["4-2-3-1"], kb)
    ids = [s["joueur"]["id"] for s in xi["postes"] if s["joueur"]]
    assert xi["complet"] and len(ids) == len(set(ids)) == 11
    injured = {p["id"] for p in enriched if p.get("injury")}
    assert injured and not injured & set(ids)
    assert xi["postes"][0]["role"] in ("gardien", "gardien_libero")


def test_tactic_check_flags_high_line_with_slow_centre_backs(ctx):
    db, kb, enriched, ref = ctx
    check = tactics.check_tactic(db.document("tactique")["data"], enriched, kb)
    assert any(a["id"] == "ligne_haute_lents" for a in check["alertes"])
    assert tactics.check_tactic(None, enriched, kb)["lue"] is False


def test_suggestions_and_missing_data_message(ctx):
    db, kb, enriched, ref = ctx
    s = tactics.suggest_tactics(enriched, kb, "pressing")
    assert 1 <= len(s["suggestions"]) <= 3 and all(x["explication"] for x in s["suggestions"])
    empty = tactics.suggest_tactics([{"id": 1, "name": "A", "pos": ["ST"]}], kb)
    assert empty["suggestions"] == [] and "attributs" in empty["message"]


def test_recruitment_filters_and_estimates(ctx):
    db, kb, enriched, ref = ctx
    pool = db.players("hors_effectif")
    res = recruitment.search(pool, {"poste": "ST", "age_max": 26}, kb, ref)
    assert res["total"] and all(r["age"] <= 26 for r in res["resultats"])
    notes = [r["note"] for r in res["resultats"] if r["note"] is not None]
    assert notes == sorted(notes, reverse=True)
    all_res = recruitment.search(pool, {}, kb, ref)["resultats"]
    assert any(r["source"] == "etoiles" for r in all_res)  # joueurs sans attributs : estimation signalée
    assert any(r["qualite_prix"] is not None for r in all_res)


def test_contracts_and_youth(ctx):
    db, kb, enriched, ref = ctx
    con = contracts.contracts(enriched, kb, ref, db.game_date(), db.document("finances")["data"])
    assert con["echeances"] and con["echeances"][0]["mois_restants"] <= 6
    assert con["marge_salariale"] == 165_000 - 155_500
    no_date = contracts.contracts(enriched, kb, ref, None, None)
    assert not no_date["echeances"] and any("Date de jeu" in n for n in no_date["notes"])
    youth = development.youth_plan(enriched, kb, ref)
    assert youth["jeunes"] and {j["decision"] for j in youth["jeunes"]} <= {"intégrer", "rotation", "prêt", "garder", "à évaluer"}


def test_merge_without_duplicates_and_history(tmp_path):
    db = Database(tmp_path / "m.sqlite")
    a, created = db.upsert_player({"name": "K. Mbappé", "age": 27, "value": 1e8}, "effectif", 1, "2026-08-01")
    b, created2 = db.upsert_player({"name": "Kylian Mbappé", "age": 27, "attributes": {"pace": 19}}, None, 2, "2026-09-01")
    assert created and not created2 and a == b
    p = db.player(a)
    assert p["name"] == "Kylian Mbappé" and p["value"] == 1e8 and p["attributes"] == {"pace": 19} and p["scope"] == "effectif"
    db.upsert_player({"name": "Kylian Mbappé", "attributes": {"finishing": 18}}, None, 3, "2026-09-01")
    assert db.player(a)["attributes"] == {"pace": 19, "finishing": 18}
    assert [h["game_date"] for h in db.history(a)] == ["2026-08-01", "2026-09-01"]
    c, created3 = db.upsert_player({"name": "Kylian Mbappé", "age": 18}, "cible", 4, "2026-09-01")  # homonyme plus jeune
    assert created3 and c != a
