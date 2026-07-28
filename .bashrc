# ============================================================
# Lagrange Tactical AI — Bash Configuration
# Project-specific shell aliases, functions, and environment
# Source this file: source .bashrc
# ============================================================

# ---- Lagrange project path ----
export LAGRANGE_HOME="$HOME/Desktop/拉格朗日智能体"
export LAGRANGE_API="http://127.0.0.1:3000"
export LAGRANGE_DATA="$LAGRANGE_HOME/data"

# ---- Service management functions ----
lagrange_start() {
    cd "$LAGRANGE_HOME" || return
    echo "[Lagrange] Starting server..."
    python main.py &
    sleep 2
    curl -s "$LAGRANGE_API/health" && echo "" || echo "[Lagrange] Failed to start"
}

lagrange_stop() {
    echo "[Lagrange] Stopping server..."
    taskkill //F //IM python.exe 2>/dev/null
    echo "[Lagrange] Server stopped"
}

lagrange_status() {
    if curl -s "$LAGRANGE_API/health" > /dev/null 2>&1; then
        echo "Lagrange AI running at $LAGRANGE_API"
        echo "Ships: $(curl -s "$LAGRANGE_API/api/ships?limit=1" | python -c "import sys,json; print(json.load(sys.stdin).get('total',0))") loaded"
    else
        echo "Lagrange AI not running"
    fi
}

lagrange_backup() {
    cd "$LAGRANGE_HOME" && python -c "from database import backup_database; print(backup_database())"
}

lagrange_rebuild() {
    echo "[Lagrange] Rebuilding vector index..."
    curl -s -X POST "$LAGRANGE_API/api/rebuild-index" || python -c "from rag_service import build_vector_index; build_vector_index()"
}

lagrange_test() {
    cd "$LAGRANGE_HOME" && python test_api.py
}

lagrange_dev() {
    cd "$LAGRANGE_HOME" && uvicorn main:app --host 0.0.0.0 --port 3000 --reload
}

lagrange_logs() {
    tail -f "$LAGRANGE_HOME/logs/server.log" 2>/dev/null || echo "No logs found"
}

lagrange_clean() {
    cd "$LAGRANGE_HOME" || return
    rm -rf __pycache__ *.pyc chroma_db/faiss_index.bin 2>/dev/null
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    echo "[Lagrange] Cache cleaned"
}

# ---- Short aliases ----
alias lg='cd "$LAGRANGE_HOME"'
alias lg-start='lagrange_start'
alias lg-stop='lagrange_stop'
alias lg-status='lagrange_status'
alias lg-backup='lagrange_backup'
alias lg-rebuild='lagrange_rebuild'
alias lg-test='lagrange_test'
alias lg-dev='lagrange_dev'
alias lg-logs='lagrange_logs'
alias lg-clean='lagrange_clean'
alias lg-export='cd "$LAGRANGE_HOME" && python export_ships.py all'
alias lg-ships='cd "$LAGRANGE_HOME" && node parse_ships.js'
alias lg-docker-dev='cd "$LAGRANGE_HOME" && docker compose -f docker-compose.override.yml up -d'
alias lg-docker-down='cd "$LAGRANGE_HOME" && docker compose -f docker-compose.override.yml down'
alias lg-k8s-apply='kubectl apply -f "$LAGRANGE_HOME/k8s/"'
alias lg-k8s-status='kubectl get all -n lagrange'

# ---- Python environment ----
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1
export PIP_REQUIRE_VIRTUALENV=false

# ---- PATH additions ----
export PATH="$LAGRANGE_HOME/scripts:$LAGRANGE_HOME/node_modules/.bin:$PATH"
