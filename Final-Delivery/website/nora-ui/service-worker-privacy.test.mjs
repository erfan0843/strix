import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source=fs.readFileSync(new URL('sw.js',import.meta.url),'utf8');
const origin='https://nora.example.invalid';
function environment({status=200,headers={},responseUrl='',fail=false}={}){
  const events={},writes=[],deleted=[],added=[],fetches=[];
  const stores=new Map([['unrelated-app',new Map()],['nora-v95',new Map()]]);
  const key=value=>new URL(typeof value==='string'?value:value.url,origin+'/').href;
  const response={ok:status>=200&&status<300,status,url:responseUrl,headers:{get:name=>headers[name.toLowerCase()]||''},clone(){return this}};
  const caches={keys:async()=>[...stores.keys()],delete:async name=>{deleted.push(name);return stores.delete(name)},
    open:async name=>{if(!stores.has(name))stores.set(name,new Map());const store=stores.get(name);return {
      addAll:async requests=>added.push(...requests.map(r=>key(r))),
      put:async(request,res)=>{writes.push(key(request));store.set(key(request),res)},
      match:async request=>store.get(key(request))
    }}};
  const self={addEventListener:(name,handler)=>events[name]=handler,skipWaiting:async()=>{},clients:{claim:async()=>{}}};
  const fetch=async request=>{fetches.push(key(request));if(fail)throw new Error('local network failure');return response};
  class Request{constructor(url,options){this.url=key(url);Object.assign(this,options)}}
  vm.runInNewContext(source,{self,caches,fetch,location:{origin},URL,Request,Promise});
  async function run(name,request){
    const pending=[];let reply;
    const event={request,waitUntil:promise=>pending.push(promise),respondWith:promise=>reply=promise};
    events[name](event);const body=reply?await reply:undefined;await Promise.all(pending);return body;
  }
  return {run,writes,deleted,added,fetches,stores,key};
}

for(const path of ['/api/account/me','/api/owner/site-content','/%61pi/account/me']){
  test(`API navigation never enters the service-worker cache: ${path}`,async()=>{
    const env=environment();await env.run('fetch',{url:origin+path,method:'GET',mode:'navigate'});
    assert.equal(env.fetches.length,0);assert.equal(env.writes.length,0);
  });
}
for(const page of ['account','admin','builder','create','form','login']){
  test(`Private HTML is network-only and never cached: ${page}`,async()=>{
    const env=environment();await env.run('fetch',{url:origin+`/${page}.html`,method:'GET',mode:'navigate'});
    assert.equal(env.fetches.length,1);assert.equal(env.writes.length,0);
  });
}
for(const options of [{status:404},{status:503},{headers:{'cache-control':'private, no-store'}},
  {headers:{vary:'Cookie, Origin'}},{headers:{vary:'*'}},{responseUrl:origin+'/account.html'}]){
  test(`Public navigation obeys status/privacy headers: ${JSON.stringify(options)}`,async()=>{
    const env=environment(options);await env.run('fetch',{url:origin+'/',method:'GET',mode:'navigate'});
    assert.equal(env.fetches.length,1);assert.equal(env.writes.length,0);
  });
}

test('Only successful cookie-independent public responses can be cached',async()=>{
  const env=environment();await env.run('fetch',{url:origin+'/events.html',method:'GET',mode:'navigate'});
  assert.deepEqual(env.writes,[origin+'/events.html']);
});

test('Install does not prefetch invalid detail routes, private shells, or unused JavaScript',async()=>{
  const env=environment();await env.run('install');
  assert.ok(env.added.includes(origin+'/offline.html'));
  assert.equal(env.added.length,6);
  assert.ok(env.added.every(url=>!/(?:account|admin|login|builder|create|form|event|post|person)\.html|\.js/.test(url)));
});

test('Activation removes stale Nora caches without deleting another application',async()=>{
  const env=environment();await env.run('activate');
  assert.deepEqual(env.deleted,['nora-v95']);assert.ok(env.stores.has('unrelated-app'));
});

test('Offline private navigation uses a generic fallback, never an old private response',async()=>{
  const env=environment({fail:true}),cache=new Map();
  const fallback={kind:'generic-offline-fixture'},privateResponse={kind:'private-fixture-not-for-display'};
  cache.set(env.key('offline.html'),fallback);cache.set(env.key('account.html'),privateResponse);
  env.stores.set('nora-v96',cache);
  const reply=await env.run('fetch',{url:origin+'/account.html',method:'GET',mode:'navigate'});
  assert.equal(reply,fallback);assert.equal(env.writes.length,0);
});

test('Query-string navigation is not replaced by another cached query variant',async()=>{
  const env=environment({fail:true}),cache=new Map();const fallback={kind:'generic-offline-fixture'};
  cache.set(env.key('offline.html'),fallback);cache.set(env.key('events.html?q=private-fixture'),{kind:'wrong-query'});
  env.stores.set('nora-v96',cache);
  const reply=await env.run('fetch',{url:origin+'/events.html?q=other',method:'GET',mode:'navigate'});
  assert.equal(reply,fallback);
});
