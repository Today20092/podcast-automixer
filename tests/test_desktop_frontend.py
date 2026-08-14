from pathlib import Path

from podcast_automixer import desktop

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "desktop-ui" / "src" / "main.tsx"
STYLES = ROOT / "desktop-ui" / "src" / "index.css"


def test_desktop_launches_the_bundled_react_shell() -> None:
    bridge = Path(desktop.__file__).read_text(encoding="utf-8")
    index = Path(desktop.__file__).parent / "desktop-ui" / "index.html"

    assert 'with_name("desktop-ui") / "index.html"' in bridge
    assert index.exists()
    assert 'id="root"' in index.read_text(encoding="utf-8")


def test_frontend_uses_required_shadcn_composition() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    for component in (
        "Sidebar",
        "Button",
        "Badge",
        "ToggleGroup",
        "Slider",
        "Progress",
        "Collapsible",
        "Alert",
        "Separator",
        "Tooltip",
    ):
        assert f"<{component}" in source
    assert "<FieldGroup" in source
    assert "space-y-" not in source


def test_renderer_models_the_exclusive_state_journey_and_primary_actions() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    for state in (
        'stage === "recordings"',
        'stage === "preview"',
        'stage === "review"',
        'stage === "render"',
    ):
        assert state in source
    assert "Create Preview" in source
    assert "Render full recordings" in source
    assert "previewActive &&" in source
    assert "renderActive &&" in source
    assert "cancel_preview" in source
    assert "cancel_full_render" in source


def test_review_has_three_modes_and_required_decision_hierarchy() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    for mode in ("Original", "Automixed", "Difference"):
        assert mode in source
    assert "Difference = Automixed − Original" in source
    assert "not a deliverable" in source
    assert "Try another section" in source
    assert "Export Preview" in source
    assert 'variant="ghost"' in source
    assert "api.export_preview()" in source


def test_preview_is_app_owned_and_recording_rows_are_compact() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "choose_preview_directory" not in source
    assert "app-owned temporary storage" in source
    assert "recording-row" in source
    assert "Replace recording" in source
    assert "Remove recording" in source
    assert "Technical details" in source


def test_frontend_preserves_focus_theme_motion_and_narrow_layout() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")

    assert "heading.current?.focus()" in source
    assert '"system" | "light" | "dark"' in source
    assert "@media (max-width: 780px)" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert "overflow-x: hidden" in styles
