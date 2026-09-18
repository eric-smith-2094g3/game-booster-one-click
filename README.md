# game-booster-one-click

A minimal CLI tool to optimize Windows performance before launching a game, and restore everything when you exit.

I built this to stop Windows background services and hoggy processes from causing micro-stutters while gaming, without having to manually toggle things in Task Manager or Services.msc every time. It operates as a wrapper: it prepares your system, launches the game, waits for it to close, and then puts everything back exactly how it was.

## How it works

1. Verifies administrative privileges (needed to control Windows services).
2. Queries and stores your current active Windows power plan, then sets it to High Performance.
3. Stops a hardcoded list of non-essential services (like SysMain, Print Spooler, Windows Search).
4. Suspends active background processes that eat CPU and RAM (such as browser helper processes and chat apps).
5. Launches the game and bumps its process priority to High.
6. Waits for the game to exit, then restores all stopped services, resumes suspended processes, and reverts the power plan.

## Installation

Clone the repository and install the only dependency:

```cmd
pip install -r requirements.txt
```

## Usage

You must run the script from an elevated terminal (Run as Administrator).

```cmd
python booster.py "C:\Program Files (x86)\Steam\steamapps\common\Half-Life 2\hl2.exe"
```

If your game needs specific launch arguments, pass them after the path:

```cmd
python booster.py "C:\Games\Doom\Doom.exe" --args "+com_skipIntroVideo 1"
```

To customize which services are stopped or which processes are suspended, open `booster.py` and tweak the lists at the top of the file. I avoided a external configuration file to keep this completely self-contained.

<!-- last-checked: 2026-09-18 -->
