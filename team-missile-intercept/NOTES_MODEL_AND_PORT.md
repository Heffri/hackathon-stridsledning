# Missile Mesh + Windows Port Notes

## 1. Missile Mesh Polish

All changes in `frontend/js/entities.js`.

### 1.1 Interceptor (IRIS-T style, shared base for SLS)
The old "cylinder + cone + 4 small fins" was bumped to:
- **Truncated-cone nose** (CylinderGeometry with a small top radius) so the seeker dome has a flat pad to sit on.
- **IR seeker** — dark half-sphere embedded in the nose cap.
- **Two accent bands** around the body (team-colour, darkened).
- **4 mid-body canards** — new forward control surfaces.
- **4 large tail fins** — replaces the old undersized pair.

### 1.2 Hypersonic glide vehicle (HGV, DF-ZF / HTV-2 style)
- Detached nose cone removed — the body **tapers to the nose point itself**, more dart-like.
- Body lengthened: 2.8 → 5.5, radius 0.6 → 0.5.
- **Diamond cross-section** — the old code had `rotation.y = π/4` trying to produce a diamond, but `ConeGeometry(...,4)` already puts base vertices on the ±X and ±Z axes (diamond is the default). The 45° rotation actually rotated the vertices onto the diagonals, turning the cross-section into a rectangle. Deleting that rotation is the fix.
- Added **dorsal vertical fin** (top-rear) + **two horizontal side fins** (rear).

### 1.3 Ballistic tail fin fix
The Box dimensions had **radial span and tangential thickness swapped** (X = 0.08 thin, Z = 0.45 wide). The 4 fins therefore wrapped around the body into a square sleeve instead of sticking out as a cross. Swapped X and Z, moved each fin outward so its inner edge sits on the body surface — now a normal cruciform tail.

### 1.4 Drone propeller fix
The old code had `prop.rotation.x = Math.PI / 2`, which tipped the cylinder from "along the flight axis (+Y)" to horizontal (disc facing sky instead of rearward). Deleting that rotation makes the default orientation correct.

### 1.5 Shared conventions (applies to every "4 fins around the body" mesh)
3D orientation: long axis = +Y (nose forward). For 4 fins arranged around the body:
- Position: `(cos(a)·r, y, sin(a)·r)` + `rotation.y = -a`.
- In the Box's local coords: **X = radial extent** (outward-pointing width), **Y = chord along the body**, **Z = tangential thickness** (thin).
- Writing X and Z backwards produces a square sleeve instead of a cross.

---

## 2. Port Conflict on Windows

### Symptom
`python server.py` fails to bind `0.0.0.0:8000`:
```
[Errno 13] error while attempting to bind on address ('0.0.0.0', 8000):
an attempt was made to access a socket in a way forbidden by its access permissions
```
`127.0.0.1:8080` fails the same way. `8088` also fails. `5174` binds successfully.

### Cause
Windows — especially with Hyper-V, WSL2, or Docker Desktop installed — **reserves large TCP port ranges** for its own use. User applications can't bind inside those ranges. Inspect them with:
```cmd
netsh interface ipv4 show excludedportrange protocol=tcp
```
Commonly reserved ranges include blocks around 8000, 8080, 50000, and many others.

### Current default
`backend/server.py` defaults to port **5174**. It binds on both hackathon laptops. Override with the `PORT` env var:
```bash
PORT=6969 python server.py                 # bash / Git Bash
```
```cmd
set PORT=6969 && python server.py          # Windows cmd
```

If 5174 is also reserved on a future machine, the recipe is: run the `netsh` command above, pick a port that doesn't fall inside any excluded range (uncommon numbers like 6969 / 7331 / 9123 / 12345 usually work), then either set `PORT=…` or edit the default in `server.py`.

---

## 3. Other Windows gotchas (for the next person picking this up)

1. **`python` command not found / silently exits with code 49** — default matches the Microsoft Store placeholder stub. Fix: turn off "App execution aliases" for `python.exe` / `python3.exe` in Windows settings, then add the real Python install directory to PATH.
2. **`setx PATH ...` truncates to 1024 characters.** If the system PATH is already long, edit the user PATH instead from PowerShell:
   ```powershell
   [Environment]::SetEnvironmentVariable(
     "PATH",
     [Environment]::GetEnvironmentVariable("PATH", "User") + ";<new directory>",
     "User"
   )
   ```
3. **`pip` isn't on PATH inside Git Bash** even when Python is. Use `python -m pip` from bash, or run pip from cmd / PowerShell.
