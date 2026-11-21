import http from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";
import Browserbase from "@browserbasehq/sdk";
import { chromium } from "playwright-core";
import { validateAllowlist, validateUrl } from "./security.js";

const PORT = Number(process.env.PORT || 10000);
const sessions = new Map();
const MAX_BODY = 65536;
const MAX_TEXT = 24000;
const tools = [
  {name:"browser_session_open",description:"Open a guarded Browserbase Chromium session with an explicit hostname allowlist.",inputSchema:{type:"object",properties:{url:{type:"string"},allowedDomains:{type:"array",items:{type:"string"},minItems:1,maxItems:50}},required:["url","allowedDomains"],additionalProperties:false}},
  {name:"browser_session_navigate",description:"Navigate within the session's original hostname allowlist.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},url:{type:"string"}},required:["sessionId","url"],additionalProperties:false}},
  {name:"browser_session_snapshot",description:"Read current URL, title and visible page text.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},includeHtml:{type:"boolean"}},required:["sessionId"],additionalProperties:false}},
  {name:"browser_session_click",description:"Click a CSS selector. Requires allowSideEffects=true.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},selector:{type:"string"},allowSideEffects:{type:"boolean"}},required:["sessionId","selector"],additionalProperties:false}},
  {name:"browser_session_type",description:"Type into an element. Requires allowSideEffects=true.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},selector:{type:"string"},text:{type:"string"},allowSideEffects:{type:"boolean"}},required:["sessionId","selector","text"],additionalProperties:false}},
  {name:"browser_session_press",description:"Press a supported key. Requires allowSideEffects=true.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},key:{type:"string"},allowSideEffects:{type:"boolean"}},required:["sessionId","key"],additionalProperties:false}},
  {name:"browser_session_screenshot",description:"Capture the current page as PNG.",inputSchema:{type:"object",properties:{sessionId:{type:"string"}},required:["sessionId"],additionalProperties:false}},
  {name:"browser_session_close",description:"Close the browser session and release usage.",inputSchema:{type:"object",properties:{sessionId:{type:"string"}},required:["sessionId"],additionalProperties:false}}
];
const browserbase = () => new Browserbase({apiKey:process.env.BROWSERBASE_API_KEY});
function authorized(req) {
  const supplied = (req.headers.authorization || "").replace(/^Bearer\s+/i,"");
  const expected = process.env.MCP_ACCESS_TOKEN || "";
  if (!supplied || !expected) return false;
  const a=Buffer.from(supplied), b=Buffer.from(expected);
  return a.length===b.length && timingSafeEqual(a,b);
}
function rpc(id,result){return {jsonrpc:"2.0",id,result};}
function rpcError(id,code,message){return {jsonrpc:"2.0",id,error:{code,message}};}
const textResult=(value,extra=[])=>({content:[{type:"text",text:typeof value==="string"?value:JSON.stringify(value)},...extra],isError:false});
async function callTool(name,args) {
  if (name==="browser_session_open") {
    const allowedDomains=validateAllowlist(args.allowedDomains);
    const url=validateUrl(args.url,allowedDomains);
    const bb=browserbase();
    const session=await bb.sessions.create({projectId:process.env.BROWSERBASE_PROJECT_ID});
    try {
      const browser=await chromium.connectOverCDP(session.connectUrl);
      const context=browser.contexts()[0] || await browser.newContext();
      const page=context.pages()[0] || await context.newPage();
      await page.route("**/*",route=>{
        try { validateUrl(route.request().url(),allowedDomains); return route.continue(); }
        catch { return route.abort("blockedbyclient"); }
      });
      await page.goto(url,{waitUntil:"domcontentloaded",timeout:45000});
      const id=randomUUID();
      sessions.set(id,{bb,browser,context,page,allowedDomains,remoteId:session.id});
      let liveViewUrl=null;
      try { const debug=await bb.sessions.debug(session.id); liveViewUrl=debug.debuggerFullscreenUrl || null; } catch {}
      return textResult({status:"opened",sessionId:id,url:page.url(),title:await page.title(),liveViewUrl});
    } catch(error) {
      try { await bb.sessions.update(session.id,{status:"REQUEST_RELEASE"}); } catch {}
      throw error;
    }
  }
  const state=sessions.get(args.sessionId);
  if (!state) throw new Error("Session not found or expired on this service instance");
  if (name==="browser_session_navigate") {
    const url=validateUrl(args.url,state.allowedDomains);
    await state.page.goto(url,{waitUntil:"domcontentloaded",timeout:45000});
    return textResult({url:state.page.url(),title:await state.page.title()});
  }
  if (name==="browser_session_snapshot") {
    const result={url:state.page.url(),title:await state.page.title(),text:(await state.page.locator("body").innerText().catch(()=> "")).slice(0,MAX_TEXT)};
    if(args.includeHtml) result.html=(await state.page.content()).slice(0,MAX_TEXT);
    return textResult(result);
  }
  if (["browser_session_click","browser_session_type","browser_session_press"].includes(name) && args.allowSideEffects!==true)
    return textResult({status:"approval_required",steps:0,message:"Explicit allowSideEffects=true is required."});
  if (name==="browser_session_click") {
    if(typeof args.selector!=="string" || args.selector.length>1000) throw new Error("Invalid selector");
    await state.page.locator(args.selector).first().click({timeout:15000});
    return textResult({clicked:true});
  }
  if (name==="browser_session_type") {
    if(typeof args.selector!=="string" || args.selector.length>1000 || typeof args.text!=="string" || args.text.length>10000) throw new Error("Invalid selector or text");
    await state.page.locator(args.selector).first().fill(args.text,{timeout:15000});
    return textResult({typed:true});
  }
  if (name==="browser_session_press") {
    const keys={ENTER:"Enter",TAB:"Tab",ESCAPE:"Escape",BACKSPACE:"Backspace",ARROWDOWN:"ArrowDown",ARROWUP:"ArrowUp",ARROWLEFT:"ArrowLeft",ARROWRIGHT:"ArrowRight",SPACE:"Space"};
    const key=keys[String(args.key||"").toUpperCase()];
    if(!key) throw new Error("Unsupported key");
    await state.page.keyboard.press(key);
    return textResult({pressed:key});
  }
  if (name==="browser_session_screenshot") {
    const png=await state.page.screenshot({type:"png"});
    return textResult({mimeType:"image/png",bytes:png.length},[{type:"image",data:png.toString("base64"),mimeType:"image/png"}]);
  }
  if (name==="browser_session_close") {
    await state.browser.close().catch(()=>{});
    try { await state.bb.sessions.update(state.remoteId,{status:"REQUEST_RELEASE"}); } catch {}
    sessions.delete(args.sessionId);
    return textResult({status:"closed"});
  }
  throw new Error("Unknown browser tool");
}
async function handle(req,res) {
  const url=new URL(req.url,"http://localhost");
  const headers={"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"};
  if(req.method==="GET" && url.pathname==="/health") {
    const configured=Boolean(process.env.BROWSERBASE_API_KEY && process.env.BROWSERBASE_PROJECT_ID && process.env.MCP_ACCESS_TOKEN);
    res.writeHead(configured?200:503,headers); res.end(JSON.stringify({status:configured?"ok":"configuration_required",service:"flybrain-browserbase-staging",browserbaseConfigured:Boolean(process.env.BROWSERBASE_API_KEY && process.env.BROWSERBASE_PROJECT_ID),mcpAuthConfigured:Boolean(process.env.MCP_ACCESS_TOKEN)})); return;
  }
  if(url.pathname!=="/mcp"){res.writeHead(404,headers);res.end(JSON.stringify({error:"not_found"}));return;}
  if(req.method!=="POST"){res.writeHead(405,{...headers,allow:"POST"});res.end();return;}
  if(!authorized(req)){res.writeHead(401,headers);res.end(JSON.stringify({error:"unauthorized"}));return;}
  let raw=""; for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>MAX_BODY){res.writeHead(413,headers);res.end(JSON.stringify({error:"request_too_large"}));return;}}
  let rpcIn; try{rpcIn=JSON.parse(raw);}catch{res.writeHead(400,headers);res.end(JSON.stringify({error:"invalid_json"}));return;}
  if(!rpcIn || rpcIn.jsonrpc!=="2.0" || typeof rpcIn.method!=="string"){res.writeHead(400,headers);res.end(JSON.stringify({error:"invalid_json_rpc"}));return;}
  let out;
  if(rpcIn.method==="initialize") out=rpc(rpcIn.id,{protocolVersion:"2025-03-26",capabilities:{tools:{listChanged:false}},serverInfo:{name:"flybrain-browserbase-staging",version:"0.1.0"},instructions:"Guarded Browserbase browser tools. New sessions require explicit HTTPS hostname allowlists. Click, type and keypress require allowSideEffects=true. Close sessions promptly."});
  else if(rpcIn.method==="ping") out=rpc(rpcIn.id,{});
  else if(rpcIn.method==="tools/list") out=rpc(rpcIn.id,{tools});
  else if(rpcIn.method==="tools/call"){
    try{const name=rpcIn.params?.name;if(!tools.some(t=>t.name===name)) throw new Error("Unknown tool");out=rpc(rpcIn.id,await callTool(name,rpcIn.params?.arguments||{}));}
    catch(error){out=rpc(rpcIn.id,{content:[{type:"text",text:error instanceof Error?error.message:"Browser operation failed"}],isError:true});}
  } else if(rpcIn.method.startsWith("notifications/")){res.writeHead(202,headers);res.end();return;}
  else out=rpcError(rpcIn.id,-32601,"Method not found");
  res.writeHead(200,headers);res.end(JSON.stringify(out));
}
http.createServer((req,res)=>handle(req,res).catch(()=>{if(!res.headersSent){res.writeHead(500,{"content-type":"application/json"});res.end(JSON.stringify({error:"internal_error"}));}})).listen(PORT,"0.0.0.0");
