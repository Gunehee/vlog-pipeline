import React from "react";

const GROUPS = [
  ["Playback", [
    ["space", "play / pause"],
    ["e", "toggle preview edited ↔ play original"],
    ["← →", "seek 1s (shift: 5s, alt when nothing selected: 0.1s)"],
  ]],
  ["Cuts", [
    ["n / p", "select next / previous cut"],
    ["x", "toggle selected cut (remove ↔ keep)"],
    ["alt+← / alt+→", "nudge selected cut IN edge by 50ms"],
    ["alt+shift+← / →", "nudge selected cut OUT edge by 50ms"],
    ["c", "add-cut mode — drag a range on the timeline"],
    ["double-click a cut", "toggle it directly on the timeline"],
    ["esc", "deselect / exit add-cut mode / close dialogs"],
  ]],
  ["Timeline", [
    ["scroll", "zoom around cursor"],
    ["shift+scroll / trackpad ↔", "pan"],
    ["click", "seek (edited preview lands outside cuts)"],
    ["drag accent handles", "adjust selected cut boundaries"],
  ]],
  ["Everything else", [
    ["⌘z / ⌘⇧z", "undo / redo any decision edit"],
    ["?", "this overlay"],
  ]],
];

export default function ShortcutOverlay({ onClose }) {
  return (
    <div className="modal-scrim" onClick={onClose} data-testid="shortcut-overlay">
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Keyboard shortcuts</h2>
        {GROUPS.map(([title, rows]) => (
          <div key={title} style={{ marginBottom: "var(--sp-4)" }}>
            <div className="muted" style={{ fontSize: "var(--fs-xs)", textTransform: "uppercase",
                                            letterSpacing: ".05em", marginBottom: "var(--sp-2)" }}>
              {title}
            </div>
            <div className="shortcuts-grid">
              {rows.map(([keys, desc]) => (
                <React.Fragment key={keys}>
                  <span><kbd>{keys}</kbd></span>
                  <span className="desc">{desc}</span>
                </React.Fragment>
              ))}
            </div>
          </div>
        ))}
        <div className="actions">
          <button className="btn" onClick={onClose}>close <kbd>esc</kbd></button>
        </div>
      </div>
    </div>
  );
}
