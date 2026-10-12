from pathlib import Path

from conversion_tracking_doctor.exporters import CAPIRemediationExporter, GTMSnippetExporter


def test_gtm_snippets_exporter(tmp_path: Path):
    exporter = GTMSnippetExporter(tmp_path)
    res = exporter.export_all()

    assert "gtm_dedup" in res
    assert "gtm_pii" in res
    assert "gtm_hash" in res

    assert res["gtm_dedup"].exists()
    assert "conv_doc_txns" in res["gtm_dedup"].read_text(encoding="utf-8")
    assert "searchParams" in res["gtm_pii"].read_text(encoding="utf-8")


def test_capi_remediation_exporter(tmp_path: Path):
    exporter = CAPIRemediationExporter(tmp_path)
    res = exporter.export_all()

    assert "capi_python" in res
    assert "capi_node" in res

    assert res["capi_python"].exists()
    assert "def send_meta_capi_purchase" in res["capi_python"].read_text(encoding="utf-8")
    assert "buildCapiPurchasePayload" in res["capi_node"].read_text(encoding="utf-8")
