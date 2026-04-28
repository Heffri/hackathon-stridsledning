// Launcher selection state — M-TIER2-J Part 2 (Issue #6).
//
// Tracks which launcher (if any) the operator has clicked on during
// SETUP. Shared between the click-to-select handler (drag_launchers.js)
// and the ribbon Remove button (hud.js).
//
// Pure frontend state — not broadcast over WS. On snapshot the server
// is the source of truth for the roster; when the selected id
// disappears from a snapshot (e.g. the operator hit Remove and the
// server confirmed the removal) we auto-deselect to keep the button
// state honest.

let _selectedId = null;
const _listeners = new Set();

export function getSelectedLauncherId() {
  return _selectedId;
}

export function setSelectedLauncherId(id) {
  if (_selectedId === id) return;
  _selectedId = id;
  for (const cb of _listeners) {
    try { cb(_selectedId); } catch (e) { console.warn('selection listener', e); }
  }
}

export function onSelectionChange(cb) {
  _listeners.add(cb);
  return () => _listeners.delete(cb);
}
