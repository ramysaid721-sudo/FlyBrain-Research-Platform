import pytest

from flybrain_os.capability_mesh import (
    TaskContractError, build_task_contract, capability_registry, plan_task_route,
)


def test_registry_is_metadata_only():
    result = capability_registry()
    assert result["execution_enabled"] is False
    assert any(item["capability_id"] == "flybrain.project_context" for item in result["capabilities"])


def test_confidential_data_is_forced_to_local_provider():
    contract = build_task_contract(
        "Review private project notes", "confidential",
        ["local", "modelhub", "http_research"], True, 0.0,
    )
    assert contract["allowed_providers"] == ["local"]
    assert contract["allow_network"] is False
    plan = plan_task_route(contract)
    assert plan["status"] == "route_planned"
    assert all(route["provider"] == "local" for route in plan["routes"])


def test_public_search_requires_explicit_network_permission():
    no_network = build_task_contract("Research a public topic", "public", ["http_research"], False, 0.0)
    assert plan_task_route(no_network)["status"] == "no_eligible_route"
    with_network = build_task_contract("Research a public topic", "public", ["http_research"], True, 0.0)
    plan = plan_task_route(with_network, "web.public_search")
    assert plan["status"] == "route_planned"
    assert plan["routes"][0]["execution_ready"] is True


def test_paid_budget_is_rejected():
    with pytest.raises(TaskContractError):
        build_task_contract("Task", max_cost_usd=0.01)


def test_restricted_data_fails_closed_until_a_hardened_local_capability_exists():
    contract = build_task_contract("Handle restricted records", "restricted",
                                   ["local", "http_research"], True, 0.0)
    plan = plan_task_route(contract)
    assert plan["status"] == "no_eligible_route"
    assert plan["routes"] == []


def test_side_effects_cannot_be_enabled_by_tampering():
    contract = build_task_contract("Read a page")
    contract["side_effects_allowed"] = True
    with pytest.raises(TaskContractError):
        plan_task_route(contract)


def test_unknown_classification_is_rejected():
    with pytest.raises(TaskContractError):
        build_task_contract("Task", "top-secret")


def test_unknown_provider_has_no_route():
    contract = build_task_contract("Task", "public", ["unknown-provider"], False, 0.0)
    assert plan_task_route(contract)["status"] == "no_eligible_route"


def test_unknown_external_provider_cost_is_not_assumed_free():
    contract = build_task_contract("Consult an external model", "public",
                                   ["modelhub"], True, 0.0)
    plan = plan_task_route(contract, "model.external_consultation")
    assert plan["status"] == "no_eligible_route"


def test_registry_reports_local_project_context_adapter_as_available():
    result = capability_registry()
    local = next(item for item in result["capabilities"]
                 if item["capability_id"] == "flybrain.project_context")
    assert local["runtime_state"] == "adapter_available"
    contract = build_task_contract("Retrieve project context", "public", ["local"], False, 0.0)
    plan = plan_task_route(contract, "flybrain.project_context")
    assert plan["routes"][0]["execution_ready"] is True
    assert plan["routes"][0]["requires_runtime_verification"] is False


def test_public_search_adapter_requires_explicit_public_network_and_is_read_only(monkeypatch):
    from flybrain_os import browser_use_adapter
    from flybrain_os.capability_mesh import execute_read_only_capability

    monkeypatch.setattr(browser_use_adapter, "run_browser_search",
                        lambda query, max_results: {"status": "completed", "query": query, "results": []})
    contract = build_task_contract("Search public sources", "public", ["http_research"], True, 0.0)
    result = execute_read_only_capability(contract, "web.public_search",
                                          {"query": "public climate data", "max_results": 3})
    assert result["execution_started"] is True
    assert result["side_effects"] is False
    assert result["result"]["query"] == "public climate data"


def test_external_adapter_rejects_confidential_data():
    from flybrain_os.capability_mesh import execute_read_only_capability
    contract = build_task_contract("Search", "confidential", ["local", "http_research"], True, 0.0)
    with pytest.raises(TaskContractError):
        execute_read_only_capability(contract, "web.public_search", {"query": "private notes"})


def test_external_adapter_rejects_missing_network_permission():
    from flybrain_os.capability_mesh import execute_read_only_capability
    contract = build_task_contract("Search", "public", ["http_research"], False, 0.0)
    with pytest.raises(TaskContractError):
        execute_read_only_capability(contract, "web.public_search", {"query": "topic"})


def test_local_project_context_adapter_runs_without_network(monkeypatch):
    from flybrain_os import chat_api
    from flybrain_os.capability_mesh import execute_read_only_capability

    monkeypatch.setattr(chat_api, "retrieve_project_context",
                        lambda question, limit=6: [{"source": "README.md", "excerpt": "Local evidence"}])
    contract = build_task_contract("Find project architecture", "confidential", ["local"], False, 0.0)
    result = execute_read_only_capability(contract, "flybrain.project_context", {"limit": 4})
    assert result["status"] == "completed"
    assert result["provider"] == "local"
    assert result["data_classification"] == "confidential"
    assert result["side_effects"] is False
    assert result["result"]["sources"][0]["source"] == "README.md"


def test_local_project_context_rejects_network_permission():
    from flybrain_os.capability_mesh import execute_read_only_capability
    contract = build_task_contract("Retrieve project context", "public", ["local"], True, 0.0)
    with pytest.raises(TaskContractError):
        execute_read_only_capability(contract, "flybrain.project_context", {"limit": 2})
