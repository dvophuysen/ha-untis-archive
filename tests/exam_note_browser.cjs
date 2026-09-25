// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
// Sprechprüfung (D193): erkannt, Hinweise und Sprechthemen der Eltern direkt an der Arbeit, kein Papierweg.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4181,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 async function run(role){
  const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.clock.install({time:new Date('2026-09-25T15:00:00+02:00')});
  let note='',topics=[{id:5,title:'Simple past',origin:'assumed',stage:'neu',stale:0,places:[],self_view:null}];const posted=[];
  await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),u=url.pathname;let body={};
   if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role,is_admin:false};
   else if(u.endsWith('/exams/all'))body={upcoming:[{exam_key:'k1',date:'2026-10-01',subject_name:'ENGLISCH',title:'Sprechprüfung Englisch Jg.6 (Klausur)',oral:true,note,topics,stages:{neu:topics.length},sources:{notice:false},scope:{since:'2026-08-01',parts:1,topics:[]}}],past:[],archived_count:0};
   else if(u.endsWith('/exams/note')){const b=req.postDataJSON();note=b.note;posted.push(['note',b]);body={oral:true,note};}
   else if(u.endsWith('/exams/topics')&&req.method()==='POST'){const b=req.postDataJSON();posted.push(['topic',b]);const t={id:10+topics.length,title:b.title,detail:b.detail,origin:'manual',stage:'neu',stale:0,places:[],self_view:null};topics=[...topics.map(x=>x.origin==='assumed'?{...x,stale:1}:x),t];body=t;}
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('http://127.0.0.1:4181/#/klausuren');
  await page.getByText('Sprechprüfung',{exact:true}).first().waitFor({timeout:8000}).catch(async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
  assert.equal(await page.getByText('ablegen',{exact:true}).count(),0,'kein rätselhaftes Ablegen');
  return {page,errors,posted,get note(){return note;}};
 }
 // Eltern: direkt eintragen.
 const p=await run('parent');
 await p.page.getByText(/noch keine Sprechthemen eingetragen/).waitFor();
 await p.page.getByRole('button',{name:'eintragen',exact:true}).click();
 await p.page.getByRole('textbox',{name:/Hinweise zur Arbeit/}).fill('Sich vorstellen, Hobbys, Ferien; Bild beschreiben');
 await p.page.getByRole('textbox',{name:/Sprechthemen ergänzen/}).fill('Meine Familie: Personen beschreiben\nHobbys');
 await p.page.getByRole('button',{name:'Speichern',exact:true}).click();
 await p.page.getByText('Gespeichert.').waitFor();
 assert.deepEqual(p.posted.map(x=>x[0]),['note','topic','topic']);
 assert.deepEqual(p.posted[1][1],{exam_key:'k1',subject:'ENGLISCH',title:'Meine Familie',detail:'Personen beschreiben'});
 await p.page.getByText(/2 Sprechthemen eingetragen/).waitFor();
 assert.equal(await p.page.getByText('Übungsarbeit wie in echt').count(),0,'kein Papierweg bei der Sprechprüfung');
 await p.page.setViewportSize({width:320,height:800});assert.equal(await p.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320');
 assert.deepEqual(p.errors,[]);
 // Kind: liest die Hinweise, kein Eingabefeld.
 const k=await run('child');
 await k.page.evaluate(()=>0);
 assert.equal(await k.page.getByRole('textbox',{name:/Hinweise zur Arbeit/}).count(),0);
 assert.deepEqual(k.errors,[]);
 console.log('PASS: speaking exam recognised, notes and topic lines saved by parents, no paper path, child without editor, 320/390 px');
 await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
