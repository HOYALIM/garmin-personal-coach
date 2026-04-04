import runpy
from types import SimpleNamespace

import pytest


def test_wizard_init_last_lines(monkeypatch):
    import garmin_coach.wizard as wizard
    import garmin_coach.profile_manager as profile_manager

    saved = []

    def make_pm():
        return SimpleNamespace(load=lambda: None, save=lambda profile: saved.append(profile))

    monkeypatch.setattr(wizard, "ProfileManager", make_pm)
    monkeypatch.setattr(wizard, "prompt_non_empty", lambda prompt: "Pat")
    monkeypatch.setattr(wizard, "prompt_number", lambda *args, **kwargs: 30)
    monkeypatch.setattr(
        wizard, "prompt_choice", lambda prompt, options, default=0: options[default]
    )
    monkeypatch.setattr(wizard, "prompt_yes_no", lambda *args, **kwargs: False)
    monkeypatch.setattr(wizard, "_check_garmin_connection", lambda: False)

    inputs = iter(["oops", "1", "Race", "bad-date", "", "", "", "", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    wizard.run_wizard()
    assert saved[-1].profile.sports == [profile_manager.Sport.RUNNING]

    inputs = iter(["", "Race", "", "", "", "", "n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    wizard.run_wizard()
    assert saved[-1].profile.sports == [profile_manager.Sport.RUNNING]

    monkeypatch.setattr(
        "builtins.input", lambda *args, **kwargs: (_ for _ in ()).throw(SystemExit(0))
    )
    with pytest.raises(SystemExit):
        runpy.run_path(
            str(
                __import__("pathlib").Path(__file__).resolve().parents[1]
                / "garmin_coach"
                / "wizard"
                / "__init__.py"
            ),
            run_name="__main__",
        )
