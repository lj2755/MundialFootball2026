# Entry point para Streamlit Cloud — redirige al dashboard real.
# Streamlit Cloud busca app.py en la raíz del repo.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard.app import *  # noqa: F401, F403
