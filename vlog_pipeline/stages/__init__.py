class StageError(RuntimeError):
    """A stage failed its validation gate; the coordinator must not proceed."""
