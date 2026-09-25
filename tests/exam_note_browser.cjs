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
  let off=[];let verdict=null;let note='',topics=[{id:5,title:'Simple past',origin:'assumed',stage:'neu',stale:0,places:[],self_view:null}];const posted=[];
  await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),u=url.pathname;let body={};
   if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role,is_admin:false};
   else if(u.endsWith('/exams/all'))body={upcoming:[{exam_key:'k1',date:'2026-10-01',subject_name:'ENGLISCH',title:'Sprechprüfung Englisch Jg.6 (Klausur)',oral:true,note,topics,references:[{key:'topic:5',label:'Simple past · Vergangenheit',kind:'topic',checked:!off.includes('topic:5')},{key:'vocab:u1',label:'Vokabeln Unit 1',kind:'vocab',checked:!off.includes('vocab:u1')}],
     oral_sims:[{id:7,session_id:60,created_at:'2026-09-25T15:00:00',topic_title:'Meine Familie',full:false,reliable:true,scores:[{criterion:'wortschatz',label:'Wortschatz',score:3},{criterion:'grammatik',label:'Grammatik',score:2}],weak_spots:[{label:'has statt have'}],verdict:null}],stages:{neu:topics.length},sources:{notice:false},scope:{since:'2026-08-01',parts:1,topics:[]}}],past:[],archived_count:0};
   else if(u.endsWith('/oral-sims/7/verdict')){verdict=req.postDataJSON().verdict;body={ok:true};}
   else if(u.endsWith('/exams/note')){const b=req.postDataJSON();note=b.note;if(b.excluded_refs)off=b.excluded_refs;posted.push(['note',b]);body={oral:true,note};}
   else if(u.endsWith('/exams/topics')&&req.method()==='POST'){const b=req.postDataJSON();posted.push(['topic',b]);const t={id:10+topics.length,title:b.title,detail:b.detail,origin:'manual',stage:'neu',stale:0,places:[],self_view:null};topics=[...topics.map(x=>x.origin==='assumed'?{...x,stale:1}:x),t];body=t;}
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('http://127.0.0.1:4181/#/klausuren');
  await page.getByText('Sprechprüfung',{exact:true}).first().waitFor({timeout:8000}).catch(async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
  assert.equal(await page.getByText('ablegen',{exact:true}).count(),0,'kein rätselhaftes Ablegen');
  return {page,errors,posted,get note(){return note;},get off(){return off;},get verdict(){return verdict;}};
 }
 // Eltern: direkt eintragen.
 const p=await run('parent');
 await p.page.getByText(/noch keine Sprechthemen eingetragen/).waitFor();
 await p.page.getByRole('button',{name:'eintragen',exact:true}).click();
 await p.page.getByRole('textbox',{name:/Hinweise zur Arbeit/}).fill('Sich vorstellen, Hobbys, Ferien; Bild beschreiben');
 await p.page.getByRole('textbox',{name:/Sprechthemen ergänzen/}).fill('Meine Familie: Personen beschreiben\nHobbys');
 const ref=p.page.getByRole('checkbox',{name:/Simple past/});assert.equal(await ref.isChecked(),true,'voreingestellt angekreuzt');await ref.uncheck();
 await p.page.getByRole('button',{name:'Speichern',exact:true}).click();
 await p.page.getByText('Gespeichert.').waitFor();
 assert.deepEqual(p.posted.map(x=>x[0]),['note','topic','topic']);
 assert.deepEqual(p.off,['topic:5'],'abgewählte Referenz gespeichert');
 await p.page.getByText(/Grammatik 2/).waitFor();await p.page.getByText('Baustellen: has statt have').waitFor();
 await p.page.getByRole('button',{name:'zu streng'}).click();await p.page.waitForFunction(()=>document.querySelector('.feel.active')?.textContent==='zu streng');assert.equal(p.verdict,'streng');
 assert.equal(await p.page.locator('a[href^="#/learning?oral="]').count(),3,'Gesamtprobe und je Thema eine');
 assert.deepEqual(p.posted[1][1],{exam_key:'k1',subject:'ENGLISCH',title:'Meine Familie',detail:'Personen beschreiben'});
 await p.page.getByText(/2 Sprechthemen eingetragen/).waitFor();
 assert.equal(await p.page.getByText('Übungsarbeit wie in echt').count(),0,'kein Papierweg bei der Sprechprüfung');
 await p.page.setViewportSize({width:320,height:800});assert.equal(await p.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320');
 assert.deepEqual(p.errors,[]);
 // Kind: liest die Hinweise, kein Eingabefeld.
 const k=await run('child');
 await k.page.evaluate(()=>0);
 assert.equal(await k.page.getByRole('textbox',{name:/Hinweise zur Arbeit/}).count(),0);
 await k.page.getByRole('button',{name:'ansehen',exact:true}).click();await k.page.getByText('Bisherige Sprechproben').waitFor();
 assert.equal(await k.page.getByRole('button',{name:'zu streng'}).count(),0,'Kalibrieren nur für Eltern');
 assert.deepEqual(k.errors,[]);
 console.log('PASS: speaking exam recognised, notes, topic lines and references saved by parents, simulations with verdict, no paper path, child without editor, 320/390 px');
 await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
