// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
// Zurückgehaltene Auswertung (D202) bei Übungsklausur und Vokabeltest: Kind sieht nichts, Eltern prüfen und übernehmen.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4187,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=','base64');
 const tasks=[1,2,3].map(i=>({prompt:`Aufgabe ${i}: Erkläre den Stromkreis.`,solution:'Geschlossener Kreis',criteria:'2 P Begründung',skill_title:`Stromkreis ${i}`,objective:'Ich kann es erklären.',points:4,minutes:5}));
 const exam={id:5,title:'Physik üben',subject:'Physik',minutes:15,status:'published',scope:{topics:['Stromkreis'],confirmed:false},tasks};
 const f=(points,extra={})=>({points,rationale:'Begründung.',next_step:'Weiter üben.',uncertain:false,transcription:'gelesen',solution_seen:false,passes:2,...extra});
 const unit={unit:'Unit 3',label:'Unit 3',words:10,pages:[],unread:0,sections:[],s1:{neu:10,wackelt:0,sitzt:0,gefestigt:0},s2:{neu:10,wackelt:0,sitzt:0,gefestigt:0},progress:{wrong:0,uncertain:0,secure:0,new:10,total:10},writing_progress:{wrong:0,uncertain:0,secure:0,new:10,total:10}};
 async function run(role,start){
  const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.setDefaultTimeout(8000);
  await page.clock.install({time:new Date('2026-09-25T15:00:00+02:00')});
  const st={exam:'review',vocab:'review',examSent:null,vocabSent:null,examManual:null,vocabManual:null};
  const attempt=()=>{
   const base={id:9,exam_id:5,version:4,status:st.exam,answers:{'0':'Antwort 1','1':'Antwort 2','2':''},exam,elapsed_seconds:0,read_only:false};
   if(role==='child')return {...base,feedback:{'0':{pending:true},'1':{pending:true},'2':{pending:true},check:{per_task:true,passes:3,open:[3]}}};
   if(st.exam==='review')return {...base,read_only:true,feedback:{'0':f(3),'1':f(2.5),'2':f(1,{uncertain:true,passes:3,transcription:'Kreis?',spread:[1,3.5]}),check:{per_task:true,passes:3,open:[3]}}};
   if(st.examManual){const t=st.examManual.tasks;return {...base,read_only:true,feedback:{...Object.fromEntries(Object.entries(t).map(([k,x])=>[k,{...x,uncertain:false,checked_by_parent:true}])),losses:[{kind:'rechenweg',label:'Rechenweg oder Begründung fehlt',points:1}],check:{per_task:true,passes:3,open:[],manual:true}}};}
   return {...base,read_only:true,feedback:{'0':f(3),'1':f(2.5),'2':f(2,{checked_by_parent:true,rationale:'Von Eltern geprüft. Begründung.'}),check:{per_task:true,passes:3,open:[],resolved_by_parent:[3]}}};
  };
  const words=Array.from({length:10},(_,i)=>({nr:i+1,prompt:`Wort ${i+1}`}));
  const verdictOf=(nr)=>nr<=7?'richtig':nr===8?'falsch':null;
  const paper=()=>{
   const graded=st.vocab==='graded';
   const w=words.map(x=>{const m=st.vocabManual?.words[String(x.nr)];if(m)return {...x,expected:`word${x.nr}`,read:`w${x.nr}`,note:'',tip:'',kind:'',...m,checked_by_parent:true};const v=verdictOf(x.nr)||(graded?st.vocabSent.verdicts[String(x.nr)]:'unklar');return {...x,expected:`word${x.nr}`,verdict:v,read:`w${x.nr}`,note:'',...(verdictOf(x.nr)?{}:graded?{checked_by_parent:true}:{votes:['richtig','unklar','falsch']})};});
   const count=k=>w.filter(x=>x.verdict===k).length;
   return {id:8,code:'V8',subject:'ENGLISCH',unit:'Unit 3',unit_label:'Unit 3',direction:'into',language:'Englisch',status:st.vocab,counts:true,pages:[201],words:w,overall:'Gut.',
    summary:st.vocabManual?{strengths:[],focus:st.vocabManual.overall.focus}:null,losses:st.vocabManual?[{kind:'sprache',label:'Rechtschreibung',count:1}]:[],
    result:{richtig:count('richtig'),falsch:count('falsch'),unklar:count('unklar')},check:st.vocabManual?{passes:3,unsure:[],held:false,manual:true}:graded?{passes:3,unsure:[],held:true,resolved_by_parent:[9,10]}:{passes:3,unsure:[9,10],held:true},read_only:false,created_at:'2026-09-25T14:00:00'};
  };
  await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};
   if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role,is_admin:false};
   else if(u.endsWith('/learning/compass'))body={day:'2026-09-25',can_write:true,can_manage:false,ai_enabled:true,speech:false,next_exam:null,calm:{text:'Keine Arbeit in Sicht.',vocab:[]},plan:{steps:[],total:0,done:0,read_only:false},plan_explain:[],exams:[],strengths:[],gaps:[],extra:[{name:'Physik',label:'Physik',language:false,exam_key:null,vocab_href:'#/vokabeln/Physik',recent:[]}],history:{weeks:[],max:1,sentence:''},sessions:[],past_exams:[],archived_sessions:[]};
   else if(u.endsWith('/learning/mentor'))body={profile:{ai_enabled:true},can_manage:role==='parent',can_write:true,subjects:['Physik'],errors:[],sessions:[],progress:[],homework_choices:[],shared_plan:{goals:[],today:{actions:[],planned_minutes:0},week:[],deferred:[]},budget:{opening_confirmed:true,used_eur:0,limit_eur:50,rate_available:true},enabled:true};
   else if(u.endsWith('/mentor/exams'))body={exams:[exam],attempts:[{id:9,exam_id:5,status:st.exam,started_at:'2026-09-25T14:00:00',is_test:0}]};
   else if(u.endsWith('/exams/5/start'))body=attempt();
   else if(u.endsWith('/exams/attempts/9/manual')){st.examManual=req.postDataJSON();body=attempt();}
   else if(u==='/api/accounts/1/vocab/papers/8/manual'){st.vocabManual=req.postDataJSON();body=paper();}
   else if(u.endsWith('/exams/attempts/9/review')){st.examSent=req.postDataJSON();st.exam='graded';body=attempt();}
   else if(u.endsWith('/exams/attempts/9/photos'))body=[{id:1,question_index:2}];
   else if(u.includes('/photos/')||u.includes('/papers/8/pages/'))return route.fulfill({status:200,contentType:'image/png',body:png});
   else if(u.endsWith('/exams/attempts/9'))body=attempt();
   else if(u==='/api/accounts/1/vocab/pensum')body={day:'2026-09-25',items:[]};
   else if(u.endsWith('/learning/vocab/ENGLISCH/units'))body={subject:'ENGLISCH',language:{name:'Englisch',code:'en',into:true},units:[unit],reading:0,overview:{started_units:1,total_units:1,progress:unit.progress,writing_progress:unit.writing_progress},speech:false,hesitation_seconds:12};
   else if(u==='/api/accounts/1/vocab/papers')body={papers:[{id:8,code:'V8',unit:'Unit 3',status:st.vocab,right:0,total:0}]};
   else if(u==='/api/accounts/1/vocab/papers/8/review'){st.vocabSent=req.postDataJSON();st.vocab='graded';body=paper();}
   else if(u==='/api/accounts/1/vocab/papers/8')body=paper();
   await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
  });
  await page.goto(`http://127.0.0.1:4187/${start}`);
  return {page,errors,st};
 }
 const fail=async(p,e)=>{console.log('ERRORS',p.errors,'BODY',await p.page.locator('body').innerText());throw e;};

 // Kind: Übungsklausur wieder geöffnet, während die Eltern prüfen.
 const kid=await run('child','#/learning?subject=Physik&mode=exam');
 await kid.page.getByRole('button',{name:'Online / Foto bearbeiten'}).click().catch(e=>fail(kid,e));
 await kid.page.getByText('Deine Arbeit ist abgegeben.').waitFor().catch(e=>fail(kid,e));
 await kid.page.getByText(/Deine Eltern schauen sich die Auswertung an/).waitFor();
 assert.equal(await kid.page.getByText(/von 4 Punkten|\/ 4 Punkte/).count(),0,'keine Punkte für das Kind');
 assert.equal(await kid.page.getByRole('spinbutton').count(),0);
 assert.equal(await kid.page.getByRole('button',{name:/Nächste Aufgabe auswerten/}).count(),0);
 assert.deepEqual(kid.errors,[]);

 // Eltern: aus „Erledigen“ zur Übungsklausur, Punkte der offenen Aufgabe eintragen.
 const par=await run('parent','#/learning?exam_attempt=9');
 await par.page.getByText('Prüfung nötig: Aufgabe 3').waitFor().catch(e=>fail(par,e));
 await par.page.getByText('Die Bewertungen kamen auf 1 und 3,5 Punkte.').waitFor();
 await par.page.getByRole('img',{name:'Foto zu Aufgabe 3'}).waitFor();
 assert.equal(await par.page.getByRole('spinbutton').count(),1,'nur die offene Aufgabe');
 assert.equal(await par.page.getByRole('button',{name:'Punkte übernehmen'}).isDisabled(),true);
 await par.page.getByRole('spinbutton',{name:/Punkte nach eurer Prüfung/}).fill('2');
 await par.page.getByRole('button',{name:'Punkte übernehmen'}).click();
 await par.page.getByRole('heading',{name:'Das große Ganze'}).waitFor().catch(e=>fail(par,e));
 assert.deepEqual(par.st.examSent,{points:{'2':2}});
 await par.page.getByRole('button',{name:'Stromkreis 3: 2 / 4 Punkte'}).waitFor();
 await par.page.getByText(/Aufgabe 3 von deinen Eltern geprüft/).waitFor();
 // D207: Eltern prüfen die fertige Übungsklausur selbst; das Kind sieht Abzüge mit Lösung.
 await par.page.getByRole('button',{name:'Selbst prüfen'}).click();
 await par.page.getByText('Ihr bewertet jede Aufgabe.').waitFor().catch(e=>fail(par,e));
 await par.page.getByLabel('Punkte Aufgabe 1').fill('3');
 await par.page.getByRole('button',{name:'+ Abzug ergänzen'}).first().click();
 await par.page.getByLabel('Was fehlte oder falsch war').first().fill('Begründung fehlt.');
 await par.page.getByLabel('So hätte es die Punkte gegeben').first().fill('Der Kreis muss geschlossen sein.');
 await par.page.setViewportSize({width:320,height:800});assert.equal(await par.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320 Elternprüfung Klausur');
 await par.page.getByRole('button',{name:'Prüfung speichern'}).click();
 await par.page.getByRole('heading',{name:'Das große Ganze'}).waitFor().catch(e=>fail(par,e));
 assert.deepEqual(par.st.examManual.tasks['0'].lost,[{points:1,kind:'unvollstaendig',why:'Begründung fehlt.',fix:'Der Kreis muss geschlossen sein.'}]);
 assert.deepEqual(Object.keys(par.st.examManual.tasks),['0','1','2']);
 await par.page.getByText('Hier sind die meisten Punkte liegen geblieben').waitFor();
 await par.page.getByText('Von deinen Eltern geprüft.').waitFor();
 await par.page.getByText('3 von 4 Punkten · von deinen Eltern geprüft').waitFor();
 await par.page.getByText('Der Kreis muss geschlossen sein.').waitFor();
 await par.page.setViewportSize({width:320,height:800});assert.equal(await par.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320 Übungsklausur');
 assert.deepEqual(par.errors,[]);

 // Eltern: Vokabelblatt aus „Erledigen“, richtig/falsch je offenem Wort.
 const voc=await run('parent','#/vokabeln/ENGLISCH?paper=8');
 await voc.page.getByText('Prüfung nötig: 2 Wörter').waitFor().catch(e=>fail(voc,e));
 await voc.page.getByRole('img',{name:'Seite 1'}).waitFor();
 assert.equal(await voc.page.locator('.words li').count(),2,'nur die offenen Wörter');
 const send=voc.page.getByRole('button',{name:'Übernehmen'});
 assert.equal(await send.isDisabled(),true);
 await voc.page.getByRole('group',{name:'Wort 9'}).getByRole('button',{name:'richtig'}).click();
 assert.equal(await send.isDisabled(),true,'erst wenn alle entschieden sind');
 await voc.page.getByRole('group',{name:'Wort 10'}).getByRole('button',{name:'falsch'}).click();
 await send.click();
 await voc.page.getByText('8 von 10 richtig').waitFor().catch(e=>fail(voc,e));
 assert.deepEqual(voc.st.vocabSent,{verdicts:{'9':'richtig','10':'falsch'}});
 await voc.page.getByText(/Unsicher gelesene Wörter haben deine Eltern geprüft/).waitFor();
 assert.equal(await voc.page.getByText(/von deinen Eltern geprüft/).count()>=2,true);
 // D207: Eltern prüfen das Blatt selbst; falsche Wörter mit Grund und Merkhilfe.
 await voc.page.getByRole('button',{name:'Selbst prüfen'}).click();
 await voc.page.getByText('Entscheidet jedes Wort.').waitFor().catch(e=>fail(voc,e));
 await voc.page.getByRole('group',{name:'Wort 1',exact:true}).getByRole('button',{name:'falsch'}).click();
 await voc.page.getByLabel('Grund Wort 1',{exact:true}).selectOption('sprache');
 await voc.page.getByLabel('Was war falsch bei Wort 1',{exact:true}).fill('ou statt au.');
 await voc.page.getByLabel('Merkhilfe Wort 1',{exact:true}).fill('house wie Haus, nur mit ou.');
 await voc.page.getByLabel('Das übt das Kind als Nächstes (eine Zeile je Schritt)').fill('Schreibung mit ou üben');
 await voc.page.setViewportSize({width:320,height:800});assert.equal(await voc.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320 Elternprüfung Vokabeln');
 await voc.page.getByRole('button',{name:'Prüfung speichern'}).click();
 await voc.page.getByText('Merkhilfe:').waitFor().catch(e=>fail(voc,e));
 const vm=voc.st.vocabManual;
 assert.deepEqual(vm.words['1'],{verdict:'falsch',kind:'sprache',note:'ou statt au.',tip:'house wie Haus, nur mit ou.'});
 assert.deepEqual(vm.words['2'],{verdict:'richtig'});assert.equal(Object.keys(vm.words).length,10);
 assert.deepEqual(vm.overall.focus,['Schreibung mit ou üben']);
 await voc.page.getByText('Daran lag es bei den falschen Wörtern').waitFor();
 await voc.page.getByText('Rechtschreibung: 1 Wort').waitFor();
 await voc.page.getByText(/Von deinen Eltern geprüft/).first().waitFor();
 await voc.page.setViewportSize({width:320,height:800});assert.equal(await voc.page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow 320 Vokabeltest');
 assert.deepEqual(voc.errors,[]);
 console.log('PASS: held practice exam shows no points to the child, parent review with photo, spread and points, result after review; held vocab paper reviewed word by word by parents, result after review; parents check exam and vocab paper themselves with reasons, fixes and memory aids (D207), 320/390 px');
 await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
