"""Default instruction used to drive the virtual try-on.

Kept in the Core (not the CLI) because the default prompt is part of the use case's
business behavior; the CLI may still override it per-invocation via DressCommand.
"""

DEFAULT_TRYON_PROMPT = (
    "Using the first image as the person and the second image as the outfit, "
    "generate a photorealistic image of the same person wearing that outfit. "
    "Preserve the person's face, body shape, pose, and background; keep the "
    "lighting and perspective consistent and natural."
)
