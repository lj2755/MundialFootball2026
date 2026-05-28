"""
Entry point único — levanta el webhook server y el pipeline en background,
luego lanza el dashboard de Streamlit.

Uso:
    python run.py                  # lanza todo
    python run.py --pipeline-only  # solo el pipeline (sin dashboard)
    python run.py --dashboard-only # solo el dashboard (sin pipeline)
"""
import sys
import asyncio
import subprocess
import threading
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def start_pipeline():
    """Runs the async pipeline loop in a separate thread."""
    from processing_layer.pipeline import run_continuous
    asyncio.run(run_continuous())


def start_webhook_server_bg():
    from execution_layer.webhook_server import start_webhook_server
    from config.settings import WEBHOOK_PORT
    start_webhook_server(WEBHOOK_PORT)
    logger.info(f"Webhook server started on port {WEBHOOK_PORT}")


def start_dashboard():
    import os
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard", "app.py")
    subprocess.run(["streamlit", "run", dashboard_path, "--server.port=8501", "--server.headless=false"])


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("all", "--pipeline-only"):
        # Start webhook server
        wh_thread = threading.Thread(target=start_webhook_server_bg, daemon=True)
        wh_thread.start()
        time.sleep(0.5)  # give it time to bind port

        # Start pipeline in background thread
        pipeline_thread = threading.Thread(target=start_pipeline, daemon=True)
        pipeline_thread.start()
        logger.info("Pipeline started in background.")

    if mode in ("all", "--dashboard-only"):
        logger.info("Launching Streamlit dashboard...")
        start_dashboard()
    elif mode == "--pipeline-only":
        logger.info("Running pipeline only — press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Pipeline stopped.")
