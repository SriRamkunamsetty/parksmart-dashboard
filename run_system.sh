#!/bin/bash
# run_system.sh
# Automates the startup of the Smart Parking AI system on Linux

echo -e "\e[36m--- Automated Smart Parking AI Startup (Linux) ---\e[0m"

BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:5173"

# 0. Stop existing services
echo -e "\e[33mCleaning up existing services...\e[0m"
pkill uvicorn 2>/dev/null
pkill node 2>/dev/null

# 1. Project Root Check
ROOT_DIR=$(pwd)
echo "Project Root: $ROOT_DIR"

# 2. Setup Python environment
echo -e "\n\e[32m[SECTION 3] Setting up Python Environment...\e[0m"
if [ ! -d "backend/venv" ]; then
    echo "Creating Virtual Environment..."
    python3 -m venv backend/venv
fi

source backend/venv/bin/activate
echo "Installing dependencies..."
pip install -r backend/requirements.txt --quiet
pip install requests --quiet

# 3. Initialize Database
echo -e "\n\e[32m[SECTION 1] Initializing Database and Seeding...\e[0m"
python3 backend/init_db_and_seed.py

# 4. Start Backend API
echo -e "\n\e[32m[SECTION 3] Starting Backend API...\e[0m"
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# 5. Wait for Backend readiness
echo -e "\e[33mWaiting for backend health check (max 60 attempts)...\e[0m"
timeout=60
count=0
while [ $count -lt $timeout ]; do
    if curl -s "http://localhost:8000/api/system/health" | grep -q "\"status\":\"UP\""; then
        echo -e "\e[32mBackend is UP!\e[0m"
        break
    fi
    sleep 2
    count=$((count+1))
done
if [ $count -ge $timeout ]; then echo -e "\e[31mTimeout!\e[0m"; kill $BACKEND_PID; exit 1; fi

# 6. Start Frontend
echo -e "\n\e[32m[SECTION 3] Starting Frontend...\e[0m"
if [ ! -d "node_modules" ]; then echo "Installing dependencies..."; npm install --silent; fi
npm run dev &
FRONTEND_PID=$!

# 7. Wait for Frontend readiness
echo -e "\e[33mWaiting for frontend server...\e[0m"
count=0
while true; do
    if nc -z localhost 5173 2>/dev/null; then
        echo -e "\e[32mFrontend is UP!\e[0m"
        break
    fi
    if [ $count -ge $timeout ]; then break; fi
    sleep 2
    count=$((count+2))
done

# 8. Trigger AI worker
echo -e "\n\e[32m[SECTION 3] Triggering AI worker demo...\e[0m"
curl -s -X POST "http://localhost:8000/api/jobs/start-demo" \
     -H "Content-Type: application/json" \
     -d '{"video":"parking_video.mp4"}'

# 9. Start Worker Watchdog (Optional)
echo -e "\n\e[32m[SECTION 5] Starting Worker Watchdog...\e[0m"
python3 worker_watchdog.py &
WATCHDOG_PID=$!

# 10. Open Admin Dashboard
echo -e "\n\e[36m[SYSTEM READY] Launching Dashboard...\e[0m"
if command -v xdg-open > /dev/null; then xdg-open "http://localhost:5173/admin"
elif command -v open > /dev/null; then open "http://localhost:5173/admin"
else echo "Please open http://localhost:5173/admin in your browser."
fi

echo -e "\nAutomation complete. Services running (PIDs: $BACKEND_PID, $FRONTEND_PID, $WATCHDOG_PID)."
wait
