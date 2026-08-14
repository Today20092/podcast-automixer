# Automix Workstation UI Prototype

Throwaway UI prototype for issue #65. It uses deterministic fake audio and does not call the Python engine.

Run from the repository root:

    uv run python -m http.server 4173 --directory workstation-prototype

Open http://127.0.0.1:4173/?variant=A. Use the floating arrows or the left/right keyboard arrows to compare variants A, B, and C. Space toggles the prototype playhead.
