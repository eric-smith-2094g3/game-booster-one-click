import argparse
import ctypes
import subprocess
import sys
import time
import re
from pathlib import Path
import psutil

# Heavy Windows services we want to pause while gaming
SERVICES_TO_STOP = [
    "SysMain",    # Superfetch / Prefetch
    "WSearch",    # Windows Search Indexer
    "wuauserv",   # Windows Update (prevents background installations)
]

# Known resource hogs we can safely suspend and resume without losing data
APPS_TO_SUSPEND = [
    "OneDrive.exe",
    "Teams.exe",
    "Discord.exe",
    "chrome.exe",
    "msedge.exe",
    "Spotify.exe"
]

HIGH_PERF_GUID = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return False

def stop_services():
    stopped = []
    for service in SERVICES_TO_STOP:
        # Check query output to see if it is currently running or stopping
        query = subprocess.run(["sc", "query", service], capture_output=True, text=True)
        if "RUNNING" in query.stdout or "START_PENDING" in query.stdout:
            print(f"Stopping service: {service}")
            res = subprocess.run(["sc", "stop", service], capture_output=True, text=True)
            if res.returncode == 0:
                stopped.append(service)
                time.sleep(1.0)
    return stopped

def start_services(services):
    for service in reversed(services):
        print(f"Restoring service: {service}")
        subprocess.run(["sc", "start", service], capture_output=True)

def suspendBackgroundApps():
    """Suspends known browser and chat tasks to free up physical cores."""
    suspended_pids = []
    current_pid = psutil.Process().pid
    
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["pid"] == current_pid:
                continue
            if proc.info["name"] and proc.info["name"].lower() in [a.lower() for a in APPS_TO_SUSPEND]:
                p = psutil.Process(proc.info["pid"])
                # Avoid suspending processes that are already suspended
                if p.status() != psutil.STATUS_STOPPED:
                    print(f"Suspending background app: {proc.info['name']} (PID {proc.info['pid']})")
                    p.suspend()
                    suspended_pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return suspended_pids

def resume_apps(pids):
    for pid in pids:
        try:
            p = psutil.Process(pid)
            print(f"Resuming background app: {p.name()} (PID {pid})")
            p.resume()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

def get_active_power_scheme():
    res = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True)
    # Regex looks for the hex pattern of a standard GUID to avoid localized string parsing bugs
    match = re.search(r"([a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})", res.stdout)
    if match:
        # print(f"DEBUG: active power scheme GUID is {match.group(1)}")
        return match.group(1)
    return None

def run_booster(game_path, game_args):
    """The main coordinator. This has to handle the process lifecycle tightly."""
    # TODO: some store apps like XboxAppServices can't be stopped easily, need to check if we should skip them
    stopped_services = []
    suspended_pids = []
    original_power = get_active_power_scheme()
    
    try:
        stopped_services = stop_services()
        suspended_pids = suspendBackgroundApps()
        
        if original_power:
            print(f"Switching power plan to High Performance...")
            subprocess.run(["powercfg", "/setactive", HIGH_PERF_GUID], capture_output=True)

        executable_path = Path(game_path)
        if not executable_path.exists():
            print(f"Error: Game executable not found at {game_path}", file=sys.stderr)
            sys.exit(1)

        print(f"Starting game: {executable_path.name}...")
        cmd = [str(executable_path)]
        if game_args:
            cmd.extend(game_args)
            
        # Launch the game detached so we can immediately capture its process handle
        proc = subprocess.Popen(cmd, cwd=str(executable_path.parent))
        
        # Wait briefly for process setup, then boost priority class
        time.sleep(1.5)
        try:
            game_proc = psutil.Process(proc.pid)
            print(f"Setting game process priority to HIGH...")
            game_proc.nice(psutil.HIGH_PRIORITY_CLASS)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # The process might have spawned a child and exited immediately (e.g. launchers)
            print("Warning: Could not boost priority. The game might have spawned a secondary process.")

        print("Game is running. Booster is waiting for exit...")
        proc.wait()
        print("Game process exited.")

    except KeyboardInterrupt:
        print("\nBoost interrupted by user keyboard input. Restoring state...")
    finally:
        print("Restoring system state...")
        if original_power:
            print(f"Restoring power plan...")
            subprocess.run(["powercfg", "/setactive", original_power], capture_output=True)
        resume_apps(suspended_pids)
        start_services(stopped_services)
        print("System state successfully restored. Farewell!")

def main():
    if not is_admin():
        print("Error: This tool requires Administrator privileges to modify Windows services and power plans.", file=sys.stderr)
        print("Please restart your command prompt or terminal as Administrator.", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Windows game booster to free up CPU and RAM. Disables services, suspends background apps, and boosts priority.",
        epilog="Example: python -m game_booster.booster \"C:\\Games\\MyGame.exe\" -- --fullscreen"
    )
    parser.add_argument("game_path", help="Absolute path to the game executable")
    parser.add_argument("game_arguments", nargs=argparse.REMAINDER, help="Arguments to forward to the game (use -- to separate)")
    args = parser.parse_args()

    # Clean up remainder arguments if they start with a double dash separator
    raw_args = args.game_arguments
    if raw_args and raw_args[0] == '--':
        raw_args = raw_args[1:]

    run_booster(args.game_path, raw_args)

if __name__ == "__main__":
    main()
