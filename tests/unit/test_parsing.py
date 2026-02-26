import pytest

from src.app.parsing import parse_amount, parse_g_command


def test_parse_g_command_ok():
    parsed = parse_g_command("/g 25000 almuerzo ejecutivo")
    assert parsed["monto"] == 25000
    assert parsed["descripcion"] == "almuerzo ejecutivo"


def test_parse_g_command_requires_description():
    parsed = parse_g_command("/g 25000")
    assert "error" in parsed


@pytest.mark.parametrize("prefix", ["$", "usd", "us", "mxn"])
def test_parse_g_command_currency_prefix_with_space(prefix):
    parsed = parse_g_command(f"/g {prefix} 6.300 Oxxo Atabanza")
    assert parsed["monto"] == 6300
    assert parsed["descripcion"] == "Oxxo Atabanza"


def test_parse_g_command_currency_prefix_with_space_requires_description():
    parsed = parse_g_command("/g usd 6.300")
    assert (
        parsed["error"]
        == "Debes incluir una descripción. Ejemplo: /g 25000 almuerzo"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("20000", 20000),
        ("20.000", 20000),
        ("20,000", 20000),
        ("50.000,00", 50000),
        ("50,000.00", 50000),
        ("20k", 20000),
        ("$20.000", 20000),
        ("10,5", 10),
    ],
)
def test_parse_amount_common_formats(raw, expected):
    assert parse_amount(raw) == expected
