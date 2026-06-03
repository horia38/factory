@echo off
echo Starting Pharmaceutical Factory Simulation...

:: Use the Python executable from the local virtual environment
set PYTHON_EXE=.venv\Scripts\python.exe

:: Check if the virtual environment exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Virtual environment not found at .venv\Scripts\python.exe
    echo Please make sure the .venv exists in this folder.
    pause
    exit /b 1
)

:: Start all processes in separate terminal windows
start "Machine 1 - Dispenser" cmd /k "%PYTHON_EXE% machine1_dispenser.py"
start "Machine 2 - Granulator" cmd /k "%PYTHON_EXE% machine2_granulator.py"
start "Machine 3 - Dryer" cmd /k "%PYTHON_EXE% machine3_dryer.py"
start "Machine 4 - Press" cmd /k "%PYTHON_EXE% machine4_press.py"
start "Machine 5 - QC Coater" cmd /k "%PYTHON_EXE% machine5_qc.py"
start "Master AI Agent" cmd /k "%PYTHON_EXE% master_agent.py"
start "WebSocket MQTT Bridge" cmd /k "%PYTHON_EXE% mqtt_bridge.py"

echo All factory processes have been successfully launched!
echo You can now run 'npm run dev' inside the dashboard folder if it's not already running.
