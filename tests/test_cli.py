from pathlib import Path

from typer.testing import CliRunner

from conversion_tracking_doctor.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "conversion-tracking-doctor" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_inspect_url():
    # Test clean URL
    result_clean = runner.invoke(app, ["inspect-url", "https://example.com/checkout/success?order_id=1024"])
    assert result_clean.exit_code == 0
    assert "PASSED" in result_clean.stdout

    # Test leaky URL with email
    result_leak = runner.invoke(app, ["inspect-url", "https://example.com/checkout/success?order_id=1024&email=user@test.com"])
    assert result_leak.exit_code == 0
    assert "PRIVACY ALERT" in result_leak.stdout


def test_cli_audit(tmp_path: Path):
    result = runner.invoke(app, ["audit", "--out-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Tracking Health Audit Summary" in result.stdout
    assert "Audit Complete!" in result.stdout

    # Check that generated files exist
    generated = list(tmp_path.glob("audit-*.html"))
    assert len(generated) == 1
    assert (tmp_path / "tracking_doctor.sqlite").exists()
    assert (tmp_path / "gtm_transaction_deduplication.js").exists()
