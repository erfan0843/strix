import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { JSDOM } from 'jsdom';

const read=name=>fs.readFileSync(new URL(name,import.meta.url),'utf8');
const apiSource=read('owner-api.js');

for(const [status,code] of [[0,'server_unreachable'],[400,'invalid_payload'],[401,'account_session_required'],
  [403,'permission_denied'],[404,'form_not_found'],[409,'response_draft_account_mismatch'],
  [413,'request_too_large'],[422,'invalid_answers'],[429,'rate_limited'],[503,'database_not_configured'],
  [500,'unknown_error'],[400,'__proto__']]){
  test(`Persian API message preserves the machine contract: ${status}/${code}`,async()=>{
    const payload={detail:{code}},calls=[];
    const window={document:{cookie:''},fetch:async(path,options)=>{
      calls.push({path,options});if(status===0)throw new Error('private connection details');
      return {ok:false,status,json:async()=>payload};
    }};
    vm.runInNewContext(apiSource,{window});
    await assert.rejects(window.NORA_SERVER_API.accountMe(),error=>{
      assert.equal(error.name,'OwnerApiError');assert.equal(error.status,status);assert.equal(error.code,code);
      assert.match(error.message,/[آ-ی]/);assert.ok(!error.message.includes(code));
      if(status!==0)assert.equal(error.payload,payload);
      return true;
    });
    assert.equal(calls.length,1);assert.equal(calls[0].path,'/api/account/me');
    assert.equal(calls[0].options.method,'GET');assert.equal(calls[0].options.credentials,'same-origin');
    assert.equal(calls[0].options.redirect,'error');
  });
}

test('All Nora documents remain Persian RTL with unique titles, descriptions, favicon, and image alternatives',()=>{
  const titles=new Set();
  for(const name of fs.readdirSync(new URL('.',import.meta.url)).filter(n=>n.endsWith('.html'))){
    const doc=new JSDOM(read(name)).window.document;
    assert.equal(doc.documentElement.lang,'fa',name);assert.equal(doc.documentElement.dir,'rtl',name);
    assert.ok(doc.title.trim(),name);assert.ok(!titles.has(doc.title),name);titles.add(doc.title);
    assert.ok(doc.querySelector('meta[name="description"]')?.content.trim(),name);
    assert.ok(doc.querySelector('link[rel="icon"]'),name);
    assert.equal(doc.querySelectorAll('img:not([alt])').length,0,name);
  }
});

test('Measured unnamed form controls now have Persian names and associated labels',()=>{
  const builder=new JSDOM(read('builder.html')).window.document;
  for(const id of ['setCap','setPer','setSlug'])assert.ok(builder.querySelector(`label[for="${id}"]`),id);
  assert.equal(builder.getElementById('setWait').tabIndex,0);
  assert.equal(builder.getElementById('setWait').getAttribute('aria-label'),'لیست انتظار');
  const create=new JSDOM(read('create.html')).window.document;
  for(const id of ['fgReq','fdReq','fdProf','fdCol','fdDelete'])assert.match(create.getElementById(id).getAttribute('aria-label'),/[آ-ی]/,id);
  assert.equal(create.querySelector('[data-copy="#slugView"]').getAttribute('aria-label'),'کپی پیوند فرم');
  assert.equal(new JSDOM(read('loading-preview.html')).window.document.querySelector('.loader-timer').getAttribute('role'),'timer');
});

test('Production account does not load the unrelated fixture dataset; explicit fixtures remain available',()=>{
  const html=read('account.html'),doc=new JSDOM(html).window.document;
  assert.equal(doc.querySelector('script[src^="data.js"]'),null);
  const gate=[...doc.querySelectorAll('script:not([src])')].find(s=>s.textContent.includes('data.js'));
  assert.ok(gate);const writes=[];
  for(const mode of [undefined,false,true]){
    const window={__NORA_TEST_FIXTURE_MODE__:mode},document={write:value=>writes.push(value)};
    vm.runInNewContext(gate.textContent,{window,document});
    assert.equal(writes.length,mode===true?1:0);
  }
  assert.match(writes[0],/data\.js\?v=100/);
  assert.match(read('account.js'),/TEST_FIXTURE_MODE\?\(A\.sections\|\|\[\]\):SERVER_SECTIONS/);
  assert.ok(fs.statSync(new URL('data.js',import.meta.url)).size>0);
});

test('Redistribution terms for every local font family are shipped without replacing font assets',()=>{
  for(const name of ['LICENSE-Estedad.txt','LICENSE-Vazirmatn.txt'])assert.match(read('fonts/'+name),/SIL OPEN FONT LICENSE Version 1\.1/);
  assert.match(read('fonts/LICENSE-Nora-Latin.txt'),/Permission is hereby granted/);
  assert.match(read('fonts/LICENSE-Nora-Latin.txt'),/Tavmjong/);
});
