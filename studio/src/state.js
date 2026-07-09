// Studio state: the review overlay is the single mutable document; everything
// else derives from it. Undo/redo snapshots the overlay (it's small).
import { deriveCuts, keptSegments, predictedDuration } from "./util.js";

const UNDO_CAP = 200;

export function initialState() {
  return {
    run: null, // server payload (engine data, immutable here)
    review: null, // the overlay document
    cuts: [], // derived view
    kept: [],
    predicted: 0,
    selection: null,
    dirty: false,
    saveState: "clean", // clean | dirty | saving | saved | error
    undo: [],
    redo: [],
  };
}

function derive(state) {
  const total = state.run.duration;
  const cuts = deriveCuts(state.run.cutlist, state.review);
  const kept = keptSegments(cuts, total);
  return { ...state, cuts, kept, predicted: predictedDuration(cuts, total) };
}

// caption lines: copy-on-write — first edit copies derived defaults into the overlay
function ownedCaptions(state) {
  return state.review.captions
    ? state.review.captions.map((l) => ({ ...l }))
    : state.run.captions.map((l) => ({ ...l }));
}

function push(state, nextReview) {
  return derive({
    ...state,
    review: nextReview,
    undo: [...state.undo.slice(-UNDO_CAP), state.review],
    redo: [],
    dirty: true,
    saveState: "dirty",
  });
}

function markReviewed(review, id) {
  const un = review.unreviewed || [];
  return un.includes(id) ? { ...review, unreviewed: un.filter((x) => x !== id) } : review;
}

export function reducer(state, action) {
  switch (action.type) {
    case "LOAD": {
      const run = action.payload;
      return derive({
        ...initialState(),
        run,
        review: run.review,
        selection: null,
      });
    }

    case "APPLY_SERVER": {
      // after re-analyze / reset: fresh engine data + overlay from server
      const run = action.payload;
      return derive({
        ...state,
        run,
        review: run.review,
        selection: null,
        undo: [],
        redo: [],
        dirty: false,
        saveState: "clean",
      });
    }

    case "SELECT":
      return { ...state, selection: action.id };

    case "SET_CUT_STATUS": {
      const { id, status } = action;
      let review = markReviewed(state.review, id);
      if (id.startsWith("e")) {
        const prev = review.cuts[id] || {};
        review = { ...review, cuts: { ...review.cuts, [id]: { ...prev, status } } };
      } else if (status === "rejected") {
        // rejecting a manual cut deletes it
        review = { ...review, manual_cuts: review.manual_cuts.filter((m) => m.id !== id) };
        return { ...push(state, review), selection: null };
      }
      return push(state, review);
    }

    case "BATCH_STATUS": {
      const { kinds, status } = action;
      const cuts = { ...state.review.cuts };
      let un = state.review.unreviewed || [];
      state.run.cutlist.removed.forEach((r, i) => {
        if (kinds.includes(r.kind)) {
          const id = `e${i}`;
          cuts[id] = { ...(cuts[id] || {}), status };
          un = un.filter((x) => x !== id);
        }
      });
      return push(state, { ...state.review, cuts, unreviewed: un });
    }

    case "SET_CUT_BOUNDS": {
      const { id } = action;
      const total = state.run.duration;
      const cur = state.cuts.find((c) => c.id === id);
      if (!cur) return state;
      let start = action.start ?? cur.start;
      let end = action.end ?? cur.end;
      start = Math.max(0, Math.min(start, total));
      end = Math.max(0, Math.min(end, total));
      if (end - start < 0.05) return state; // refuse degenerate cuts
      let review = markReviewed(state.review, id);
      if (id.startsWith("e")) {
        const prev = review.cuts[id] || {};
        review = {
          ...review,
          cuts: { ...review.cuts, [id]: { ...prev, start, end, status: prev.status || "accepted" } },
        };
      } else {
        review = {
          ...review,
          manual_cuts: review.manual_cuts.map((m) => (m.id === id ? { ...m, start, end } : m)),
        };
      }
      return push(state, review);
    }

    case "NUDGE_CUT": {
      const cur = state.cuts.find((c) => c.id === action.id);
      if (!cur) return state;
      const start = action.edge === "start" ? cur.start + action.delta : cur.start;
      const end = action.edge === "end" ? cur.end + action.delta : cur.end;
      return reducer(state, { type: "SET_CUT_BOUNDS", id: action.id, start, end });
    }

    case "RESET_CUT": {
      const { id } = action;
      if (!id.startsWith("e")) return state;
      const cuts = { ...state.review.cuts };
      delete cuts[id];
      return push(state, markReviewed({ ...state.review, cuts }, id));
    }

    case "ADD_MANUAL_CUT": {
      const id = `m${Date.now().toString(36)}`;
      const start = Math.min(action.start, action.end);
      const end = Math.max(action.start, action.end);
      if (end - start < 0.05) return state;
      const review = {
        ...state.review,
        manual_cuts: [...state.review.manual_cuts, { id, start, end }],
      };
      return { ...push(state, review), selection: id };
    }

    case "SET_CAPTION_TEXT": {
      const lines = ownedCaptions(state).map((l) =>
        l.id === action.id ? { ...l, text: action.text } : l);
      return push(state, { ...state.review, captions: lines });
    }

    case "SPLIT_CAPTION": {
      const lines = ownedCaptions(state);
      const i = lines.findIndex((l) => l.id === action.id);
      if (i < 0) return state;
      const l = lines[i];
      const words = l.text.trim().split(/\s+/);
      if (words.length < 2) return state;
      const half = Math.ceil(words.length / 2);
      const frac = half / words.length;
      const mid = l.start + (l.end - l.start) * frac;
      const a = { ...l, end: Math.round(mid * 1000) / 1000, text: words.slice(0, half).join(" ") };
      const b = {
        id: `${l.id}s${Date.now().toString(36)}`,
        start: a.end,
        end: l.end,
        text: words.slice(half).join(" "),
      };
      lines.splice(i, 1, a, b);
      return push(state, { ...state.review, captions: lines });
    }

    case "MERGE_CAPTION": {
      // merge line with the following line
      const lines = ownedCaptions(state);
      const i = lines.findIndex((l) => l.id === action.id);
      if (i < 0 || i + 1 >= lines.length) return state;
      const merged = {
        ...lines[i],
        end: lines[i + 1].end,
        text: `${lines[i].text} ${lines[i + 1].text}`.trim(),
      };
      lines.splice(i, 2, merged);
      return push(state, { ...state.review, captions: lines });
    }

    case "RESET_CAPTIONS":
      return push(state, { ...state.review, captions: null });

    case "SET_PRESET":
      return push(state, { ...state.review, caption_preset: action.preset });

    case "SET_EXPORT_OPT":
      return push(state, {
        ...state.review,
        export: { ...state.review.export, [action.key]: action.value },
      });

    case "UNDO": {
      if (!state.undo.length) return state;
      const prev = state.undo[state.undo.length - 1];
      return derive({
        ...state,
        review: prev,
        undo: state.undo.slice(0, -1),
        redo: [...state.redo, state.review],
        dirty: true,
        saveState: "dirty",
      });
    }

    case "REDO": {
      if (!state.redo.length) return state;
      const next = state.redo[state.redo.length - 1];
      return derive({
        ...state,
        review: next,
        redo: state.redo.slice(0, -1),
        undo: [...state.undo, state.review],
        dirty: true,
        saveState: "dirty",
      });
    }

    case "SAVING":
      return { ...state, saveState: "saving" };
    case "SAVED":
      return { ...state, dirty: false, saveState: "saved" };
    case "SAVE_ERROR":
      return { ...state, saveState: "error" };

    default:
      return state;
  }
}

// caption lines currently in effect (overlay if owned, else engine defaults)
export function currentCaptions(state) {
  return state.review?.captions || state.run?.captions || [];
}
