"""Régénère fm_assistant/data/connaissances.json (base de connaissances FM).

Le JSON produit reste éditable à la main : ce script n'est utile que pour
repartir d'une base propre.  Usage : python tools/build_knowledge.py
"""
import json
from pathlib import Path

ATTRS = """
corners|Corners|Corners|technique|
crossing|Centres|Crossing|technique|
dribbling|Dribbles|Dribbling|technique|Dribble
finishing|Finition|Finishing|technique|
first_touch|Contrôle de balle|First Touch|technique|Première touche;Contrôle
free_kicks|Coups francs|Free Kick Taking|technique|Free Kicks;Coup franc
heading|Jeu de tête|Heading|technique|Tête
long_shots|Tirs de loin|Long Shots|technique|
long_throws|Touches longues|Long Throws|technique|
marking|Marquage|Marking|technique|
passing|Passes|Passing|technique|Passe
penalties|Penalty|Penalty Taking|technique|Penaltys;Penalties;Pénaltys
tackling|Tacles|Tackling|technique|Tacle
technique|Technique|Technique|technique|
aggression|Agressivité|Aggression|mental|
anticipation|Anticipation|Anticipation|mental|
bravery|Courage|Bravery|mental|
composure|Sang-froid|Composure|mental|Sang froid
concentration|Concentration|Concentration|mental|
decisions|Décisions|Decisions|mental|Prise de décision
determination|Détermination|Determination|mental|
flair|Inspiration|Flair|mental|Créativité
leadership|Leadership|Leadership|mental|Charisme
off_the_ball|Appels de balle|Off The Ball|mental|Jeu sans ballon;Sans ballon
positioning|Placement|Positioning|mental|
teamwork|Jeu collectif|Teamwork|mental|Collectif;Travail d'équipe
vision|Vision du jeu|Vision|mental|
work_rate|Volume de jeu|Work Rate|mental|Activité
acceleration|Accélération|Acceleration|physique|
agility|Agilité|Agility|physique|
balance|Équilibre|Balance|physique|
jumping|Détente verticale|Jumping Reach|physique|Détente;Jumping
natural_fitness|Qualités physiques naturelles|Natural Fitness|physique|Qual. phys. nat.;Physique naturel
pace|Vitesse|Pace|physique|
stamina|Endurance|Stamina|physique|
strength|Puissance|Strength|physique|Force
aerial_reach|Jeu aérien|Aerial Reach|gardien|Sorties aériennes;Allonge
command_of_area|Autorité dans la surface|Command Of Area|gardien|Présence dans la surface;Domination de la surface
communication|Communication|Communication|gardien|
eccentricity|Excentricité|Eccentricity|gardien|
handling|Prises de balle|Handling|gardien|Prise de balle
kicking|Dégagements|Kicking|gardien|Jeu au pied;Dégagement
one_on_ones|Un contre un|One On Ones|gardien|Face à face;1 contre 1
punching|Tendance à boxer|Punching (Tendency)|gardien|Boxer le ballon;Punching
reflexes|Réflexes|Reflexes|gardien|
rushing_out|Sorties|Rushing Out (Tendency)|gardien|Tendance à sortir;Rushing Out
throwing|Relances à la main|Throwing|gardien|Relances
"""

# id|nom FR|nom EN|postes|clés|secondaires|description
ROLES = """
gardien|Gardien de but|Goalkeeper|GK|reflexes,handling,positioning,one_on_ones,aerial_reach,command_of_area,concentration|communication,kicking,throwing,anticipation,decisions,agility|Gardien classique qui reste sur sa ligne et sécurise sa surface.
gardien_libero|Gardien libéro|Sweeper Keeper|GK|reflexes,one_on_ones,rushing_out,anticipation,command_of_area,kicking,first_touch,passing|handling,positioning,composure,concentration,decisions,acceleration,agility,throwing,vision|Gardien qui sort loin de son but et participe à la relance. Indispensable avec une ligne haute.
defenseur_central|Défenseur central|Central Defender|DC|heading,marking,tackling,positioning,jumping,strength|anticipation,concentration,decisions,bravery,composure,pace,aggression|Défenseur axial polyvalent.
defenseur_relanceur|Défenseur relanceur|Ball-Playing Defender|DC|heading,marking,tackling,positioning,passing,composure,jumping,strength|first_touch,technique,vision,anticipation,decisions,concentration,pace,bravery|Défenseur axial chargé de lancer le jeu par des passes propres.
defenseur_strict|Défenseur strict|No-Nonsense Centre-Back|DC|heading,marking,tackling,positioning,jumping,strength,bravery|anticipation,concentration,aggression,pace|Défenseur qui dégage sans prendre de risque.
libero|Libéro|Libero|DC|passing,first_touch,technique,composure,decisions,positioning,tackling,anticipation,marking,heading|vision,dribbling,teamwork,concentration,jumping,strength,pace,stamina|Défenseur libre qui monte au milieu en phase de possession.
defenseur_central_excentre|Défenseur central excentré|Wide Centre-Back|DC|heading,marking,tackling,positioning,strength,jumping,pace|crossing,dribbling,passing,stamina,work_rate,anticipation,concentration,decisions,agility|Axial d'une défense à trois qui s'écarte et accompagne le couloir.
arriere_lateral|Arrière latéral|Full-Back|DR,DL|marking,tackling,positioning,anticipation,concentration,teamwork,stamina,pace|crossing,passing,work_rate,decisions,acceleration,first_touch|Latéral équilibré entre défense et soutien.
arriere_lateral_strict|Arrière latéral strict|No-Nonsense Full-Back|DR,DL|marking,tackling,positioning,strength,anticipation,concentration|heading,bravery,aggression,teamwork,pace|Latéral purement défensif.
arriere_lateral_interieur|Arrière latéral intérieur|Inverted Full-Back|DR,DL|heading,marking,tackling,positioning,strength,anticipation|passing,first_touch,composure,concentration,decisions,pace,jumping,agility|Latéral qui rentre former une défense à trois en possession.
lateral_offensif|Latéral offensif|Wing-Back|DR,DL,WBR,WBL|crossing,dribbling,tackling,marking,stamina,work_rate,acceleration,pace,teamwork|passing,first_touch,technique,off_the_ball,positioning,anticipation,decisions,concentration,agility,balance|Latéral qui occupe tout le couloir.
lateral_complet|Latéral complet|Complete Wing-Back|DR,DL,WBR,WBL|crossing,dribbling,technique,first_touch,off_the_ball,stamina,work_rate,acceleration,pace,teamwork|passing,tackling,marking,flair,decisions,anticipation,positioning,agility,balance|Latéral très offensif, quasi-ailier.
lateral_inverse|Latéral inversé|Inverted Wing-Back|DR,DL,WBR,WBL|passing,first_touch,tackling,decisions,positioning,teamwork,composure|technique,marking,vision,anticipation,concentration,work_rate,stamina,acceleration,agility|Latéral qui rentre au milieu en possession.
milieu_defensif|Milieu défensif|Defensive Midfielder|DM|tackling,positioning,anticipation,concentration,teamwork,decisions|marking,passing,first_touch,composure,work_rate,stamina,strength,aggression|Milieu qui protège la défense.
sentinelle|Sentinelle|Anchor|DM|marking,tackling,positioning,anticipation,concentration,decisions|composure,teamwork,strength,heading|Milieu fixe devant la défense, ne quitte jamais sa zone.
demi_centre|Demi-centre|Half-Back|DM|marking,tackling,positioning,anticipation,concentration,decisions,composure,teamwork|passing,first_touch,heading,strength,jumping,stamina,work_rate,bravery,aggression|Milieu qui redescend entre les centraux en possession.
milieu_recuperateur|Milieu récupérateur|Ball-Winning Midfielder|DM,MC|tackling,aggression,anticipation,work_rate,stamina,teamwork,bravery|marking,positioning,concentration,decisions,strength,pace,agility,passing|Milieu qui harcèle le porteur pour récupérer le ballon.
meneur_recule|Meneur de jeu reculé|Deep-Lying Playmaker|DM,MC|passing,first_touch,technique,vision,composure,decisions,teamwork|anticipation,positioning,balance,off_the_ball,tackling,concentration|Organisateur placé bas, oriente le jeu par ses passes.
regista|Regista|Regista|DM|passing,first_touch,technique,vision,composure,decisions,flair,off_the_ball,teamwork|anticipation,dribbling,long_shots,balance|Meneur reculé totalement libre, cœur créatif de l'équipe.
volante|Volante|Segundo Volante|DM|tackling,marking,positioning,passing,off_the_ball,work_rate,stamina,pace|finishing,long_shots,first_touch,anticipation,decisions,concentration,composure,strength,acceleration,balance|Milieu défensif qui se projette jusque dans la surface.
meneur_libre|Meneur de jeu libre|Roaming Playmaker|DM,MC|passing,first_touch,technique,vision,composure,decisions,off_the_ball,teamwork,work_rate,stamina,anticipation|dribbling,long_shots,positioning,concentration,acceleration,pace,agility,balance|Meneur qui porte le ballon et se déplace partout.
milieu_central|Milieu central|Central Midfielder|MC|passing,first_touch,tackling,decisions,teamwork,work_rate|technique,vision,composure,anticipation,concentration,positioning,off_the_ball,stamina|Milieu axial polyvalent.
box_to_box|Milieu relayeur|Box-to-Box Midfielder|MC|passing,tackling,off_the_ball,teamwork,work_rate,stamina|dribbling,finishing,first_touch,long_shots,technique,aggression,anticipation,composure,decisions,positioning,acceleration,balance,pace,strength|Milieu d'une surface à l'autre.
meneur_avance|Meneur de jeu avancé|Advanced Playmaker|MC,AMC,AMR,AML|passing,first_touch,technique,vision,composure,decisions,off_the_ball,teamwork,flair|dribbling,anticipation,agility,balance,acceleration|Créateur placé entre les lignes.
mezzala|Mezzala|Mezzala|MC|passing,technique,off_the_ball,decisions,work_rate,acceleration,dribbling,first_touch|vision,long_shots,finishing,composure,anticipation,flair,balance,stamina,tackling|Milieu axial qui s'excentre dans le demi-espace.
carrilero|Carrilero|Carrilero|MC|passing,tackling,first_touch,decisions,positioning,teamwork,stamina,work_rate|technique,anticipation,composure,concentration,vision,off_the_ball|Milieu navette qui couvre latéralement.
milieu_excentre|Milieu excentré|Wide Midfielder|MR,ML|passing,tackling,decisions,teamwork,work_rate,stamina,crossing|first_touch,technique,anticipation,composure,concentration,positioning,off_the_ball,vision|Milieu de couloir équilibré.
ailier|Ailier|Winger|MR,ML,AMR,AML|crossing,dribbling,technique,acceleration,pace,agility|first_touch,passing,off_the_ball,flair,work_rate,stamina,balance,anticipation|Ailier de débordement qui centre.
ailier_defensif|Ailier défensif|Defensive Winger|MR,ML|technique,anticipation,off_the_ball,positioning,teamwork,work_rate,stamina,tackling|crossing,dribbling,first_touch,marking,passing,aggression,concentration,decisions,acceleration|Ailier qui presse et défend haut.
ailier_interieur|Ailier intérieur|Inverted Winger|MR,ML,AMR,AML|dribbling,passing,technique,first_touch,acceleration,agility,composure,decisions|crossing,long_shots,vision,off_the_ball,flair,work_rate,pace,balance,stamina,anticipation|Ailier qui repique dans l'axe pour créer.
meneur_excentre|Meneur de jeu excentré|Wide Playmaker|MR,ML|passing,first_touch,technique,vision,composure,decisions,teamwork|dribbling,off_the_ball,agility,balance,flair,anticipation|Créateur partant d'un côté.
milieu_offensif|Milieu offensif|Attacking Midfielder|AMC|first_touch,long_shots,passing,technique,anticipation,decisions,flair,off_the_ball|dribbling,finishing,composure,vision,agility,acceleration|Milieu avancé polyvalent.
attaquant_ombre|Attaquant de l'ombre|Shadow Striker|AMC|dribbling,finishing,first_touch,anticipation,composure,off_the_ball,acceleration|passing,technique,concentration,decisions,work_rate,agility,balance,pace,stamina|Milieu offensif qui joue comme un second attaquant.
trequartista|Trequartista|Trequartista|AMC,ST|passing,first_touch,technique,dribbling,vision,composure,decisions,flair,off_the_ball,acceleration|finishing,anticipation,agility,balance|Numéro 10 libre de tout travail défensif.
enganche|Enganche|Enganche|AMC|passing,first_touch,technique,vision,composure,decisions,flair|dribbling,anticipation,off_the_ball,teamwork,agility|Meneur fixe, pivot créatif de l'équipe.
attaquant_interieur|Attaquant intérieur|Inside Forward|AMR,AML|dribbling,finishing,first_touch,technique,anticipation,off_the_ball,acceleration,agility|long_shots,passing,composure,flair,work_rate,balance,pace,stamina|Ailier qui repique pour marquer.
raumdeuter|Raumdeuter|Raumdeuter|AMR,AML|finishing,anticipation,composure,concentration,decisions,off_the_ball,balance|first_touch,technique,work_rate,acceleration,stamina|Chasseur d'espaces partant du côté.
pivot_excentre|Pivot excentré|Wide Target Forward|AMR,AML|heading,bravery,teamwork,jumping,strength|crossing,first_touch,anticipation,off_the_ball,work_rate,balance,stamina|Point d'appui aérien placé sur un côté.
attaquant_avance|Attaquant avancé|Advanced Forward|ST|dribbling,finishing,first_touch,technique,composure,off_the_ball,acceleration|passing,anticipation,decisions,work_rate,agility,balance,pace,stamina|Avant-centre qui attaque la profondeur.
renard|Renard des surfaces|Poacher|ST|finishing,anticipation,composure,off_the_ball|first_touch,heading,technique,decisions,acceleration|Buteur pur à la limite du hors-jeu.
attaquant_complet|Attaquant complet|Complete Forward|ST|dribbling,finishing,first_touch,heading,long_shots,passing,technique,anticipation,composure,decisions,off_the_ball,vision,acceleration,agility,strength|teamwork,work_rate,balance,jumping,pace,stamina|Avant-centre capable de tout faire.
attaquant_pivot|Attaquant pivot|Target Forward|ST|heading,bravery,teamwork,balance,jumping,strength|finishing,first_touch,aggression,anticipation,composure,decisions,off_the_ball|Point d'appui physique dos au but.
attaquant_retrait|Attaquant en retrait|Deep-Lying Forward|ST|first_touch,passing,technique,composure,decisions,off_the_ball,teamwork|finishing,anticipation,flair,vision,balance,strength|Attaquant qui décroche pour lier le jeu.
faux_neuf|Faux neuf|False Nine|ST|dribbling,first_touch,passing,technique,composure,decisions,off_the_ball,vision,acceleration,agility|finishing,anticipation,flair,teamwork,balance|Avant-centre qui décroche au milieu pour créer.
attaquant_pressing|Attaquant de pressing|Pressing Forward|ST|aggression,anticipation,bravery,off_the_ball,teamwork,work_rate,acceleration,pace,stamina|first_touch,composure,concentration,decisions,agility,balance,strength,finishing|Premier défenseur de l'équipe, harcèle la relance adverse.
"""

D4 = [("DG", ["DL", "WBL"], 12, 26), ("DCG", ["DC"], 36, 19), ("DCD", ["DC"], 64, 19), ("DD", ["DR", "WBR"], 88, 26)]
D3 = [("DCG", ["DC"], 26, 20), ("DC", ["DC"], 50, 17), ("DCD", ["DC"], 74, 20)]
GK = [("GB", ["GK"], 50, 5)]


def slots(lst):
    return [{"id": i, "postes": p, "x": x, "y": y} for i, p, x, y in lst]


FORMATIONS = [
    {"id": "4-2-3-1", "nom": "4-2-3-1", "postes": slots(GK + D4 + [("MDG", ["DM", "MC"], 37, 41), ("MDD", ["DM", "MC"], 63, 41), ("MOG", ["AML", "ML"], 14, 68), ("MOC", ["AMC"], 50, 65), ("MOD", ["AMR", "MR"], 86, 68), ("BU", ["ST"], 50, 88)])},
    {"id": "4-3-3", "nom": "4-3-3", "postes": slots(GK + D4 + [("MDC", ["DM"], 50, 38), ("MCG", ["MC"], 32, 53), ("MCD", ["MC"], 68, 53), ("AG", ["AML", "ML"], 14, 76), ("AD", ["AMR", "MR"], 86, 76), ("BU", ["ST"], 50, 88)])},
    {"id": "4-4-2", "nom": "4-4-2", "postes": slots(GK + D4 + [("MG", ["ML", "AML"], 12, 55), ("MCG", ["MC"], 38, 49), ("MCD", ["MC"], 62, 49), ("MD", ["MR", "AMR"], 88, 55), ("BUG", ["ST"], 38, 86), ("BUD", ["ST"], 62, 86)])},
    {"id": "4-1-4-1", "nom": "4-1-4-1", "postes": slots(GK + D4 + [("MDC", ["DM"], 50, 37), ("MG", ["ML", "AML"], 12, 60), ("MCG", ["MC"], 38, 56), ("MCD", ["MC"], 62, 56), ("MD", ["MR", "AMR"], 88, 60), ("BU", ["ST"], 50, 88)])},
    {"id": "4-3-1-2", "nom": "4-3-1-2", "postes": slots(GK + D4 + [("MCG", ["MC"], 28, 47), ("MC", ["MC", "DM"], 50, 42), ("MCD", ["MC"], 72, 47), ("MOC", ["AMC"], 50, 66), ("BUG", ["ST"], 38, 87), ("BUD", ["ST"], 62, 87)])},
    {"id": "3-5-2", "nom": "3-5-2", "postes": slots(GK + D3 + [("LG", ["WBL", "ML", "DL"], 8, 50), ("LD", ["WBR", "MR", "DR"], 92, 50), ("MDC", ["DM", "MC"], 50, 38), ("MCG", ["MC"], 34, 56), ("MCD", ["MC"], 66, 56), ("BUG", ["ST"], 38, 86), ("BUD", ["ST"], 62, 86)])},
    {"id": "5-3-2", "nom": "5-3-2", "postes": slots(GK + D3 + [("LG", ["WBL", "DL"], 8, 34), ("LD", ["WBR", "DR"], 92, 34), ("MCG", ["MC"], 28, 55), ("MC", ["MC", "DM"], 50, 49), ("MCD", ["MC"], 72, 55), ("BUG", ["ST"], 38, 86), ("BUD", ["ST"], 62, 86)])},
    {"id": "3-4-3", "nom": "3-4-3", "postes": slots(GK + D3 + [("LG", ["WBL", "ML", "DL"], 8, 50), ("MCG", ["MC", "DM"], 38, 46), ("MCD", ["MC", "DM"], 62, 46), ("LD", ["WBR", "MR", "DR"], 92, 50), ("AG", ["AML"], 20, 77), ("AD", ["AMR"], 80, 77), ("BU", ["ST"], 50, 88)])},
]

TACTIQUES = [
    {"id": "gegenpressing", "nom": "Pressing intense (gegenpressing)", "style": "pressing",
     "description": "Récupérer le ballon haut et vite, attaquer avant que l'adversaire ne se replace.",
     "exigences": {"work_rate": 3, "stamina": 3, "teamwork": 2.5, "aggression": 2, "anticipation": 2, "acceleration": 2, "pace": 1.5, "decisions": 1.5, "natural_fitness": 1},
     "formations": ["4-2-3-1", "4-3-3"], "mentalite": "Positive",
     "instructions": ["Pressing beaucoup plus intense", "Ligne défensive plus haute", "Contre-pressing", "Tempo plus élevé", "Relances courtes du gardien"]},
    {"id": "possession", "nom": "Jeu de possession", "style": "possession",
     "description": "Confisquer le ballon, faire courir l'adversaire et attendre l'ouverture.",
     "exigences": {"passing": 3, "first_touch": 3, "technique": 2.5, "composure": 2.5, "vision": 2, "decisions": 2, "teamwork": 2, "off_the_ball": 1.5, "balance": 1},
     "formations": ["4-3-3", "4-2-3-1", "3-4-3"], "mentalite": "Maîtrise",
     "instructions": ["Passes plus courtes", "Repartir de derrière", "Travailler le ballon jusque dans la surface", "Tempo légèrement plus faible", "Contre-pressing"]},
    {"id": "contre_attaque", "nom": "Contre-attaque rapide", "style": "contre",
     "description": "Bloc compact, puis projection très rapide dans le dos de la défense.",
     "exigences": {"pace": 3, "acceleration": 3, "off_the_ball": 2.5, "anticipation": 2, "passing": 2, "positioning": 2, "concentration": 2, "decisions": 1.5, "finishing": 1.5},
     "formations": ["4-4-2", "4-2-3-1", "5-3-2"], "mentalite": "Équilibrée",
     "instructions": ["Contre-attaquer", "Passes plus directes", "Ligne défensive plus basse", "Bloc médian", "Passes dans les espaces"]},
    {"id": "jeu_direct", "nom": "Jeu direct et physique", "style": "direct",
     "description": "Jeu long vers un point d'appui, deuxièmes ballons et duels aériens.",
     "exigences": {"jumping": 3, "heading": 3, "strength": 2.5, "bravery": 2, "work_rate": 2, "crossing": 2, "aggression": 1.5, "teamwork": 1.5, "long_throws": 0.5},
     "formations": ["4-4-2", "3-5-2"], "mentalite": "Équilibrée",
     "instructions": ["Passes beaucoup plus directes", "Centres aériens", "Jouer plus large", "Être plus physique", "Longs dégagements du gardien"]},
    {"id": "bloc_bas", "nom": "Bloc bas solide", "style": "defensif",
     "description": "Défendre regroupé, fermer l'axe et jouer les coups de pied arrêtés et les contres.",
     "exigences": {"positioning": 3, "concentration": 3, "marking": 2.5, "tackling": 2.5, "anticipation": 2, "teamwork": 2, "strength": 2, "heading": 2, "bravery": 1.5, "decisions": 1.5},
     "formations": ["5-3-2", "4-1-4-1"], "mentalite": "Prudente",
     "instructions": ["Ligne défensive beaucoup plus basse", "Bloc bas", "Jouer plus étroit", "Pressing moins intense", "Gagner du temps (en fin de match)"]},
    {"id": "jeu_ailes", "nom": "Jeu sur les ailes", "style": "ailes",
     "description": "Étirer le bloc adverse, déborder et multiplier les centres.",
     "exigences": {"crossing": 3, "dribbling": 2.5, "pace": 2.5, "acceleration": 2, "heading": 2, "stamina": 2, "off_the_ball": 2, "jumping": 1.5, "work_rate": 1.5},
     "formations": ["4-4-2", "3-4-3", "4-3-3"], "mentalite": "Positive",
     "instructions": ["Jouer plus large", "Concentrer le jeu sur les ailes", "Dédoublements à gauche et à droite", "Centres fréquents", "Tempo plus élevé"]},
]

INCOHERENCES = [
    {"id": "ligne_haute_lents", "si_instructions": ["ligne defensive plus haute", "ligne defensive beaucoup plus haute", "higher defensive line", "much higher defensive line"],
     "postes": ["DC"], "attributs": ["pace", "acceleration"], "seuil": 12, "sens": "<",
     "message": "Ligne défensive haute avec des défenseurs centraux lents : chaque ballon dans le dos sera dangereux.",
     "conseil": "Baissez la ligne d'un cran, ou alignez vos centraux les plus rapides et un gardien libéro."},
    {"id": "pressing_endurance", "si_instructions": ["pressing plus intense", "pressing beaucoup plus intense", "contre-pressing", "counter-press", "more urgent", "much more often"],
     "postes": ["*"], "attributs": ["stamina", "work_rate"], "seuil": 12, "sens": "<",
     "message": "Pressing intense avec une équipe peu endurante : le bloc va s'effondrer en seconde période.",
     "conseil": "Réduisez l'intensité du pressing ou faites tourner davantage."},
    {"id": "passes_courtes_technique", "si_instructions": ["passes plus courtes", "passes beaucoup plus courtes", "repartir de derriere", "shorter passing", "play out of defence"],
     "postes": ["DC", "DM", "MC"], "attributs": ["passing", "first_touch", "composure"], "seuil": 11.5, "sens": "<",
     "message": "Relance courte avec des joueurs axiaux peu à l'aise techniquement : risque élevé de pertes de balle dans votre camp.",
     "conseil": "Passez à une relance plus directe, ou installez un défenseur relanceur et un meneur reculé plus sûrs."},
    {"id": "jeu_direct_aerien", "si_instructions": ["passes plus directes", "passes beaucoup plus directes", "centres aeriens", "more direct passing", "float crosses"],
     "postes": ["ST"], "attributs": ["jumping", "heading", "strength"], "seuil": 11.5, "sens": "<",
     "message": "Jeu long sans point d'appui aérien devant : vos attaquants perdront la majorité des duels.",
     "conseil": "Jouez plutôt au sol dans les espaces, ou alignez un attaquant pivot."},
    {"id": "contre_lents", "si_instructions": ["contre-attaquer", "passes dans les espaces", "counter", "pass into space"],
     "postes": ["ST", "AMR", "AML", "MR", "ML"], "attributs": ["pace", "acceleration"], "seuil": 12.5, "sens": "<",
     "message": "Contre-attaque avec des joueurs offensifs lents : les transitions n'aboutiront pas.",
     "conseil": "Privilégiez un jeu plus posé ou des ailiers plus rapides."},
    {"id": "centres_sans_tete", "si_instructions": ["centres frequents", "centrer plus souvent", "cross more often", "hit early crosses"],
     "postes": ["ST"], "attributs": ["heading", "jumping"], "seuil": 11, "sens": "<",
     "message": "Beaucoup de centres mais des attaquants faibles de la tête.",
     "conseil": "Demandez des centres à ras de terre ou travaillez le ballon jusque dans la surface."},
    {"id": "ligne_haute_gardien", "si_instructions": ["ligne defensive plus haute", "ligne defensive beaucoup plus haute", "higher defensive line"],
     "postes": ["GK"], "attributs": ["rushing_out", "one_on_ones", "acceleration"], "seuil": 11, "sens": "<",
     "message": "Ligne haute avec un gardien peu à l'aise loin de son but.",
     "conseil": "Un gardien libéro rapide est préférable derrière une ligne haute."},
]

NIVEAUX = [
    {"mots_cles": ["premier league", "liga", "laliga", "serie a", "bundesliga", "ligue 1"], "niveau": 14.6, "libelle": "Élite européenne"},
    {"mots_cles": ["eredivisie", "liga portugal", "primeira", "pro league", "super lig", "championship", "premiership"], "niveau": 13.3, "libelle": "Première division intermédiaire"},
    {"mots_cles": ["ligue 2", "serie b", "2. bundesliga", "segunda", "laliga 2", "super league", "mls"], "niveau": 12.3, "libelle": "Deuxième division majeure"},
    {"mots_cles": ["league one", "national", "3. liga", "serie c", "primera rfef", "challenge league"], "niveau": 11.2, "libelle": "Troisième niveau"},
    {"mots_cles": ["league two", "national 2", "regionalliga", "serie d"], "niveau": 10.2, "libelle": "Quatrième niveau"},
    {"mots_cles": ["national league", "national 3", "regional", "régional", "vanarama"], "niveau": 9.2, "libelle": "Semi-professionnel"},
]

ENTRAINEMENT = {
    "passing": "Passes courtes / Jeu de passes", "first_touch": "Contrôle de balle", "technique": "Technique", "vision": "Jeu de passes (meneur)",
    "dribbling": "Dribbles", "crossing": "Centres", "finishing": "Finition", "long_shots": "Tirs de loin", "heading": "Jeu aérien",
    "tackling": "Tacles / Défense individuelle", "marking": "Marquage", "positioning": "Placement défensif", "off_the_ball": "Déplacements offensifs",
    "composure": "Finition / situations de match", "decisions": "Temps de jeu et mentor", "anticipation": "Temps de jeu et mentor", "concentration": "Temps de jeu et mentor",
    "teamwork": "Mentor / cohésion", "work_rate": "Mentor (travailleur)", "bravery": "Mentor", "aggression": "Mentor", "flair": "Temps de jeu",
    "pace": "Vivacité (sprint)", "acceleration": "Vivacité (sprint)", "agility": "Agilité et équilibre", "balance": "Agilité et équilibre",
    "stamina": "Endurance", "strength": "Musculation", "jumping": "Jeu aérien / musculation", "natural_fitness": "Charge physique régulière",
    "reflexes": "Gardien : arrêts réflexes", "handling": "Gardien : prises de balle", "one_on_ones": "Gardien : un contre un", "aerial_reach": "Gardien : jeu aérien",
    "command_of_area": "Gardien : jeu aérien", "kicking": "Gardien : jeu au pied", "throwing": "Gardien : relance", "rushing_out": "Gardien : un contre un", "communication": "Gardien : tactique",
}


def main():
    attrs = []
    for line in ATTRS.strip().splitlines():
        k, fr, en, cat, alias = line.split("|")
        attrs.append({"id": k, "nom": fr, "en": en, "categorie": cat, "alias": [a for a in alias.split(";") if a]})
    roles = []
    for line in ROLES.strip().splitlines():
        i, fr, en, pos, cle, sec, desc = line.split("|")
        roles.append({"id": i, "nom": fr, "en": en, "postes": pos.split(","), "cles": cle.split(","), "secondaires": sec.split(","), "poids": {}, "description": desc})
    kb = {
        "_aide": "Fichier éditable. 'poids_defaut' fixe le poids des attributs clés et secondaires ; chaque rôle peut surcharger un attribut via son champ 'poids' (ex. {\"passing\": 5}). Les noms de rôles peuvent être adaptés à votre version du jeu.",
        "version": 1,
        "poids_defaut": {"cle": 3.0, "secondaire": 1.5},
        "couverture_minimale": 0.6,
        "attributs": attrs,
        "postes": {"GK": "GB", "DR": "DD", "DL": "DG", "DC": "DC", "WBR": "LD", "WBL": "LG", "DM": "MDC", "MC": "MC", "MR": "MD", "ML": "MG", "AMR": "MOD", "AML": "MOG", "AMC": "MOC", "ST": "BU"},
        "postes_noms": {"GK": "Gardien", "DR": "Défenseur droit", "DL": "Défenseur gauche", "DC": "Défenseur central", "WBR": "Latéral droit", "WBL": "Latéral gauche", "DM": "Milieu défensif", "MC": "Milieu central", "MR": "Milieu droit", "ML": "Milieu gauche", "AMR": "Ailier droit", "AML": "Ailier gauche", "AMC": "Milieu offensif axial", "ST": "Attaquant"},
        "postes_proches": {"DR": ["WBR"], "WBR": ["DR", "MR"], "DL": ["WBL"], "WBL": ["DL", "ML"], "DM": ["MC", "DC"], "MC": ["DM", "AMC"], "AMC": ["MC", "ST"], "MR": ["AMR", "WBR"], "AMR": ["MR"], "ML": ["AML", "WBL"], "AML": ["ML"], "ST": ["AMC"], "DC": ["DM"]},
        "malus_poste_proche": 0.88,
        "roles": roles,
        "formations": FORMATIONS,
        "tactiques": TACTIQUES,
        "incoherences": INCOHERENCES,
        "niveaux_division": NIVEAUX,
        "entrainement": ENTRAINEMENT,
    }
    out = Path(__file__).resolve().parent.parent / "fm_assistant" / "data" / "connaissances.json"
    out.write_text(json.dumps(kb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out, len(roles), "rôles,", len(attrs), "attributs")


if __name__ == "__main__":
    main()
