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

def test_mcp_auth_required(tmp_path):
    token="z"*40
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    response,body=call(app,{"jsonrpc":"2.0","id":1,"method":"initialize"},"bad")
    assert response["status"]=="401 Unauthorized"

def test_initialize_and_tool_discovery(tmp_path):
    token="z"*40
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    response,body=call(app,{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26"}})
    assert body["result"]["serverInfo"]["name"]=="flybrain-research-bridge"
    response,body=call(app,{"jsonrpc":"2.0","id":2,"method":"tools/list"})
    assert body["result"]["tools"][0]["name"]=="ask_flybrain"

def test_tool_call_uses_existing_bridge(tmp_path,monkeypatch):
    token="z"*40
    monkeypatch.setattr("flybrain_os.chat_api.retrieve_project_context",lambda q:[{"source":"README.md","relevance_score":1,"excerpt":"FlyBrain research."}])
    monkeypatch.setattr("flybrain_os.chat_api.ModelConsultation.consult",lambda *a,**k:{"status":"no_providers_configured","results":[]})
    app=FlyBrainMCP(FlyBrainChatApp(token,tmp_path/"db.sqlite"),token)
    request={"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"ask_flybrain","arguments":{"question":"What is FlyBrain?"}}}
    response,body=call(app,request)
    assert response["status"]=="200 OK"
    assert body["result"]["structuredContent"]["status"]=="context_only"
    assert body["result"]["isError"] is False
