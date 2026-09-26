// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
// Rückmeldung zum Lernen und Elternprüfung (D207): Das Kind sieht je Aufgabe, was Punkte brachte, wo und warum
// Punkte verloren gingen und wie es sie bekommt; Eltern prüfen jede Arbeit selbst, mit KI-Vorschlag.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4191,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 const cell=(state)=>({state,ratio:null,tasks:0,helped:0});
 const topics=[{id:11,title:'Gleichungen',detail:'',places_label:'',stage:'neu',cells:{'1':cell('offen'),'2':cell('offen'),'3':cell('offen')},level:0,target:1,ready:false}];
 const task=(i)=>({prompt:`Aufgabe ${i}: Löse 3x + 5 = 2x + 11.`,solution:'x = 6',criteria:'2 P Gleichung; 2 P Umformung',skill_title:'Gleichungen',topic_id:11,afb:2,points:4,minutes:5,operator:'Löse'});
 const graded={'0':{points:2.5,uncertain:false,rationale:'Gleichung richtig, Umformung lückenhaft.',next_step:'Jeden Umformungsschritt in eine eigene Zeile schreiben.',transcription:'3x+5=2x+11, x=6',
   earned:[{text:'Gleichung aus der Waage richtig aufgestellt',points:2},{text:'Ergebnis x = 6',points:0.5}],
   lost:[{points:1.5,kind:'rechenweg',why:'Die Umformungsschritte fehlen.',fix:'3x + 5 = 2x + 11 | −2x  →  x + 5 = 11 | −5  →  x = 6'}],model:'3x + 5 = 2x + 11 | −2x\nx + 5 = 11 | −5\nx = 6'},
  '1':{points:0,uncertain:false,rationale:'Nicht bearbeitet.',next_step:'Klammern auflösen üben.',earned:[],lost:[{points:4,kind:'nicht_bearbeitet',why:'Keine Antwort.',fix:'Klammern auflösen: 4x − 8 + 3 = 3x + 2, dann x = 7.'}],model:'x = 7'},
  overall:{text:'Guter Anfang bei einfachen Gleichungen.',strengths:['Gleichungen aus Texten aufstellen'],focus:['Klammern auflösen','Rechenwege aufschreiben']},
  losses:[{kind:'nicht_bearbeitet',label:'Nicht bearbeitet',points:4},{kind:'rechenweg',label:'Rechenweg oder Begründung fehlt',points:1.5}],check:{passes:2,open:[]}};
 async function run(role){
  const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.clock.install({time:new Date('2026-09-25T15:00:00+02:00')});
  const st={feedback:graded,prior:null,saved:null,hint:null};
  const attempt=()=>({id:41,status:'graded',label:'Probearbeit',format:'probe',pages:[101],read_only:false,answers:{},exam:{title:'Probearbeit Gleichungen',minutes:45,tasks:[task(1),task(2)]},feedback:st.feedback,...(st.prior?{prior:st.prior}:{})});
  await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};
   if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role,is_admin:false};
   else if(u.endsWith('/exams/all'))body={upcoming:[{exam_key:'k1',date:'2026-09-28',subject_name:'Mathematik',title:'Mathematik',topics:topics.map(t=>({...t,stale:0,places:[],self_view:null})),stages:{neu:1},sources:null,scope:null}],past:[],archived_count:0};
   else if(u==='/api/accounts/1/practice'&&req.method()==='GET')body={topics,ready:0,total:1,goal_afb:2,afb_names:{'1':'Wiedergeben','2':'Anwenden','3':'Übertragen'},formats:[],papers:[{id:5,attempt_id:41,label:'Probearbeit',created_at:'2026-09-25T15:00:00',status:'graded',points:2.5,points_max:8,tasks:2}]};
   else if(u==='/api/accounts/1/practice/attempts/41')body=attempt();
   else if(u.endsWith('/attempts/41/manual/suggest')){st.hint=req.postDataJSON().hint;body={tasks:{'0':{...graded['0'],points:3,earned:[{text:'Gleichung',points:2},{text:'x = 6',points:1}],lost:[{points:1,kind:'rechenweg',why:'Schritte fehlen.',fix:'−2x, dann −5.'}]},'1':graded['1']},overall:{text:'Vorschlag.',strengths:['Aufstellen'],focus:['Klammern']}};}
   else if(u.endsWith('/attempts/41/manual')){st.saved=req.postDataJSON();st.prior={'0':{points:2.5},'1':{points:0}};st.feedback={...graded,'0':{...graded['0'],...st.saved.tasks['0'],checked_by_parent:true},check:{passes:2,open:[],manual:true}};body=attempt();}
   else if(u.includes('/photos/'))return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=','base64')});
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto('http://127.0.0.1:4191/#/klausuren?exam=k1&paper=41');
  await page.getByText('Probearbeit Gleichungen').first().waitFor({timeout:8000}).catch(async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
  return {page,errors,st};
 }
 // Kind: nachvollziehbare Rückmeldung.
 const kid=await run('child');const k=kid.page;
 await k.getByText('2,5 von 8 Punkten').waitFor();
 await k.getByText('Das kannst du schon').waitFor();
 await k.getByText('Hier sind die meisten Punkte liegen geblieben').waitFor();
 await k.getByText(/−4\s*Nicht bearbeitet/).first().waitFor();
 await k.getByText('Das übst du als Nächstes').waitFor();
 assert.equal(await k.getByText('Das war richtig').count(),1);
 await k.getByText('Gleichung aus der Waage richtig aufgestellt').waitFor();
 assert.equal(await k.getByText('Hier hast du Punkte verloren').count(),2);
 await k.getByText('Die Umformungsschritte fehlen.').waitFor();
 assert.equal(await k.getByText('So hättest du die Punkte bekommen:').count(),2);
 await k.getByText('−1,5').first().waitFor();
 const links=k.getByRole('link',{name:'Mit dem Mentor üben'});
 assert.equal(await links.count(),2);
 assert.equal(await links.first().getAttribute('href'),'#/learning?topic_id=11&redo=41&task=0');
 assert.equal(await k.getByRole('button',{name:'Selbst prüfen'}).count(),0,'Kind prüft nicht selbst');
 await k.setViewportSize({width:320,height:800});assert.equal(await k.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320 Kind');
 assert.deepEqual(kid.errors,[]);
 // Eltern: selbst prüfen mit KI-Vorschlag.
 const par=await run('parent');const p=par.page;
 await p.getByRole('button',{name:'Selbst prüfen'}).click();
 await p.getByText('Ihr bewertet jede Aufgabe.').waitFor();
 assert.equal(await p.getByLabel('Punkte Aufgabe 1').inputValue(),'2.5','vorausgefüllt mit der Bewertung der App');
 await p.getByLabel('Hinweis für die KI (freiwillig)').fill('Aufgabe 1 großzügig.');
 await p.getByRole('button',{name:'KI-Vorschlag holen'}).click();
 await p.getByText('Vorschlag eingetragen.').waitFor();
 assert.equal(par.st.hint,'Aufgabe 1 großzügig.');
 assert.equal(await p.getByLabel('Punkte Aufgabe 1').inputValue(),'3');
 await p.getByLabel('Begründung Aufgabe 1').fill('');
 await p.getByText('Aufgabe 1: Begründung fehlt.').waitFor();
 assert.equal(await p.getByRole('button',{name:'Prüfung speichern'}).isDisabled(),true);
 await p.getByLabel('Begründung Aufgabe 1').fill('Gleichung und Ergebnis richtig, Schritte fehlen.');
 await p.setViewportSize({width:320,height:800});assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320 Elternprüfung');
 await p.getByRole('button',{name:'Prüfung speichern'}).click();
 await p.getByText('Von deinen Eltern geprüft.').waitFor();
 const t0=par.st.saved.tasks['0'];
 assert.equal(t0.points,3);assert.equal(t0.rationale,'Gleichung und Ergebnis richtig, Schritte fehlen.');
 assert.deepEqual(t0.lost,[{points:1,kind:'rechenweg',why:'Schritte fehlen.',fix:'−2x, dann −5.'}]);
 assert.deepEqual(par.st.saved.overall,{text:'Vorschlag.',strengths:['Aufstellen'],focus:['Klammern']});
 await p.getByText('Vor eurer Prüfung: 2,5 Punkte (sieht das Kind nicht)').waitFor();
 assert.deepEqual(par.errors,[]);
 console.log('PASS: child sees earned points, each loss with reason and fix, summary by reason, mentor links per task; parents check it themselves with AI suggestion, validation, save, prior visible only to parents, 320/390 px');
 await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
