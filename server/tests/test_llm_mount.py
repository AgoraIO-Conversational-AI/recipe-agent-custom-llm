"""The LLM endpoint is mounted into the server app and stays agora-free."""


def test_llm_health_is_mounted_under_slash_llm(client):
    response = client.get("/llm/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_llm_chat_completions_reachable_through_mount(client):
    response = client.post(
        "/llm/chat/completions",
        json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    # Prove a well-formed SSE stream flows through the mount, not just that the
    # route is reachable.
    assert response.text.rstrip().endswith("data: [DONE]")


def test_llm_module_has_no_agora_dependency():
    """llm.py must not import any Agora SDK — it stays provider-agnostic.

    Checks actual import statements (not prose): mentioning Agora in
    docstrings or demo strings is fine; importing an agora_* package is not.
    """
    import ast
    import inspect

    import llm

    tree = ast.parse(inspect.getsource(llm))
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(node.module.split(".")[0])

    agora_imports = sorted(r for r in imported_roots if r.startswith("agora"))
    assert not agora_imports, f"llm.py must not import an Agora SDK; found: {agora_imports}"
