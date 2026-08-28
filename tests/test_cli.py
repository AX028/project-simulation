from project_simulation.cli import main


def test_cli_lists_content(capsys) -> None:
    assert main(["classes"]) == 0
    assert "barbarian" in capsys.readouterr().out


def test_cli_create_fight_save_reload(tmp_path, capsys) -> None:
    save = tmp_path / "campaign.json"
    world = tmp_path / "world.h5"
    result = main(
        [
            "play",
            "--class",
            "paladin",
            "--enemy",
            "slime",
            "--seed",
            "12",
            "--save",
            str(save),
            "--world",
            str(world),
        ]
    )
    assert result == 0
    assert save.exists() and world.exists()
    assert "Winner:" in capsys.readouterr().out
    assert main(["inspect", str(save)]) == 0
