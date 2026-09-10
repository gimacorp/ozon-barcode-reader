from barcode_reader.provenance import config_hash, metadata


def test_metadata_records_actual_revision_config_and_explicit_cpu(monkeypatch):
    monkeypatch.setenv("OZON_CPU_MODEL", "Test CPU")
    result = metadata({"speed": 1000}, seed=42)
    assert result["cpu"] == "Test CPU" and result["cpu_source"] == "OZON_CPU_MODEL"
    assert len(result["git_revision"]) == 40 and len(result["source_sha256"]) == 64
    assert result["config_sha256"] == config_hash({"speed": 1000})
    assert result["parameters"] == {"seed": 42}
    assert result["python"] and result["os"] and result["packages"]
