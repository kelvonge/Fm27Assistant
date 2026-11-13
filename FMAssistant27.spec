# -*- mode: python ; coding: utf-8 -*-
# Recette PyInstaller : produit dist/FM Assistant 27/FM Assistant 27.exe (dossier autonome).
#   pyinstaller --noconfirm --clean FMAssistant27.spec
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("fm_assistant/data", "fm_assistant/data"), ("fm_assistant/web", "fm_assistant/web")]
binaries = []
hiddenimports = collect_submodules("uvicorn") + ["mss", "mss.windows"]
for pkg in ("rapidocr", "onnxruntime", "webview"):  # modèles OCR, bibliothèques natives, moteur de fenêtre
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(["lancer.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             excludes=["tkinter", "matplotlib", "pytest"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FM Assistant 27", console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="FM Assistant 27", upx=False)
