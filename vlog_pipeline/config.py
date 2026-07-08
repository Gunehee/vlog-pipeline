"""Pipeline configuration with editing thresholds and model routing."""
from dataclasses import dataclass, field, asdict


# Words treated as fillers when they appear as standalone tokens.
# "like"/"so"/"you know" are only cut when whisper flags them as
# low-confidence hesitations (see fillers.py) to avoid cutting real usage.
ALWAYS_FILLERS = {"um", "uh", "uhm", "umm", "uhh", "erm", "hmm", "mmm", "ah", "eh"}
CONTEXTUAL_FILLERS = {"like", "so", "basically", "actually", "literally"}


@dataclass
class Config:
    # silence removal
    silence_db: float = -35.0        # silencedetect noise floor
    min_silence: float = 0.45        # seconds of quiet before we call it dead air
    keep_pad: float = 0.15           # breathing room kept on each side of a cut
    # pacing
    min_segment: float = 0.60        # never emit a kept segment shorter than this
    min_cut: float = 0.12            # cuts smaller than this are not worth a jump cut
    audio_fade: float = 0.010        # crossfade at cut points to avoid clicks
    # filler removal
    filler_pad: float = 0.04         # trim margin around a filler word
    # whisper
    whisper_model: str = "small.en"
    # highlight / shorts
    short_target: float = 50.0       # target duration of 9:16 highlight cut
    short_min: float = 35.0
    short_max: float = 59.0
    # export
    crf: int = 20
    preset: str = "veryfast"
    audio_bitrate: str = "192k"

    def to_dict(self) -> dict:
        return asdict(self)


# stage -> (model, engine, billing) for runtime visibility
STAGE_ROUTING = {
    "plan":     ("sonnet",  "claude -p subprocess", "METERED (ANTHROPIC_API_KEY)"),
    "ingest":   ("-",       "local ffprobe/ffmpeg", "free (local)"),
    "edit":     ("-",       "local ffmpeg/whisper/OpenCV (Fable-authored, deterministic)", "free (local)"),
    "caption":  ("-",       "local whisper/libass (Fable-authored, deterministic)", "free (local)"),
    "package":  ("sonnet",  "claude -p subprocess", "METERED (ANTHROPIC_API_KEY)"),
    "optimize": ("haiku",   "claude -p subprocess", "METERED (ANTHROPIC_API_KEY)"),
}

STAGE_ORDER = ["plan", "ingest", "edit", "caption", "package", "optimize"]
