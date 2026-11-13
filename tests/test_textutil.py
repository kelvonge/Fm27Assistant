from fm_assistant.textutil import (name_key, names_compatible, norm, parse_date, parse_int, parse_money,
                                   parse_positions, parse_wage)


def test_money():
    assert parse_money("4,5 M €")["amount"] == 4_500_000
    assert parse_money("€325K")["amount"] == 325_000
    assert parse_money("12 500 €")["amount"] == 12_500
    assert parse_money("1.250.000 €")["amount"] == 1_250_000
    rng = parse_money("4M € - 6,5M €")
    assert (rng["min"], rng["max"]) == (4_000_000, 6_500_000)
    assert parse_money("Non à vendre") is None
    assert parse_money("") is None


def test_wage_periods():
    assert parse_wage("12 500 € p/s") == 12_500
    assert parse_wage("52 000 € p/m") == 12_000
    assert round(parse_wage("£1.2M p/a")) == 23_077
    assert parse_wage("8 k €", "mois") == 8_000 * 12 / 52


def test_dates():
    assert parse_date("30/6/2028") == "2028-06-30"
    assert parse_date("Ven. 13 nov. 2026") == "2026-11-13"
    assert parse_date("1er juillet 2027") == "2027-07-01"
    assert parse_date("14 Aug 2026") == "2026-08-14"
    assert parse_date("Juin 2028") == "2028-06-30"
    assert parse_date("31/2/2027") is None
    assert parse_date("Très bon") is None


def test_positions_fr_and_en():
    assert parse_positions("D (C), MD, M (C)") == ["DC", "DM", "MC"]
    assert parse_positions("AM (RL), ST (C)") == ["AMR", "AML", "ST"]
    assert parse_positions("MO (DG), BT (C)") == ["AMR", "AML", "ST"]
    assert parse_positions("D/DL (D)") == ["DR", "WBR"]
    assert parse_positions("GB") == ["GK"]
    assert parse_positions("Arsenal") == []


def test_ints_and_names():
    assert parse_int("l6", 1, 20) == 16      # confusion OCR l/1
    assert parse_int("23 ans") == 23
    assert parse_int("25", 1, 20) is None    # hors bornes → inconnu, pas inventé
    assert norm("  Équipe Première : ") == "equipe premiere"
    assert name_key("N'Golo Kanté") == "n golo kante"
    assert names_compatible("k mbappe", "kylian mbappe")
    assert not names_compatible("l dupont", "marc dupont")
