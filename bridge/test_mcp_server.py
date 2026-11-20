import io, json
from flybrain_os.chat_api import FlyBrainChatApp
from flybrain_os.mcp_server import FlyBrainMCP

def call(app, request, token="z"*40):
    raw = json.dumps(request).encode()
    env = {"REQUEST_METHOD":"POST","PATH_INFO":"/mcp","CONTENT_LENGTH":str(len(raw)),
           "CONTENT_TYPE":"application/json","HTTP_AUTHORIZATION":"Bearer "+token,
           "wsgi.input":io.BytesIO(raw)}
    captured = {}
    def start(status, headers): captured["status"] = status
    body = b"".join(app(env, start))
    return captured, json.loads(body) if body else None

def test_interactive_browser_task_requires_bearer_token(tmp_path):
    token="z"*40
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"browser_run_task","arguments":{"url":"https://example.com","goal":"Read the page title"}}}
    response,body=call(app,request,"bad")
    assert response["status"]=="401 Unauthorized"

def test_initialize_and_tool_discovery(tmp_path):
    token="z"*40
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    response,body=call(app,{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}})
    assert body["result"]["serverInfo"]["name"]=="flybrain-research-bridge"
    response,body=call(app,{"jsonrpc":"2.0","id":2,"method":"tools/list"})
    names={tool["name"] for tool in body["result"]["tools"]}
    assert {"ask_flybrain","browser_use_status","browser_run_task","browser_search","browser_fetch","browser_research"} <= names

def test_tool_call_uses_existing_bridge(tmp_path,monkeypatch):
    token="z"*40
    monkeypatch.setattr("flybrain_os.chat_api.retrieve_project_context",lambda q:[{"source":"README.md","relevance_score":1,"excerpt":"FlyBrain research."}])
    monkeypatch.setattr("flybrain_os.chat_api.ModelConsultation.consult",lambda *a,**k:{"status":"no_providers_configured","results":[]})
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ask_flybrain","arguments":{"question":"What is FlyBrain?"}}}
    response,body=call(app,request,"")
    assert response["status"]=="200 OK"
    assert body["result"]["structuredContent"]["status"]=="context_only"
    assert body["result"]["isError"] is False

def test_browser_status_tool_is_exposed(tmp_path,monkeypatch):
    token="z"*40
    monkeypatch.setattr("flybrain_os.browser_use_adapter.browser_use_status",lambda:{"installed":False,"ready":False})
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"browser_use_status","arguments":{}}}
    response,body=call(app,request,"")
    assert response["status"]=="200 OK"
    assert body["result"]["structuredContent"]["ready"] is False


def test_health_reports_http_research_and_interactive_browser_separately(tmp_path,monkeypatch):
    token="z"*40
    monkeypatch.setattr("flybrain_os.browser_use_adapter.browser_use_status",lambda:{
        "installed":False,"ready":False,"interactive_browser_ready":False,
        "web_search_ready":True,"web_fetch_ready":True,"provider":"ollama"
    })
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    env={"REQUEST_METHOD":"GET","PATH_INFO":"/health","CONTENT_LENGTH":"0"}
    captured={}
    def start(status,headers): captured["status"]=status
    body=b"".join(app(env,start))
    payload=json.loads(body)
    assert captured["status"]=="200 OK"
    assert payload["version"]=="0.16.0"
    assert payload["capabilities"]["public_web_search"] is True
    assert payload["capabilities"]["interactive_browser"] is False


def test_public_browser_search_tool_uses_http_adapter_without_token(tmp_path,monkeypatch):
    token="z"*40
    monkeypatch.setattr("flybrain_os.browser_use_adapter.run_browser_search",lambda q,n:{"status":"completed","query":q,"results":[]})
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"browser_search","arguments":{"query":"test"}}}
    response,body=call(app,request,"")
    assert response["status"]=="200 OK"
    assert body["result"]["structuredContent"]["status"]=="completed"


def test_public_mcp_rate_limit(tmp_path):
    token="z"*40
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":1,"method":"ping"}
    for _ in range(60):
        response,_=call(app,request,"")
        assert response["status"]=="200 OK"
    response,_=call(app,request,"")
    assert response["status"]=="429 Too Many Requests"


def test_root_path_is_a_public_health_check(tmp_path,monkeypatch):
    token="z"*40
    monkeypatch.setattr("flybrain_os.browser_use_adapter.browser_use_status",lambda:{
        "installed":False,"ready":False,"interactive_browser_ready":False,
        "web_search_ready":True,"web_fetch_ready":True,"provider":"ollama"
    })
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    env={"REQUEST_METHOD":"GET","PATH_INFO":"/","CONTENT_LENGTH":"0"}
    captured={}
    def start(status,headers): captured["status"]=status
    body=b"".join(app(env,start))
    payload=json.loads(body)
    assert captured["status"]=="200 OK"
    assert payload["service"]=="flybrain-mcp"
    assert payload["version"]=="0.16.0"


def test_capability_registry_is_exposed_without_execution(tmp_path):
    token = "z" * 40
    app = FlyBrainMCP(FlyBrainChatApp(token, tmp_path / "db.sqlite"), token)
    response, body = call(app, {"jsonrpc": "2.0", "id": 20, "method": "tools/list"})
    names = {tool["name"] for tool in body["result"]["tools"]}
    assert {"capability_registry", "plan_task_route"} <= names
    response, body = call(app, {"jsonrpc": "2.0", "id": 21, "method": "tools/call",
                                "params": {"name": "capability_registry", "arguments": {}}}, "")
    assert response["status"] == "200 OK"
    assert body["result"]["structuredContent"]["execution_enabled"] is False


def test_confidential_task_route_is_forced_to_local(tmp_path):
    token = "z" * 40
    app = FlyBrainMCP(FlyBrainChatApp(token, tmp_path / "db.sqlite"), token)
    request = {"jsonrpc": "2.0", "id": 22, "method": "tools/call",
               "params": {"name": "plan_task_route", "arguments": {
                   "objective": "Review confidential project notes",
                   "data_classification": "confidential",
                   "allowed_providers": ["local", "modelhub", "http_research"],
                   "allow_network": True, "max_cost_usd": 0}}}
    response, body = call(app, request, "")
    plan = body["result"]["structuredContent"]
    assert response["status"] == "200 OK"
    assert plan["status"] == "route_planned"
    assert plan["contract"]["allowed_providers"] == ["local"]
    assert plan["contract"]["allow_network"] is False
    assert plan["execution_started"] is False


def test_execute_read_only_route_uses_public_search_adapter(tmp_path, monkeypatch):
    token = "z" * 40
    monkeypatch.setattr("flybrain_os.browser_use_adapter.run_browser_search",
                        lambda query, max_results: {
                            "status": "completed", "query": query,
                            "results": [{"title": "Public source", "url": "https://example.org"}],
                        })
    app = FlyBrainMCP(FlyBrainChatApp(token, tmp_path / "db.sqlite"), token)
    request = {"jsonrpc": "2.0", "id": 23, "method": "tools/call",
               "params": {"name": "execute_read_only_route", "arguments": {
                   "objective": "Search public climate information",
                   "capability_id": "web.public_search",
                   "allow_network": True,
                   "allowed_providers": ["http_research"],
                   "arguments": {"query": "public climate information", "max_results": 2}}}}
    response, body = call(app, request)
    result = body["result"]["structuredContent"]
    assert response["status"] == "200 OK"
    assert result["execution_started"] is True
    assert result["side_effects"] is False
    assert result["result"]["results"][0]["url"] == "https://example.org"


def test_execute_read_only_route_rejects_unapproved_arguments(tmp_path):
    token = "z" * 40
    app = FlyBrainMCP(FlyBrainChatApp(token, tmp_path / "db.sqlite"), token)
    request = {"jsonrpc": "2.0", "id": 24, "method": "tools/call",
               "params": {"name": "execute_read_only_route", "arguments": {
                   "objective": "Search", "capability_id": "web.public_search",
                   "allow_network": True, "allowed_providers": ["http_research"],
                   "arguments": {"query": "topic", "arbitrary": "not allowed"}}}}
    response, body = call(app, request)
    assert response["status"] == "400 Bad Request"


def test_execute_local_project_context_route_keeps_confidential_data_local(tmp_path, monkeypatch):
    token = "z" * 40
    monkeypatch.setattr("flybrain_os.chat_api.retrieve_project_context",
                        lambda question, limit=6: [{"source": "README.md", "excerpt": "Local result"}])
    app = FlyBrainMCP(FlyBrainChatApp(token, tmp_path / "db.sqlite"), token)
    request = {"jsonrpc": "2.0", "id": 25, "method": "tools/call",
               "params": {"name": "execute_read_only_route", "arguments": {
                   "objective": "Retrieve confidential project context",
                   "capability_id": "flybrain.project_context",
                   "data_classification": "confidential",
                   "allowed_providers": ["local"],
                   "allow_network": False,
                   "arguments": {"limit": 3}}}}
    response, body = call(app, request)
    result = body["result"]["structuredContent"]
    assert response["status"] == "200 OK"
    assert result["provider"] == "local"
    assert result["data_classification"] == "confidential"
    assert result["side_effects"] is False
    assert result["result"]["sources"][0]["source"] == "README.md"



def test_fase_component_compliance_tool_is_exposed_and_requires_auth(tmp_path):
    token = "z" * 40
    app = FlyBrainMCP(FlyBrainChatApp(token, tmp_path / "db.sqlite"), token)
    response, body = call(app, {"jsonrpc": "2.0", "id": 30, "method": "tools/list"})
    names = {tool["name"] for tool in body["result"]["tools"]}
    assert "evaluate_component_review" in names

    request = {"jsonrpc": "2.0", "id": 31, "method": "tools/call",
               "params": {"name": "evaluate_component_review", "arguments": {
                   "component_record": {
                       "component_id": "flybrain.native.service",
                       "component_type": "original",
                       "provenance_verified": True,
                       "licence_review_status": "unreviewed",
                       "clean_room_required": False,
                       "clean_room_spec_approved": False,
                       "restricted_material_accessed": False,
                       "patent_review_required": False,
                       "patent_review_status": "not_assessed",
                       "trade_secret_review_status": "no_restricted_material",
                       "terms_review_status": "approved",
                       "security_review_status": "passed",
                       "intended_use": "staging-only",
                       "jurisdiction": "to-be-confirmed"
                   }}}}
    response, body = call(app, request, "invalid")
    assert response["status"] == "401 Unauthorized"
    response, body = call(app, request, token)
    assert response["status"] == "200 OK"
    assert body["result"]["structuredContent"]["decision"] == "eligible_for_human_approval"
    assert body["result"]["structuredContent"]["release_eligible"] is True
