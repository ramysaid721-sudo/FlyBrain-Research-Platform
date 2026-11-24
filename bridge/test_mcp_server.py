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

def test_eec_tools_are_discoverable_and_read_only(tmp_path):
    token="z"*40
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    response,body=call(app,{"jsonrpc":"2.0","id":10,"method":"tools/list"})
    tools={tool["name"]:tool for tool in body["result"]["tools"]}
    assert {"eec_status","eec_plan","eec_submit_plan","eec_plan_status"} <= set(tools)
    assert tools["eec_submit_plan"]["annotations"]["readOnlyHint"] is False
    assert tools["eec_plan"]["annotations"]["readOnlyHint"] is True


def test_eec_plan_tool_returns_bounded_zero_cost_plan(tmp_path):
    token="z"*40
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"eec_plan","arguments":{"objective":"Build an isolated EEC planning layer","task_kind":"engineering"}}}
    response,body=call(app,request,"")
    plan=body["result"]["structuredContent"]
    assert response["status"]=="200 OK"
    assert plan["status"]=="planned"
    assert plan["policy"]["max_spend"]==0
    assert plan["policy"]["provider_calls_enabled"] is False
    assert plan["policy"]["external_data_transfer"] is False
    assert plan["execution_readiness"]=="blocked_pending_typed_worker_and_zero_cost_provider_gate"


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

def test_eec_submit_plan_requires_authentication_and_persists_plan(tmp_path,monkeypatch):
    token="z"*40
    monkeypatch.setattr("flybrain_os.mcp_server.persist_plan",lambda plan:{
        "status":"ok","result":{"status":"persisted","plan_id":plan["plan_id"],"task_count":len(plan["tasks"])}
    })
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"eec_submit_plan","arguments":{
        "objective":"Build the Staging EEC plan ledger","task_kind":"engineering"
    }}}
    response,_=call(app,request,"bad")
    assert response["status"]=="401 Unauthorized"
    response,body=call(app,request,token)
    assert response["status"]=="200 OK"
    assert body["result"]["structuredContent"]["result"]["status"]=="persisted"


def test_eec_plan_status_requires_authentication(tmp_path,monkeypatch):
    token="z"*40
    monkeypatch.setattr("flybrain_os.mcp_server.get_plan_status",lambda plan_id:{"status":"ok","plan":{"plan_id":plan_id}})
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":13,"method":"tools/call","params":{"name":"eec_plan_status","arguments":{
        "plan_id":"12233a4b-be9b-5bf5-969c-f1eb278545eb"
    }}}
    response,_=call(app,request,"")
    assert response["status"]=="401 Unauthorized"
    response,body=call(app,request,token)
    assert response["status"]=="200 OK"
    assert body["result"]["structuredContent"]["status"]=="ok"
