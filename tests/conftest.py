import os
import sys
import tempfile
from pathlib import Path

# Chaque session de tests travaille dans un dossier de données jetable
os.environ["FMA_DATA_DIR"] = tempfile.mkdtemp(prefix="fma-tests-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
