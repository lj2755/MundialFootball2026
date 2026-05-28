VS Code debería estar abriendo. Aquí está lo que tienes configurado:

---

## .vscode — Lo que hace cada archivo

**`settings.json`**
- Apunta el intérprete a `.venv/Scripts/python.exe` (el venv local)
- `PYTHONPATH` apunta a la raíz del proyecto — los imports `from data_layer import ...` funcionan sin `sys.path` hacks
- Lee `.env` automáticamente para variables de entorno
- Pytest configurado apuntando a `tests/`
- File nesting: `.env.example` agrupa `.env` y `.gitignore` en el Explorer

**`launch.json`** — 6 configuraciones en el panel Run & Debug (`Ctrl+Shift+D`):
| Nombre | Qué hace |
|---|---|
| 🚀 Lanzar Todo | `python run.py` — todo junto |
| 📊 Solo Dashboard | Streamlit en puerto 8501 |
| ⚙️ Solo Pipeline | fetch + análisis, sin UI |
| 🌐 Webhook Server | servidor interno aislado |
| 🧪 Tests | pytest con output verbose |
| 🔍 Debug Pipeline | un ciclo solo, para debuggear |
| 🏟️ Full Stack (compound) | los tres procesos en paralelo |

**`tasks.json`** — accesibles con `Ctrl+Shift+P → Run Task`:
- **Setup completo** (default build): crea venv + instala deps + copia `.env.example` → `.env`
- **Ejecutar tests** (default test)
- **Verificar conexión Polygon**: one-liner que confirma que el RPC responde
- **Limpiar __pycache__**, **Ver .env actual**

**`extensions.json`** — VS Code te pedirá instalar las recomendadas al abrir el workspace.

---

## Primer arranque

```
Ctrl+Shift+P → "Run Task" → ⚙️ Setup completo
```
Esto crea el venv, instala todo, y genera el `.env`. Luego editas el `.env` con tus keys y ya puedes usar `F5` con cualquier configuración.