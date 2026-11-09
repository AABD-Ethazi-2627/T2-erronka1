import {spawn} from 'node:child_process';
import {mkdtempSync,readFileSync,writeFileSync,readdirSync,mkdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=dirname(fileURLToPath(import.meta.url)),out=join(root,'verificacion');mkdirSync(out,{recursive:true});
const data=JSON.parse(readFileSync(join(root,'datos-revisados.json'),'utf8'));
const fmt=x=>Number(x).toLocaleString('es-ES',{minimumFractionDigits:0,maximumFractionDigits:0});
const profile=mkdtempSync(join(tmpdir(),'cnc-report-v4-'));
const chrome=spawn('/usr/lib/chromium/chromium',['--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--remote-debugging-port=0',`--user-data-dir=${profile}`,'about:blank'],{stdio:['ignore','ignore','pipe']});
let ws;const errors=[],requests=[],checks=[];
function assert(ok,msg){if(!ok)throw Error(msg);checks.push(msg)}
try{
 const browserUrl=await new Promise((resolve,reject)=>{let buf='';const timer=setTimeout(()=>reject(Error('Chrome startup timeout')),15000);chrome.stderr.on('data',b=>{buf+=b;const m=buf.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(m){clearTimeout(timer);resolve(m[1])}});chrome.once('exit',code=>reject(Error('Chrome exited '+code)))});
 const port=new URL(browserUrl).port;
 const targets=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();ws=new WebSocket(targets.find(x=>x.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let id=0;const pending=new Map();const events=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result)}else{if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails);if(m.method==='Network.requestWillBeSent')requests.push(m.params.request.url);const q=events.get(m.method);if(q){events.delete(m.method);q(m.params)}}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const next=++id;pending.set(next,{resolve,reject});ws.send(JSON.stringify({id:next,method,params}))});
 const ev=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text+': '+JSON.stringify(r.exceptionDetails.exception));return r.result.value};
 const change=(id,value)=>ev(`document.getElementById(${JSON.stringify(id)}).value=${JSON.stringify(String(value))};document.getElementById(${JSON.stringify(id)}).dispatchEvent(new Event('change',{bubbles:true}));true`);
 const input=(id,value)=>ev(`document.getElementById(${JSON.stringify(id)}).value=${JSON.stringify(String(value))};document.getElementById(${JSON.stringify(id)}).dispatchEvent(new Event('input',{bubbles:true}));true`);
 const view=async name=>{await ev(`document.querySelector('nav [data-view="${name}"]').click();true`)};
 const shot=async name=>{const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});writeFileSync(join(out,name+'.png'),Buffer.from(r.data,'base64'))};
 await call('Page.enable');await call('Runtime.enable');await call('Network.enable');await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 const loaded=new Promise(r=>events.set('Page.loadEventFired',r));await call('Page.navigate',{url:'file://'+join(root,'reunion.html')});await loaded;
 await ev(`Promise.all([...document.images].map(x=>x.decode().catch(()=>{}))).then(()=>true)`);
 assert(await ev(`document.title.includes('sincronización')`),'Page loads and JavaScript initializes');
 assert(await ev(`document.querySelectorAll('main>section').length===7`),'Seven report sections');
 assert((await ev(`document.getElementById('leadUncertainty').textContent`)).includes(fmt(data.uncertainty.comparisons.find(x=>x.procedure==='pair').delta_cost_ci95[0])),'Policy A uncertainty uses its own interval');
 await shot('escritorio-inicio');
 await ev(`document.getElementById('mode').click();document.getElementById('project').click();true`);
 assert(await ev(`!document.body.classList.contains('brief')&&document.body.classList.contains('projector')`),'Detail and projector modes toggle');
 await ev(`document.getElementById('project').click();true`);
 await view('models');
 for(const scenario of data.scenarios){await change('scenario',scenario.id);const text=await ev(`document.getElementById('scenarioTable').innerText`);const r=data.sensitivity.find(x=>x.scenario===scenario.id&&x.procedure==='pair');assert(text.includes(fmt(r.cost_per_1000)),`Executed scenario ${scenario.id}: displayed cost`)}
 await change('scenario','base');await shot('escritorio-modelos');
 for(const x of data.uncertainty.comparisons){await change('uncertaintyChoice',x.procedure);const t=await ev(`document.getElementById('uncertaintyResult').innerText`);assert(t.includes(fmt(x.delta_cost_ci95[0]))&&t.includes(fmt(x.delta_cost_ci95[1])),`Policy A interval ${x.procedure}`)}
 await change('uncertaintyChoice','pair');
 for(const policy of ['A','B','C']){await change('policy',policy);assert(await ev(`document.querySelectorAll('#allMethods tbody tr').length===7`),`Seven procedures for policy ${policy}`)}
 await change('policy','A');await input('priceFN','10000');assert((await ev(`document.getElementById('frozenResult').innerText`)).includes('51.679'),'Custom price revalues fixed A decisions');
 await input('priceFN','');assert((await ev(`document.getElementById('frozenResult').innerText`)).includes('finitos'),'Invalid cost shows validation message');
 await ev(`document.getElementById('resetPrices').click();true`);
 assert((await ev(`document.getElementById('frozenResult').innerText`)).includes('32.036'),'Reset restores exercise matrix');
 await view('capacity');
 for(const budget of [10,20,30,50,100]){await change('budget',budget);const text=await ev(`document.getElementById('capacityResult').innerText`);assert(budget<=20?text.includes('No hay política factible'):text.includes('tres particiones'),`Budget ${budget}: feasibility state`)}
 await change('budget',20);await shot('escritorio-no-factible');await change('budget',50);
 await view('services');
 for(let i=0;i<12;i++){await change('serviceChoice',i);assert(await ev(`document.querySelector('#serviceCard img').decode().then(()=>document.querySelector('#serviceCard img').naturalWidth>0)`),`Service diagram ${i+1} loads`)}
 for(let i=0;i<5;i++){await change('captureChoice',i);assert(await ev(`document.getElementById('captureImage').decode().then(()=>document.getElementById('captureImage').naturalWidth>0)`),`Historical capture ${i+1} loads`)}
 await change('serviceChoice',4);await shot('escritorio-servicio');
 await view('data');for(let i=0;i<data.cases.length;i++){await change('caseChoice',i);assert((await ev(`document.getElementById('caseDetail').innerText`)).includes(String(data.cases[i].row)),`Source-backed case ${i+1}`)}
 await view('rubric');await change('rubricArea','ML');assert(await ev(`document.querySelectorAll('#rubricTable tbody tr').length===14`),'Rubric area filter');await input('rubricSearch','ZZZ-NO-CRITERIO');assert((await ev(`document.getElementById('rubricTable').innerText`)).includes('No hay criterios'),'Rubric no-results state');await change('rubricArea','');await input('rubricSearch','');assert(await ev(`document.querySelectorAll('#rubricTable tbody tr').length===40`),'All 40 rubric criteria restored');
 await view('closing');await ev(`document.querySelector('#closing [data-source="quality"]').click();true`);assert(await ev(`document.getElementById('sourceDialog').open&&document.getElementById('sourceContent').textContent.includes('negative_with_any_subtype')`),'Source dialog exposes reviewed data');await ev(`document.getElementById('closeSource').click();true`);
 const downloads=join(out,'descargas-prueba');mkdirSync(downloads,{recursive:true});await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloads});await input('meetingVersion','VERSION-PRUEBA');await input('meetingObjective','BORRADOR DE PRUEBA, NO ACUERDO');await input('meetingActions','Prueba de descarga');await ev(`document.getElementById('exportDraft').click();true`);
 await new Promise(r=>setTimeout(r,500));const draft=JSON.parse(readFileSync(join(downloads,'cnc-guard-borrador-acuerdos.json'),'utf8'));assert(draft.version==='VERSION-PRUEBA'&&draft.status.includes('no acredita'),'Draft download preserves entered text and draft status');
 await ev(`document.getElementById('downloadData').click();true`);await new Promise(r=>setTimeout(r,500));assert(JSON.parse(readFileSync(join(downloads,'cnc-guard-datos-revisados.json'),'utf8')).sensitivity.length===27,'Data download contains reviewed scenarios');
 await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 for(const name of ['briefing','models','capacity','services','data','rubric','closing']){await view(name);assert(await ev(`document.documentElement.scrollWidth<=window.innerWidth+1`),`Mobile ${name}: no page overflow`);if(['briefing','models','services'].includes(name))await shot('movil-'+name)}
 assert(errors.length===0,'No JavaScript runtime exceptions');assert(requests.filter(x=>/^https?:/.test(x)).length===0,'No external HTTP requests');
 writeFileSync(join(out,'navegador.json'),JSON.stringify({status:'passed',checks,viewports:['1440x1000','390x844'],runtimeErrors:errors,externalRequests:requests.filter(x=>/^https?:/.test(x)),browser:'isolated local Chromium headless over CDP; no server',limits:['not full keyboard/screen-reader/WCAG audit','no service integration or model execution by report','test download is a labelled dummy draft']},null,2));
 console.log(JSON.stringify({status:'passed',checks:checks.length,screenshots:readdirSync(out).filter(x=>x.endsWith('.png'))}));
}catch(e){writeFileSync(join(out,'fallo-navegador.txt'),e.stack);throw e}
finally{ws?.close();chrome.kill('SIGTERM');await new Promise(r=>setTimeout(r,300));try{rmSync(profile,{recursive:true,force:true})}catch{}}
