import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, accept, mcp-session-id, last-event-id",
};
const MAX_BODY = 65536;
const MAX_TEXT = 24000;
const tools = [
  {name:"browser_session_open",description:"Start a guarded Browserbase Chromium session. Supply an HTTPS URL and explicit hostname allowlist.",inputSchema:{type:"object",properties:{url:{type:"string"},allowedDomains:{type:"array",items:{type:"string"},minItems:1,maxItems:50}},required:["url","allowedDomains"],additionalProperties:false}},
  {name:"browser_session_navigate",description:"Navigate within the session's original hostname allowlist.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},url:{type:"string"}},required:["sessionId","url"],additionalProperties:false}},
  {name:"browser_session_snapshot",description:"Read the current URL, title, visible text and optional bounded HTML.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},includeHtml:{type:"boolean"}},required:["sessionId"],additionalProperties:false}},
  {name:"browser_session_click",description:"Click a page element. Requires allowSideEffects=true.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},selector:{type:"string"},allowSideEffects:{type:"boolean"}},required:["sessionId","selector"],additionalProperties:false}},
  {name:"browser_session_type",description:"Type into a page element. Requires allowSideEffects=true.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},selector:{type:"string"},text:{type:"string"},allowSideEffects:{type:"boolean"}},required:["sessionId","selector","text"],additionalProperties:false}},
  {name:"browser_session_press",description:"Press a supported key. Requires allowSideEffects=true.",inputSchema:{type:"object",properties:{sessionId:{type:"string"},key:{type:"string"},allowSideEffects:{type:"boolean"}},required:["sessionId","key"],additionalProperties:false}},
  {name:"browser_session_screenshot",description:"Capture the current viewport as PNG.",inputSchema:{type:"object",properties:{sessionId:{type:"string"}},required:["sessionId"],additionalProperties:false}},
  {name:"browser_session_close",description:"Close the browser session and release Browserbase usage.",inputSchema:{type:"object",properties:{sessionId:{type:"string"}},required:["sessionId"],additionalProperties:false}}
];
function json(data:unknown,status=200){return new Response(JSON.stringify(data),{status,headers:HEADERS});}
function rpc(id:unknown,result:unknown){return json({jsonrpc:"2.0",id,result});}
function rpcError(id:unknown,code:number,message:string){return json({jsonrpc:"2.0",id,error:{code,message}});}
function textResult(value:unknown,extra:unknown[]=[]){return {content:[{type:"text",text:typeof value==="string"?value:JSON.stringify(value)},...extra],isError:false};}
function isAuthorized(req:Request){
  const supplied=(req.headers.get("authorization")||"").replace(/^Bearer\s+/i,"");
  const expected=Deno.env.get("FLYBRAIN_BROWSER_ACCESS_TOKEN")||"";
  if(!supplied||!expected)return false;
  const a=new TextEncoder().encode(supplied),b=new TextEncoder().encode(expected);
  if(a.length!==b.length)return false;
  let diff=0;for(let i=0;i<a.length;i++)diff|=a[i]^b[i];return diff===0;
}
function validateAllowlist(value:unknown):string[]{
  if(!Array.isArray(value)||value.length<1||value.length>50)throw new Error("allowedDomains must contain 1–50 hostnames");
  const list=[...new Set(value.map(v=>String(v).trim().toLowerCase()))];
  for(const p of list){
    if(!/^(?:\*\.)?[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(p)||p.includes("..")||p.length>253)throw new Error("Invalid hostname allowlist entry");
    const h=p.startsWith("*.")?p.slice(2):p;
    if(!h.includes(".")||/^(?:localhost|.*\.(?:local|internal|test))$/.test(h))throw new Error("Unsafe hostname allowlist entry");
  }
  return list;
}
function allowedHost(host:string,list:string[]){
  return list.some(p=>p.startsWith("*.")?host.endsWith(p.slice(1))&&host!==p.slice(2):host===p);
}
function validateUrl(value:string,list:string[]){
  const u=new URL(value);
  if(u.protocol!=="https:"||u.username||u.password)throw new Error("Only credential-free HTTPS URLs are allowed");
  if(!allowedHost(u.hostname.toLowerCase(),list))throw new Error("URL hostname is not in the session allowlist");
  return u.toString();
}
function b64(bytes:Uint8Array){let s="";for(const b of bytes)s+=String.fromCharCode(b);return btoa(s).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");}
function unb64(s:string){if(!/^[A-Za-z0-9_-]+$/.test(s))throw new Error("Invalid session token");const x=s.replace(/-/g,"+").replace(/_/g,"/")+"=".repeat((4-s.length%4)%4);return Uint8Array.from(atob(x),c=>c.charCodeAt(0));}
async function signingKey(){
  const secret=Deno.env.get("FLYBRAIN_SESSION_SIGNING_KEY")||"";
  if(secret.length<32)throw new Error("Session signing key is not configured");
  return await crypto.subtle.importKey("raw",new TextEncoder().encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign","verify"]);
}
async function signSession(id:string,domains:string[]){
  const payload=b64(new TextEncoder().encode(JSON.stringify({v:1,id,domains,exp:Date.now()+15*60*1000})));
  const sig=await crypto.subtle.sign("HMAC",await signingKey(),new TextEncoder().encode(payload));
  return payload+"."+b64(new Uint8Array(sig));
}
async function readSession(token:string){
  if(typeof token!=="string"||token.length>4096)throw new Error("Invalid session handle");
  const p=token.split(".");if(p.length!==2)throw new Error("Invalid session handle");
  const valid=await crypto.subtle.verify("HMAC",await signingKey(),unb64(p[1]),new TextEncoder().encode(p[0]));
  if(!valid)throw new Error("Invalid session signature");
  const data=JSON.parse(new TextDecoder().decode(unb64(p[0])));
  if(data.v!==1||typeof data.id!=="string"||!data.id||!Number.isFinite(data.exp)||data.exp<=Date.now())throw new Error("Session handle expired");
  return {id:data.id,domains:validateAllowlist(data.domains)};
}
async function bbFetch(path:string,init:RequestInit={}){
  const key=Deno.env.get("BROWSERBASE_API_KEY")||"";
  if(key.length<16)throw new Error("Browserbase API key is not configured");
  const response=await fetch("https://api.browserbase.com"+path,{...init,headers:{"X-BB-API-Key":key,"content-type":"application/json",...(init.headers||{})},signal:AbortSignal.timeout(20000)});
  if(!response.ok)throw new Error("Browserbase API returned HTTP "+response.status);
  return response.status===204?null:await response.json();
}
async function createRemoteSession(){
  const projects=await bbFetch("/v1/projects",{method:"GET"});
  const project=Array.isArray(projects)?projects[0]:projects?.projects?.[0];
  if(!project?.id)throw new Error("No Browserbase project was found for this API key");
  return await bbFetch("/v1/sessions",{method:"POST",body:JSON.stringify({projectId:project.id})});
}
async function withCdp(connectUrl:string,domains:string[],operation:(send:(method:string,params?:Record<string,unknown>,sessionId?:string)=>Promise<any>,sid:string)=>Promise<any>){
  const ws=new WebSocket(connectUrl);
  await new Promise<void>((resolve,reject)=>{const t=setTimeout(()=>reject(new Error("Browser connection timed out")),15000);ws.onopen=()=>{clearTimeout(t);resolve();};ws.onerror=()=>{clearTimeout(t);reject(new Error("Browser connection failed"));};});
  let seq=0;const pending=new Map<number,{resolve:(v:any)=>void;reject:(e:Error)=>void}>();
  const send=(method:string,params:Record<string,unknown>={},sessionId?:string)=>new Promise<any>((resolve,reject)=>{
    const id=++seq;pending.set(id,{resolve,reject});
    const msg:any={id,method,params};if(sessionId)msg.sessionId=sessionId;
    try{ws.send(JSON.stringify(msg));}catch(e){pending.delete(id);reject(e);}
    setTimeout(()=>{const p=pending.get(id);if(p){pending.delete(id);p.reject(new Error("CDP command timeout: "+method));}},12000);
  });
  ws.onmessage=async(event)=>{
    let msg:any;try{msg=JSON.parse(event.data);}catch{return;}
    if(typeof msg.id==="number"&&pending.has(msg.id)){const p=pending.get(msg.id)!;pending.delete(msg.id);msg.error?p.reject(new Error(msg.error.message||"CDP error")):p.resolve(msg.result||{});return;}
    if(msg.method==="Fetch.requestPaused"){
      const requestId=msg.params?.requestId;const requestUrl=msg.params?.request?.url||"";
      let ok=false;try{const u=new URL(requestUrl);ok=u.protocol==="https:"&&allowedHost(u.hostname.toLowerCase(),domains);}catch{}
      try{await send(ok?"Fetch.continueRequest":"Fetch.failRequest",ok?{requestId}:{requestId,errorReason:"BlockedByClient"},msg.sessionId);}catch{}
    }
  };
  try{
    const targets=await send("Target.getTargets");
    const page=(targets.targetInfos||[]).find((t:any)=>t.type==="page");
    if(!page)throw new Error("No browser page target available");
    const attached=await send("Target.attachToTarget",{targetId:page.targetId,flatten:true});
    const sid=attached.sessionId;
    await send("Page.enable",{},sid);
    await send("Runtime.enable",{},sid);
    await send("Fetch.enable",{patterns:[{urlPattern:"*"}]},sid);
    return await operation(send,sid);
  }finally{try{ws.close();}catch{}}
}
async function evaluate(send:any,sid:string,expression:string){
  const r=await send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true},sid);
  if(r.exceptionDetails)throw new Error(r.exceptionDetails.text||"Page evaluation failed");
  return r.result?.value;
}
async function openBrowser(args:any){
  const domains=validateAllowlist(args.allowedDomains);
  const url=validateUrl(args.url,domains);
  const session=await createRemoteSession();
  try{
    const result=await withCdp(session.connectUrl,domains,async(send,sid)=>{
      await send("Page.navigate",{url},sid);
      await new Promise(r=>setTimeout(r,1200));
      return {title:await evaluate(send,sid,"document.title"),url:await evaluate(send,sid,"location.href")};
    });
    let liveViewUrl=null;
    try{const debug=await bbFetch("/v1/sessions/"+session.id+"/debug",{method:"GET"});liveViewUrl=debug.debuggerFullscreenUrl||null;}catch{}
    return textResult({status:"opened",sessionId:await signSession(session.id,domains),title:result.title||"",url:result.url||url,liveViewUrl});
  }catch(e){try{await bbFetch("/v1/sessions/"+session.id,{method:"POST",body:JSON.stringify({status:"REQUEST_RELEASE"})});}catch{}throw e;}
}
async function callTool(name:string,args:any){
  if(name==="browser_session_open")return await openBrowser(args);
  const s=await readSession(args.sessionId);
  if(name==="browser_session_close"){await bbFetch("/v1/sessions/"+s.id,{method:"POST",body:JSON.stringify({status:"REQUEST_RELEASE"})});return textResult({status:"closed"});}
  return await withCdp((await bbFetch("/v1/sessions/"+s.id,{method:"GET"})).connectUrl,s.domains,async(send,sid)=>{
    if(name==="browser_session_navigate"){
      const url=validateUrl(args.url,s.domains);await send("Page.navigate",{url},sid);await new Promise(r=>setTimeout(r,1000));
      return textResult({url:await evaluate(send,sid,"location.href"),title:await evaluate(send,sid,"document.title")});
    }
    if(name==="browser_session_snapshot"){
      const result:any={url:await evaluate(send,sid,"location.href"),title:await evaluate(send,sid,"document.title"),text:String(await evaluate(send,sid,"document.body?.innerText||''")||"").slice(0,MAX_TEXT)};
      if(args.includeHtml)result.html=String(await evaluate(send,sid,"document.documentElement.outerHTML")||"").slice(0,MAX_TEXT);
      return textResult(result);
    }
    if(["browser_session_click","browser_session_type","browser_session_press"].includes(name)&&args.allowSideEffects!==true)return textResult({status:"approval_required",steps:0,message:"Explicit allowSideEffects=true is required."});
    if(name==="browser_session_click"){
      if(typeof args.selector!=="string"||args.selector.length>1000)throw new Error("Invalid selector");
      return textResult(await evaluate(send,sid,`(()=>{const e=document.querySelector(${JSON.stringify(args.selector)});if(!e)return {clicked:false,reason:"not_found"};e.click();return {clicked:true,tag:e.tagName};})()`));
    }
    if(name==="browser_session_type"){
      if(typeof args.selector!=="string"||args.selector.length>1000||typeof args.text!=="string"||args.text.length>10000)throw new Error("Invalid selector or text");
      return textResult(await evaluate(send,sid,`(()=>{const e=document.querySelector(${JSON.stringify(args.selector)});if(!e)return {typed:false,reason:"not_found"};e.focus();const p=e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const set=Object.getOwnPropertyDescriptor(p,"value")?.set;if(set&&"value" in e)set.call(e,${JSON.stringify(args.text)});else e.textContent=${JSON.stringify(args.text)};e.dispatchEvent(new Event("input",{bubbles:true}));e.dispatchEvent(new Event("change",{bubbles:true}));return {typed:true};})()`));
    }
    if(name==="browser_session_press"){
      const keys:any={ENTER:"Enter",TAB:"Tab",ESCAPE:"Escape",BACKSPACE:"Backspace",ARROWDOWN:"ArrowDown",ARROWUP:"ArrowUp",ARROWLEFT:"ArrowLeft",ARROWRIGHT:"ArrowRight",SPACE:" "};
      const key=keys[String(args.key||"").toUpperCase()];if(!key)throw new Error("Unsupported key");
      await send("Input.dispatchKeyEvent",{type:"keyDown",key},sid);await send("Input.dispatchKeyEvent",{type:"keyUp",key},sid);return textResult({pressed:key});
    }
    if(name==="browser_session_screenshot"){
      const result=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false},sid);
      if(!result.data||result.data.length>4_000_000)throw new Error("Screenshot exceeds size limit");
      return textResult({mimeType:"image/png"},[{type:"image",data:result.data,mimeType:"image/png"}]);
    }
    throw new Error("Unknown browser tool");
  });
}
Deno.serve(async(req:Request)=>{
  const url=new URL(req.url);
  if(req.method==="OPTIONS")return new Response(null,{status:204,headers:HEADERS});
  if(url.pathname==="/health"&&req.method==="GET")return json({status:"ok",service:"flybrain-browserbase-staging",browserbaseConfigured:Boolean(Deno.env.get("BROWSERBASE_API_KEY")),accessTokenConfigured:Boolean(Deno.env.get("FLYBRAIN_BROWSER_ACCESS_TOKEN")),sessionSigningConfigured:Boolean((Deno.env.get("FLYBRAIN_SESSION_SIGNING_KEY")||"").length>=32)});
  if(url.pathname!=="/mcp")return json({error:"not_found"},404);
  if(req.method!=="POST")return new Response(null,{status:405,headers:{...HEADERS,allow:"POST, OPTIONS"}});
  if(!isAuthorized(req))return json({error:"unauthorized"},401);
  const raw=await req.text();if(new TextEncoder().encode(raw).length>MAX_BODY)return json({error:"request_too_large"},413);
  let input:any;try{input=JSON.parse(raw);}catch{return json({error:"invalid_json"},400);}
  if(!input||input.jsonrpc!=="2.0"||typeof input.method!=="string")return json({error:"invalid_json_rpc"},400);
  if(input.method==="initialize")return rpc(input.id,{protocolVersion:"2025-03-26",capabilities:{tools:{listChanged:false}},serverInfo:{name:"flybrain-browserbase-staging",version:"0.1.0"},instructions:"Guarded Browserbase Chromium. HTTPS hostname allowlists are enforced for all intercepted requests. Click, type and keypress require allowSideEffects=true. Session handles expire after 15 minutes. Close sessions promptly."});
  if(input.method==="ping")return rpc(input.id,{});
  if(input.method==="tools/list")return rpc(input.id,{tools});
  if(input.method==="notifications/initialized"||input.method.startsWith("notifications/"))return new Response(null,{status:202,headers:HEADERS});
  if(input.method==="tools/call"){
    const name=input.params?.name;if(!tools.some(t=>t.name===name))return rpcError(input.id,-32602,"Unknown browser tool");
    try{return rpc(input.id,await callTool(name,input.params?.arguments||{}));}
    catch(e){return rpc(input.id,{content:[{type:"text",text:e instanceof Error?e.message:"Browser operation failed"}],isError:true});}
  }
  return rpcError(input.id,-32601,"Method not found");
});
