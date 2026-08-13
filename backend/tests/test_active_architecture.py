def test_openapi_bevat_alleen_actieve_bronnenwerkbank(client):
    paths = set(client.get("/openapi.json").json()["paths"])

    assert "/research/candidates/{candidate_id}/review" in paths
    assert "/batches/{batch_id}/export.xlsx" in paths
    assert not any(path.startswith("/chat") for path in paths)
    assert not any(path.startswith("/chat-templates") for path in paths)
    assert not any(path.startswith("/jaarverslagen") for path in paths)
    assert not any(path.startswith("/bellijst") for path in paths)
    assert not any(path.endswith("/run-legacy") for path in paths)
    assert "/candidates/{candidate_id}/approve" not in paths
