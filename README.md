# FM Assistant 27

Compagnon de bureau **100 % local et gratuit** pour Football Manager 27. Il lit votre carrière **en direct, à l'écran**, pendant que vous jouez — sans export, sans clé API, sans Internet — puis analyse votre effectif, votre tactique, vos contrats et vos cibles de recrutement, en expliquant chaque conseil en français.

> **Votre sauvegarde n'est jamais touchée.** L'assistant photographie la fenêtre du jeu et lit le texte qui s'y trouve. Il n'envoie rien au jeu, sauf si vous lancez le **scan automatique**, qui navigue alors dans les écrans à votre place (touches de navigation, clics sur les noms, molette).

---

## 1. Ce que fait l'application

| Module | Contenu |
|---|---|
| **Lecture en direct** | Détection de la fenêtre FM, capture seulement quand l'image change, reconnaissance de 9 écrans (effectif, profil, tactique, recherche, shortlist, finances, classement, calendrier, staff), scan guidé, calibrage avec aperçu de ce qui a été lu |
| **Tableau de bord** | Niveau du onze type face à la division, masse salariale, âge moyen, contrats qui expirent, objectif, alertes |
| **Effectif** | Notes par rôle, profondeur par poste, forces/faiblesses, radars, comparateur (jusqu'à 4 joueurs) |
| **Assistant tactique** | Meilleur XI (affectation optimale), doublures, 3 tactiques adaptées à l'effectif, incohérences de votre tactique, conseils avant match |
| **Recrutement** | Recherche ciblée (poste, rôle, âge, budget, salaire, niveau), rapport qualité/prix, pépites, shortlist annotée, besoins de l'effectif |
| **Jeunes** | Plan de progression par joueur, décision prêt / rotation / intégration |
| **Contrats & finances** | Échéances, joueurs à prolonger ou à vendre, budgets, évolution |
| **Idées de carrière** | 30 défis filtrables, bouton « Surprends-moi » |
| **Chat local** | Apparaît seulement si Ollama est installé |
| **Overlay** | Petite fenêtre de conseils par-dessus le jeu |

Quand une donnée n'a pas été lue, l'application **le dit** (« attributs non lus », « classement non lu ») au lieu d'inventer une valeur.

---

## 2. Installation pas à pas (Windows 10 / 11)

### Étape 1 — Installer Python
1. Allez sur <https://www.python.org/downloads/windows/> et téléchargez **Python 3.12** (« Windows installer 64-bit »).
2. Lancez l'installateur et **cochez « Add python.exe to PATH »** en bas de la première fenêtre, puis « Install Now ».

### Étape 2 — Récupérer l'application
Sur la page GitHub du projet : bouton vert **Code → Download ZIP**, puis décompressez le dossier où vous voulez (par exemple `Documents\FMAssistant27`).

### Étape 3 — Installer les dépendances
Double-cliquez sur **`installer.bat`**. Une fenêtre noire télécharge les composants (environ 300 Mo, quelques minutes). C'est la seule étape qui demande Internet. Attendez le message « Installation terminée ».

### Étape 4 — Lancer
- **`lancer.bat`** : démarre l'application.
- **`lancer_demo.bat`** : démarre avec une carrière fictive, pour découvrir l'interface sans le jeu.

### Étape 5 — Premier lancement et calibrage
1. Lancez FM 27 en mode **fenêtré** ou **fenêtré sans bordure** et chargez votre partie.
2. Dans l'assistant, page **Lecture en direct**, cliquez **Démarrer le scan guidé**.
3. Revenez dans FM et ouvrez les écrans demandés. Chaque écran lu se coche tout seul :
   - **Effectif** : choisissez une vue qui montre *Nom, Poste, Âge, Valeur, Salaire, Contrat* et faites défiler jusqu'en bas ;
   - **Profils** : ouvrez la page des attributs de chaque joueur (une seconde par profil suffit) ;
   - **Tactique**, **Finances**, **Classement**, **Calendrier** ; Staff et Recherche de joueurs sont facultatifs.
4. Retournez sur **Lecture en direct → Calibrage — ce que j'ai lu**. Vous y voyez la capture avec les textes reconnus encadrés. Si quelque chose cloche :
   - *écran mal reconnu* → choisissez son type puis cliquez le texte qui l'identifie ;
   - *colonne ignorée* → associez l'en-tête au bon champ ;
   - *nom mal lu* → cliquez dessus et corrigez ;
   - *petits textes illisibles* → augmentez « Agrandissement avant lecture ».

   Chaque correction est mémorisée et appliquée aux lectures suivantes.
5. Dans **Réglages**, renseignez votre **club** (nom exact du jeu), votre **division**, la saison et le style de jeu voulu.

Ensuite, il n'y a plus rien à faire : jouez, l'assistant met la base à jour à chaque écran que vous ouvrez. L'indicateur en bas à gauche affiche par exemple « FM 27 détecté ✓ – dernier écran lu : Effectif – 32 joueurs à jour ».

### Scan automatique (sans ouvrir les écrans vous-même)
Page **Lecture en direct → Scan automatique**. L'assistant fait défiler l'effectif, ouvre chaque profil, puis visite tactique, finances, classement et calendrier.

1. Dépliez **Raccourcis du jeu** et saisissez ceux de FM 27 (dans le jeu : Préférences → Raccourcis). Le plus utile est **Joueur suivant** ; à défaut, **Retour**. Le bouton **Tester** envoie le raccourci une fois pour vérifier.
2. Ouvrez l'écran Effectif dans FM, puis cliquez **Lancer le scan automatique** et ne touchez plus à rien.
3. Pour arrêter : bouton **Arrêter**, ou cliquez dans une autre fenêtre (le scan s'interrompt dès que FM n'est plus au premier plan).

Un écran sans raccourci n'est pas bloquant : l'assistant vous demande de l'ouvrir et reprend dès qu'il le voit. Seules des touches de navigation, des clics sur les noms de joueurs et la molette sont envoyés au jeu ; la sauvegarde n'est jamais lue ni modifiée.

### Étape 6 (facultative) — Créer le .exe
Double-cliquez sur **`creer_exe.bat`**. Le résultat est dans `dist\FM Assistant 27\` : lancez `FM Assistant 27.exe` (gardez tout le dossier, il contient les composants).

### Étape 7 (facultative) — Chat avec Ollama
1. Installez Ollama depuis <https://ollama.com/download>.
2. Ouvrez l'Invite de commandes et tapez `ollama pull llama3.2` (ou un autre modèle).
3. Relancez l'assistant : l'entrée **Chat local** apparaît dans le menu. Sans Ollama, elle reste masquée.

---

## 3. Conseils pour une bonne lecture

- Gardez FM **au premier plan** : la lecture se suspend quand une autre fenêtre le recouvre.
- Les attributs ne sont lus que sur le **profil du joueur**. Tant qu'un profil n'a pas été ouvert, le joueur est marqué « attributs non lus » et sa note est au mieux *estimée d'après ses étoiles* (affichée en pointillé).
- Les listes ne contiennent que les **lignes visibles** : faites défiler pour tout lire.
- Si la fenêtre du jeu ne s'appelle pas « Football Manager… », modifiez le titre recherché dans **Réglages**.
- Si une liste lue n'était pas votre équipe (effectif adverse), utilisez **Journal des lectures → Reclasser**.

---

## 4. Personnaliser l'analyse

**Réglages → Ouvrir le dossier de données** donne accès à trois fichiers modifiables avec le Bloc-notes :

| Fichier | Contenu |
|---|---|
| `connaissances.json` | 45 rôles (attributs clés/secondaires, poids), 8 formations, 6 styles tactiques, règles d'incohérence, repères de niveau par division, conseils d'entraînement |
| `ecrans.json` | Mots-clés des écrans, noms de colonnes, consignes d'équipe reconnues, étapes du scan guidé |
| `defis.json` | Bibliothèque d'idées de carrière |

Après modification : **Réglages → Recharger après modification**. Si un fichier contient une erreur, l'application le signale et utilise la version d'origine.

Calcul d'une note : moyenne des attributs du rôle pondérée par leur poids (clé = 3, secondaire = 1,5 par défaut, surcharge possible par rôle via `"poids"`).

---

## 5. Limites connues (à lire)

- **L'interface réelle de FM 27 n'a pas pu être testée** pendant le développement. La lecture repose sur l'alignement des textes et non sur des positions fixes, et elle est validée par des tests automatiques sur des captures synthétiques en 1366×768, 1920×1080 et 2560×1440. Sur le vrai jeu, attendez-vous à passer quelques minutes dans le calibrage (mots-clés d'écran, colonnes).
- **Les noms de rôles** de la base sont les rôles classiques de la série en français. Si FM 27 en renomme certains, ajustez `connaissances.json` : un rôle inconnu n'est simplement pas reconnu sur l'écran Tactique.
- **Barres d'attributs** : lecture approximative (±1), uniquement si la barre a un rail visible. **Étoiles** : seules les étoiles dorées sont comptées.
- **Blessures** : lues uniquement si le jeu les écrit en texte dans une colonne.
- **Repères de niveau par division** : estimations modifiables, pas des données du jeu.
- **Scan automatique** : sa logique est testée contre un jeu simulé, mais l'envoi réel de touches à FM n'a pas pu être essayé, et les raccourcis de FM 27 sont à saisir par vous. Le fichier de sauvegarde lui-même n'est pas lu : son format est propriétaire et non documenté.
- **OCR Windows de secours, overlay et création du .exe** : écrits mais non exécutés ici (développement hors Windows). L'OCR principal (RapidOCR) est, lui, testé.

---

## 6. Dépannage

| Problème | Solution |
|---|---|
| « Python est introuvable » | Réinstallez Python en cochant *Add python.exe to PATH* |
| Fenêtre blanche au lancement | Installez « Microsoft Edge WebView2 Runtime », ou lancez `lancer.bat --navigateur` |
| « FM 27 non détecté » | Jeu lancé ? Titre de fenêtre correct dans Réglages ? |
| Rien n'est lu en plein écran exclusif | Passez le jeu en fenêtré sans bordure |
| « Moteur OCR indisponible » | Relancez `installer.bat` ; en secours : `pip install -r requirements-ocr-windows.txt` |
| Repartir de zéro | Réglages → Tout effacer |

Vos données sont dans `%LOCALAPPDATA%\FMAssistant27` (base `carriere.sqlite`, `calibrage.json`, fichiers JSON).

---

## 7. Architecture

```
lancer.py                  point d'entrée
fm_assistant/
  main.py                  serveur local + fenêtre pywebview + overlay
  api.py                   routes FastAPI
  config.py  db.py         dossiers et réglages · SQLite (fusion sans doublons, historique par date de jeu)
  textutil.py              montants, dates, postes FR/EN, chiffres tolérants à l'OCR
  demo.py  chat.py         données de démonstration · Ollama
  capture/
    window.py              détection de la fenêtre, capture mss, empreinte d'image
    ocr.py                 RapidOCR, OCR Windows en secours
    layout.py              lignes, cellules et colonnes à partir des mots
    screens.py             reconnaissance du type d'écran
    visual.py              étoiles et barres d'attributs
    parsers.py             un parseur par écran
    calibration.py         corrections apprises
    ingest.py  watcher.py  enregistrement en base · boucle d'arrière-plan
    autopilot.py inputs.py scan automatique · envoi de touches et de clics
  analysis/
    knowledge.py ratings.py squad.py tactics.py
    recruitment.py development.py contracts.py dashboard.py
  data/                    connaissances.json · ecrans.json · defis.json
  web/                     interface (HTML/CSS/JS sans dépendance externe)
tests/                     34 tests, dont la chaîne OCR complète et le scan automatique (jeu simulé)
tools/build_knowledge.py   régénère connaissances.json
```

Développeurs : `pip install -r requirements-dev.txt` puis `python -m pytest`. Options : `--demo`, `--navigateur`, `--port`, `--sans-capture`.
