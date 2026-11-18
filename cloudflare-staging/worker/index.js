/**
 * FlyBrain-NOS / URCAL — Cloudflare MCP bridge
 * Version: 0.16.0-staging
 * Public, read-only retrieval bridge. No write/delete operations.
 */
const REPOSITORY = "ramysaid721-sudo/FlyBrain-Research-Platform";
const BRANCH = "main";
const SOURCES = ["README.md","components/FlyBrain-NOS/README.md","components/URCAL/README.md"];
const JSON_HEADERS = {
  "content-type":"application/json; charset=utf-8",
  "cache-control":"no-store",
  "x-content-type-options":"nosniff",
  "access-control-allow-origin":"*",
  "access-control-allow-methods":"GET, POST, OPTIONS",
  "access-control-allow-headers":"content-type, accept, mcp-session-id, last-event-id"
};
function json(data,status=200,extraHeaders={}) {
  return new Response(JSON.stringify(data),{status,headers:{...JSON_HEADERS,...extraHeaders}});
}
function rpcError(id,code,message) {
  return json({jsonrpc:"2.0",id:id??null,error:{code,message}});
}
function terms(value) {
  return [...new Set((value.toLowerCase().match(/[\\p{L}\\p{N}_-]{3,}/gu)??[]))];
}
async function retrieve(question) {
  const queryTerms=new Set(terms(question)),found=[];
  await Promise.all(SOURCES.map(async path=>{
    const url=`https://raw.githubusercontent.com/${REPOSITORY}/${BRANCH}/${path}`;
    try {
      const response=await fetch(url,{cf:{cacheTtl:300,cacheEverything:true}});
      if(!response.ok)return;
      const body=await response.text();
      const paragraphs=body.split(/\\n\\s*\\n/).map(p=>p.replace(/\\s+/g," ").trim()).filter(p=>p.length>=45);
      for(const paragraph of paragraphs){
        const pTerms=new Set(terms(paragraph));let score=0;
        for(const term of queryTerms)if(pTerms.has(term))score++;
        if(score>0)found.push({source:path,relevance_score:score,excerpt:paragraph.slice(0,1400)});
      }
    } catch {}
  }));
  found.sort((a,b)=>b.relevance_score-a.relevance_score||b.excerpt.length-a.excerpt.length);
  const seen=new Set();
  return found.filter(item=>{const key=item.source+item.excerpt.slice(0,160);if(seen.has(key))return false;seen.add(key);return true;}).slice(0,6);
}
async function handleMcp(request) {
  const contentLength=Number(request.headers.get("content-length")??"0");
  if(contentLength>65536)return json({error:"request_too_large"},413);
  if(!(request.headers.get("content-type")??"").toLowerCase().includes("application/json"))return json({error:"content_type_must_be_application_json"},415);
  let rpc;try{rpc=await request.json();}catch{return json({error:"invalid_json"},400);}
  if(!rpc||rpc.jsonrpc!=="2.0"||typeof rpc.method!=="string")return json({error:"invalid_json_rpc_request"},400);
  if(rpc.id===undefined&&rpc.method.startsWith("notifications/"))return new Response(null,{status:202,headers:JSON_HEADERS});
  if(rpc.method==="initialize"){
    const requested=rpc.params?.protocolVersion;
    const supported=["2024-11-05","2025-03-26","2025-06-18"];
    return json({jsonrpc:"2.0",id:rpc.id,result:{
      protocolVersion:supported.includes(requested)?requested:"2025-03-26",
      capabilities:{tools:{listChanged:false}},
      serverInfo:{name:"flybrain-research-bridge",version:"0.16.0-staging"},
      instructions:"Use ask_flybrain to retrieve source-labelled FlyBrain-NOS and URCAL project context. Distinguish documented evidence from interpretation and hypotheses. This server is public and read-only."
    }});
  }
  if(rpc.method==="ping")return json({jsonrpc:"2.0",id:rpc.id,result:{}});
  if(rpc.method==="tools/list")return json({jsonrpc:"2.0",id:rpc.id,result:{tools:[{
    name:"ask_flybrain",title:"Ask FlyBrain research system",
    description:"Public read-only retrieval of source-labelled FlyBrain-NOS and URCAL project evidence. ChatGPT synthesizes returned excerpts. This tool cannot write, edit, or delete project data.",
    inputSchema:{type:"object",properties:{question:{type:"string",minLength:1,maxLength:12000}},required:["question"],additionalProperties:false},
    annotations:{readOnlyHint:true,openWorldHint:true}
  }]}});
  if(rpc.method==="tools/call"){
    const name=rpc.params?.name,question=rpc.params?.arguments?.question;
    if(name!=="ask_flybrain"||typeof question!=="string"||!question.trim()||question.length>12000)return rpcError(rpc.id,-32602,"Invalid tool or question");
    const research_context=await retrieve(question.trim());
    const result={status:research_context.length?"context_only":"no_matching_context",answer_candidates:[],research_context,
      message:"No external language provider is configured. Use returned project evidence as context and let the connected ChatGPT model synthesize the response.",
      external_data_transfer:false};
    return json({jsonrpc:"2.0",id:rpc.id,result:{content:[{type:"text",text:JSON.stringify(result)}],structuredContent:result,isError:false}});
  }
  return rpcError(rpc.id,-32601,"Method not found");
}
export default {
  async fetch(request,env) {
    const url=new URL(request.url);
    if(request.method==="OPTIONS")return new Response(null,{status:204,headers:JSON_HEADERS});
    if(url.pathname==="/health"&&request.method==="GET")return json({status:"ok",service:"flybrain-cloudflare-worker",version:"0.16.0-staging",mode:"read-only",rate_limiter_binding:Boolean(env?.FLYBRAIN_PUBLIC_LIMITER)});
    if(url.pathname!=="/mcp")return json({error:"not_found"},404);
    if(request.method!=="POST")return new Response(null,{status:405,headers:{...JSON_HEADERS,allow:"POST, OPTIONS"}});
    const limiter=env?.FLYBRAIN_PUBLIC_LIMITER;
    if(!limiter||typeof limiter.limit!=="function")return json({error:"rate_limit_binding_unavailable",diagnostic:"The Worker is running, but FLYBRAIN_PUBLIC_LIMITER is not bound. Add a Cloudflare Rate Limiting binding with this exact variable name.",expected_binding:"FLYBRAIN_PUBLIC_LIMITER"},503);
    try {
      const key=request.headers.get("cf-connecting-ip")??"anonymous";
      const result=await limiter.limit({key});
      if(!result?.success)return json({error:"rate_limit_exceeded",retry_after_seconds:60},429);
    } catch(error) {
      return json({error:"rate_limiter_execution_failed",diagnostic:error instanceof Error?error.message:"Unknown rate limiter error"},503);
    }
    try{return await handleMcp(request);}catch(error){
      return json({error:"mcp_internal_error",diagnostic:error instanceof Error?error.message:"Unknown Worker error"},500);
    }
  }
};