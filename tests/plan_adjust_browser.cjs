// Eltern passen das Lernpensum auf der Familienkarte an (D214): weniger, mehr,
// streichen, hinzufügen, zurücksetzen; der nächste Schultag als eigener Reiter.
// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const p=req.url.split('?')[0];const file=path.join(root,p==='/'?'index.html':p);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4185,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
page.setDefaultTimeout(6000);
await page.clock.install({time:new Date('2026-09-26T14:00:00+02:00')});
const step=(key,title,subject,done=false,by_parent=false)=>({key,kind:'paper',title,subject,exam_date:subject==='Mathematik'?'2026-09-28':'2026-10-05',format:'kurz',done,skipped:false,by_parent});
let steps=[step('m1','Probearbeit Mathematik','Mathematik',true),step('m2','Kurztest Mathematik: Gleichungen','Mathematik'),step('m3','Kurztest Mathematik: Wertetabellen','Mathematik')];
let cands=[step('mu','Einstiegstest Musik','Musik')];let changes=[];const posts=[];
const day=()=>({day:'2026-09-25',label:'Liste vom Freitag (gilt bis zum nächsten Schultag)',frozen:true,steps,open:steps.filter(s=>!s.done).length,total:steps.length,candidates:cands,changes});
const next={day:'2026-09-28',label:'Nächster Schultag, Montag 28.09.',frozen:false,steps:[],open:0,total:0,candidates:[],changes:[]};
await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};
 if(u==='/api/me')body={id:1,role:'parent',accounts:[{id:1,name:'Kind A'}]};
 else if(u==='/api/dashboard')body={today:'2026-09-26',kids:[{account_id:1,name:'Kind A',board:{status:{level:'warn',label:'Nachsteuern',reasons:[]},evening:false,ok:[],acute:[],exams:[],later:[],watch:[]},
   rings:{next_school_day:'2026-09-28',carry_day:'2026-09-25',tasks:{done:1,total:1},study:{done:1,total:3,tight:[],carry:'2026-09-25'},bag:null,feedback:{done:0,total:0}}}]};
 else if(u.endsWith('/study-plan/adjust')&&req.method()==='GET')body={days:[day(),next]};
 else if(u.endsWith('/study-plan/adjust')){const b=req.postDataJSON();posts.push(b);
   if(b.action==='less'){const last=[...steps].reverse().find(s=>!s.done);steps=steps.filter(s=>s!==last);cands=[last,...cands];changes.push({action:'drop',title:last.title,at:'2026-09-26T14:01:00+02:00',by:'Elternteil'});}
   else if(b.action==='add'){const c=cands.find(x=>x.key===b.key);cands=cands.filter(x=>x!==c);steps=[...steps,{...c,by_parent:true}];changes.push({action:'add',title:c.title,at:'2026-09-26T14:02:00+02:00',by:'Elternteil'});}
   else if(b.action==='drop'){const s=steps.find(x=>x.key===b.key);steps=steps.filter(x=>x!==s);changes.push({action:'drop',title:s.title,at:'2026-09-26T14:03:00+02:00',by:'Elternteil'});}
   else if(b.action==='reset'){steps=[step('m1','Probearbeit Mathematik','Mathematik',true),step('m2','Kurztest Mathematik: Gleichungen','Mathematik'),step('m3','Kurztest Mathematik: Wertetabellen','Mathematik')];cands=[step('mu','Einstiegstest Musik','Musik')];changes=[];}
   body=b.day==='2026-09-25'?day():next;}
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});});
await page.goto('http://127.0.0.1:4185/#/overview');
await page.getByRole('button',{name:'Lernen anpassen'}).click();
const sheet=page.getByRole('dialog',{name:'Lernen anpassen'});await sheet.waitFor();
await sheet.getByText('2 offen von 3 Schritten',{exact:false}).waitFor();
assert.equal(await sheet.getByRole('tab').count(),2);
await sheet.getByRole('button',{name:'Einen Schritt weniger'}).click();
await sheet.getByText('1 offen von 2 Schritten',{exact:false}).waitFor();
assert.deepEqual(posts.at(-1),{day:'2026-09-25',action:'less',key:null});
assert.match(await sheet.locator('.log').innerText(),/Wertetabellen gestrichen \(Elternteil\)/);
await sheet.getByRole('button',{name:/Weitere hinzufügen \(2\)/}).click();
await sheet.getByRole('button',{name:'Einstiegstest Musik hinzufügen'}).click();
await sheet.getByText('von Eltern').waitFor();
await sheet.getByRole('button',{name:'Kurztest Mathematik: Gleichungen streichen'}).click();
await sheet.getByText('1 offen von 2 Schritten',{exact:false}).waitFor();
assert.equal(await sheet.getByRole('button',{name:/Probearbeit Mathematik streichen/}).count(),0,'Erledigtes lässt sich nicht streichen');
await sheet.getByRole('button',{name:'Zurücksetzen'}).click();
await sheet.getByText('2 offen von 3 Schritten',{exact:false}).waitFor();
await sheet.getByRole('tab',{name:/Nächster Schultag/}).click();
await sheet.getByText('steht noch nicht fest',{exact:false}).waitFor();
assert.ok(await sheet.getByRole('button',{name:'Einen Schritt weniger'}).isDisabled());
const box=await sheet.boundingBox();assert.ok(box.width<=390,'passt aufs Telefon');
await sheet.getByRole('button',{name:'Fertig'}).click();
await sheet.waitFor({state:'detached'});
assert.deepEqual(errors,[]);
console.log('PASS: parents adjust the plan: fewer, more from the list, drop, reset, next school day tab; phone width; no JS errors');
}finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
