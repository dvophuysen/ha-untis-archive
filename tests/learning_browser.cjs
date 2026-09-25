// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Synthetic API fixtures only.
// Lernen als Kompass (D186): Reihenfolge der Abschnitte, Los-Knöpfe, Weg zur Arbeit,
// Extra-Auswahl, Links innerhalb der Lernseite (Router), Mitlesen, Breiten, keine JS-Fehler.
const {chromium}=require('playwright-core');const http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{let file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4183,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote']});
 const page=await browser.newPage({viewport:{width:390,height:844},serviceWorkers:'block',timezoneId:'Europe/Berlin'});const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});page.setDefaultTimeout(8000);
 await page.clock.install({time:new Date('2026-09-28T15:00:00+02:00')});
 const cells=(a,b,c)=>({'1':a,'2':b,'3':c});
 const raster=[{id:11,title:'Terme und Variablen mit einem sehr langen Titel, der umbrechen muss',state:'sitzt',ready:true,stage:'sitzt',cells:cells('sicher','sicher','offen')},
               {id:12,title:'Gleichungen',state:'wackelt',ready:false,stage:'wackelt',cells:cells('unsicher','offen','offen')}];
 const path_=[['einstieg','Einstiegstest','done'],['luecken','Lücken schließen','now'],['probe','Probearbeit','todo'],['arbeit','Arbeit','todo']].map(([key,label,state])=>({key,label,state,text:'Satz zu '+label}));
 const exam={exam_key:'ma1',subject:'Mathematik',title:'',date:'2026-09-30',day_label:'Mi 30.09.',days:2,school_days_left:2,kind:'arbeit',ready:1,total:2,raster,afb_names:{'1':'Wiedergeben','2':'Anwenden','3':'Übertragen'},stage:'luecken',path:path_,verdict:'eng',verdict_text:'Eng: Jeder Schritt zählt jetzt, auch am Wochenende.',vocab:null,topics_missing:false,papers:[{attempt_id:41,label:'Probearbeit',date:'2026-09-25',status:'graded',points:6,points_max:40,unclear:3}]};
 const vocabExam={exam_key:'en1',subject:'Englisch',title:'Vokabeltest',date:'2026-10-05',day_label:'Mo 05.10.',days:7,school_days_left:5,kind:'vokabeltest',ready:0,total:0,raster:[],afb_names:exam.afb_names,stage:'',path:[],verdict:'',verdict_text:'',vocab:{missing:true,unit:'Vokabeln Unit 3',href:null},topics_missing:false};
 let oralState=null;const turns=[];let mirror=false,compassCalls=0,mentorCalls=0,sessionBody=null,practiceBody=null,unarchived=null;
 const compass=()=>({day:'2026-09-28',can_write:!mirror,can_manage:false,ai_enabled:true,speech:false,next_exam:exam,calm:null,
  plan:{day:'2026-09-28',steps:[
   {key:'paper:ma1:kurz',kind:'paper',title:'Kurztest Mathematik: Gleichungen',why:'Im Gespräch geübt, jetzt zeigst du es auf Papier.',subject:'Mathematik',exam_key:'ma1',format:'kurz',topic_id:12,level:null,href:null,done:false},
   {key:'dialog:12',kind:'dialog',title:'Mathematik: Gleichungen',why:'Das Thema sitzt noch nicht sicher.',subject:'Mathematik',exam_key:'ma1',format:null,topic_id:12,level:null,href:'#/learning?topic_id=12',done:false},
   {key:'vocab:Englisch:u3',kind:'vocab',title:'Vokabeln Englisch: Unit 3',why:'Jeden Tag ein paar Wörter.',subject:'Englisch',exam_key:null,format:null,topic_id:null,level:null,href:'#/vokabeln/Englisch?unit=u3',done:true}],
   engpass:true,tight:[],free_day:false,frozen:!mirror,read_only:mirror,done:1,total:3},
  plan_explain:['Jeden Morgen entsteht der Plan neu.','Zwei Schultage vorher durch.','Vokabeln nach Pensum.'],
  exams:[exam,vocabExam],
  strengths:[{kind:'topic',topic_id:11,subject:'Mathematik',title:'Terme und Variablen',text:'sicher seit 24.09.'}],
  gaps:[{kind:'topic',topic_id:12,subject:'Mathematik',title:'Gleichungen',why:'Das Thema wackelt noch. Arbeit am 30.09.',href:'#/learning?topic_id=12'},
        {kind:'lessons',lesson_id:77,subject:'Deutsch',title:'Kommasetzung',why:'2 Stunden in zwei Wochen nicht ganz klar.',href:'#/learning?lesson_id=77&subject=Deutsch&title=Kommasetzung'}],
  extra:[{name:'Deutsch',label:'Deutsch',language:false,exam_key:null,vocab_href:'#/vokabeln/Deutsch',recent:[{lesson_id:77,title:'Kommasetzung',date:'2026-09-24',href:'#/learning?lesson_id=77&subject=Deutsch&title=Kommasetzung'}]},
         {name:'Englisch',label:'Englisch',language:true,exam_key:null,vocab_href:'#/vokabeln/Englisch',recent:[]},
         {name:'Mathematik',label:'Mathematik',language:false,exam_key:'ma1',vocab_href:'#/vokabeln/Mathematik',recent:[]}],
  history:{weeks:[['2026-09-07','vor 3 Wochen',0],['2026-09-14','vor 2 Wochen',1],['2026-09-21','letzte Woche',2],['2026-09-28','diese Woche',1]].map(([start,label,topics])=>({start,label,topics,cells:topics})),topics:4,cells:4,max:2,sentence:'4 Themen sind sicher geworden, 2 davon in Latein.'},
  sessions:[{id:31,subject:'Mathematik',goal:'Terme',label:'Terme',status:'active',task_done:false,last_at:'2026-09-27T16:00:00'}],
  past_exams:[{exam_key:'de0',subject:'Deutsch',date:'2026-09-25',day_label:'Fr 25.09.',ready:1,total:2,raster:[{id:1,title:'A',state:'sitzt'},{id:2,title:'B',state:'wackelt'}]}],
  archived_sessions:[{id:21,subject:'Deutsch',goal:'Nominalisierung',label:'Nominalisierung',archive_reason:'Arbeit am 25.09. geschrieben'}]});
 const session=(id,subject,goal)=>({id,version:1,subject,goal,label:goal,status:'active',mode:'topic',messages:[{id:1,role:'assistant',text:'Los geht es.',payload:{choices:[]},author:null}],attachments:[],materials:[],quiz:[],quiz_open:[]});
 const attempt={id:41,status:'active',label:'Kurztest',format:'kurz',pages:[],read_only:false,answers:{},exam:{title:'Kurztest Gleichungen',minutes:20,tasks:[{prompt:'Löse 2x = 4.',skill_title:'Gleichungen',topic_id:12,afb:1,points:2,minutes:5,operator:'Löse'}]},feedback:{}};
 await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),u=url.pathname;let body={},status=200;
  if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:mirror?'parent':'child',is_admin:false};
  else if(u.endsWith('/learning/compass')){compassCalls++;body=compass();}
  else if(u.endsWith('/learning/mentor')){mentorCalls++;body={};}
  else if(u.endsWith('/learning/mentor/sessions')&&req.method()==='POST'&&req.postDataJSON().oral_exam_key){sessionBody=req.postDataJSON();oralState={id:60,version:1,subject:'ENGLISCH',goal:'Sprechprobe: Meine Familie',label:'Sprechprobe: Meine Familie',status:'active',mode:'oral',oral:{exam_key:'en9',full:false},untimed:true,messages:[{id:1,role:'assistant',text:'Hello! Tell me about your family.',payload:{choices:[]},author:null}],attachments:[],materials:[],quiz:[],quiz_open:[]};body=oralState;}
  else if(u.endsWith('/learning/mentor/sessions')&&req.method()==='POST'){sessionBody=req.postDataJSON();body=session(55,sessionBody.subject||'Mathematik',sessionBody.goal||'Gleichungen');}
  else if(/\/sessions\/60\/turn$/.test(u)){const b=req.postDataJSON();turns.push(b);const n=oralState.messages.length;oralState={...oralState,version:oralState.version+1,messages:[...oralState.messages,{id:n+1,role:'user',text:b.text,payload:{spoken:b.spoken},author:'kind'},
    b.kind==='finish'?{id:n+2,role:'assistant',text:'Du hast viel erzählt.',payload:{choices:[],oral_result:{reliable:true,scores:[{criterion:'wortschatz',label:'Wortschatz',score:3,evidence:'I have a sister.'},{criterion:'grammatik',label:'Grammatik',score:2,evidence:'She have a dog.'}],weak_spots:[{label:'has statt have',example:'She have a dog.',better:'She has a dog.'}],followups:[],level_note:'Etwa A1+.'}},author:null}
    :{id:n+2,role:'assistant',text:'Nice! What does your sister like?',payload:{choices:[],picture:{figure_id:9,caption:'',seite:'Buch S. 20'}},author:null}],status:b.kind==='finish'?'completed':'active'};body=oralState;}
  else if(/\/learning\/mentor\/sessions\/\d+$/.test(u)){const id=Number(u.split('/').pop());body=session(id,'Mathematik','Terme');}
  else if(/\/sessions\/\d+\/unarchive$/.test(u)){unarchived=Number(u.split('/').at(-2));body={ok:true};}
  else if(u.endsWith('/materials/figures/9'))return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=','base64')});
  else if(u.endsWith('/pause'))body=session(55,'Mathematik','Gleichungen');
  else if(u==='/api/accounts/1/practice'&&req.method()==='GET')body={papers:[]};
  else if(u==='/api/accounts/1/practice'&&req.method()==='POST'){practiceBody=req.postDataJSON();body={id:41};}
  else if(u==='/api/accounts/1/practice/attempts/41')body=attempt;
  else if(u.endsWith('/learning/mentor/exams'))body={exams:[],attempts:[]};
  else if(u.endsWith('/settings'))body={default_daily_budget_minutes:60,budget_overrides:{},auto_budget:false,erlass:{}};
  else if(u.endsWith('/reminders'))body={enabled:false,remind_at:null,devices:0,can_manage:false};
  await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 const dump=async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;};
 await page.goto('http://127.0.0.1:4183/#/learning');
 await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor().catch(dump);
 // Reihenfolge: Wo stehe ich, Pflicht, Arbeiten, Stärken/Baustellen, Extra, Verlauf, Weitermachen.
 assert.deepEqual(await page.$$eval('[data-section]',els=>els.map(e=>e.dataset.section)),['kompass','pflicht','vokabeln','arbeiten','staerken','extra','verlauf','weiter']);
 const kompass=page.locator('#k-kompass');
 assert.match(await kompass.innerText(),/Nächste Arbeit · Mathematik · Mi 30\.09\. · noch 2 Schultage/);
 assert.match(await kompass.innerText(),/1 von 2 Themen sicher/);
 assert.match(await kompass.innerText(),/Eng:/);
 assert.equal(mentorCalls,0,'die Übersicht lädt den schweren Lernraum nicht');
 for(const gone of ['Was schon klappt','Deine Lernideen','Übungsklausur','Vokabeln üben','Hast du Material dazu?'])assert.equal(await page.getByText(gone,{exact:true}).count(),0,gone);
 assert.equal(await page.locator('#k-pflicht .step').count(),3);
 assert.equal(await page.locator('#k-pflicht .step.done').count(),1);
 assert.equal(await page.locator('#k-pflicht button',{hasText:'Los'}).count(),2,'Los nur für Offenes');
 // Wie der Plan entsteht: aufklappbar, drei Sätze.
 await page.getByText('Wie der Plan entsteht',{exact:true}).click();await page.getByText('Zwei Schultage vorher durch.',{exact:true}).waitFor();
 // Weg zur Arbeit aufklappen.
 await page.locator('#k-arbeiten .exam-row').first().click();
 await page.getByRole('heading',{name:'Weg zur Arbeit'}).waitFor();
 assert.match(await page.locator('.path li.now').innerText(),/Lücken schließen[\s\S]*Du bist hier/);
 assert.equal(await page.locator('.raster .r-cell').count(),6);
 assert.equal(await page.locator('.raster .r-cell.st-wackelt').count(),1);
 assert.equal(await page.locator('#k-arbeiten .dot').count(),2);
 await page.getByText('Lektion fehlt',{exact:true}).first().waitFor();
 if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'learning-compass.png'),fullPage:true});
 // Los auf einem Papier-Schritt erstellt die Übungsarbeit und öffnet sie.
 await page.locator('#k-pflicht .step').first().getByRole('button',{name:'Los'}).click();
 await page.getByText('Kurztest Gleichungen').first().waitFor().catch(dump);
 assert.deepEqual(practiceBody,{exam_key:'ma1',format:'kurz',topic_ids:[12],level:null});
 await page.getByRole('button',{name:/Zurück zu Lernen/}).first().click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Los auf einem Gesprächsschritt: Link innerhalb der Lernseite öffnet die Einheit (Router-Fix).
 await page.locator('#k-pflicht .step').nth(1).getByRole('button',{name:'Los'}).click();
 await page.getByRole('button',{name:'← Lernen'}).waitFor().catch(dump);
 assert.deepEqual(sessionBody,{topic_id:12});
 assert.equal(await page.evaluate(()=>location.hash),'#/learning','Parameter nach dem Öffnen entfernt');
 await page.getByRole('button',{name:'← Lernen'}).click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Derselbe Link noch einmal wirkt wieder, ohne die Seite neu zu laden.
 sessionBody=null;await page.evaluate(()=>{location.hash='#/learning?topic_id=12';});
 await page.getByRole('button',{name:'← Lernen'}).waitFor();assert.deepEqual(sessionBody,{topic_id:12});
 await page.getByRole('button',{name:'← Lernen'}).click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Neuladen öffnet nichts ungewollt erneut.
 sessionBody=null;await page.reload();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();assert.equal(sessionBody,null);
 // Baustelle angehen: Stunde als Gespräch.
 await page.locator('#k-staerken').getByRole('button',{name:'Angehen'}).nth(1).click();
 await page.getByRole('button',{name:'← Lernen'}).waitFor();assert.equal(sessionBody.lesson_id,77);assert.equal(sessionBody.voluntary,true);assert.equal(sessionBody.goal,'Kommasetzung');
 await page.getByRole('button',{name:'← Lernen'}).click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Extra: Fach, dann Art; Vokabeln nur bei Sprachen.
 const extra=page.locator('#k-extra');
 await extra.getByRole('button',{name:/Deutsch/}).click();
 assert.equal(await extra.getByRole('button',{name:/Vokabeln/}).count(),0,'Deutsch ist keine Fremdsprache');
 await extra.getByRole('button',{name:/Neues Thema anfangen/}).click();await extra.getByRole('button',{name:/Kommasetzung/}).waitFor();
 await extra.getByRole('button',{name:/Englisch/}).click();await extra.getByRole('button',{name:/Vokabeln/}).waitFor();
 await extra.getByRole('button',{name:/Erklären lassen/}).click();
 await page.getByRole('button',{name:'← Lernen'}).waitFor();assert.equal(sessionBody.subject,'Englisch');assert.equal(sessionBody.voluntary,true);
 await page.getByRole('button',{name:'← Lernen'}).click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Kurztest in Mathe: zur anstehenden Arbeit.
 practiceBody=null;await extra.getByRole('button',{name:/Mathematik/}).click();await extra.getByRole('button',{name:/Kurztest/}).click();
 await page.getByText('Kurztest Gleichungen').first().waitFor();assert.deepEqual(practiceBody,{exam_key:'ma1',format:'kurz',topic_ids:[],level:null});
 await page.getByRole('button',{name:/Zurück zu Lernen/}).first().click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Kurztest ohne Arbeit: freie Übungsarbeiten.
 await extra.getByRole('button',{name:/Deutsch/}).click();await extra.getByRole('button',{name:/Kurztest/}).click();
 await page.getByRole('heading',{name:'Übungsarbeiten'}).waitFor();await page.getByRole('button',{name:'← Lernen'}).click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Verlauf in Ergebnissen, Weitermachen, frühere Arbeiten und Archiv.
 assert.equal(await page.locator('#k-verlauf progress').count(),4);
 await page.getByText('4 Themen sind sicher geworden, 2 davon in Latein.',{exact:true}).waitFor();
 await page.getByText('Frühere Arbeiten',{exact:true}).click();await page.getByText('Arbeit am 25.09. geschrieben',{exact:true}).waitFor();
 assert.equal(await page.locator('.past .dot').count(),2);
 await page.getByRole('button',{name:'Wieder aufnehmen'}).click();await page.getByRole('button',{name:'← Lernen'}).waitFor();assert.equal(unarchived,21);
 await page.getByRole('button',{name:'← Lernen'}).click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 for(const width of [320,390,768]){await page.setViewportSize({width,height:900});await page.locator('#k-arbeiten .exam-row').first().click();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);
  const small=await page.$$eval('#k-pflicht button, #k-extra button, #k-staerken button, .exam-row',els=>els.filter(e=>e.offsetParent&&e.getBoundingClientRect().height<44).map(e=>e.textContent.trim()));
  assert.deepEqual(small,[],'44px '+width);
  await page.locator('#k-arbeiten .exam-row').first().click();}
 // D201: Übungsarbeiten je Arbeit auf der Lernseite und Direktsprung ?paper=
 await page.locator('#k-arbeiten .exam-row').first().click();
 await page.getByText('Deine Übungsarbeiten').waitFor();await page.getByText('6 von 40 Punkten · 3 unklar gelesen · Ansehen').click();
 await page.getByText('Kurztest Gleichungen').first().waitFor();
 await page.getByRole('button',{name:/Zurück zu Lernen/}).first().click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 await page.evaluate(()=>{location.hash='#/learning?paper=41';});await page.getByText('Kurztest Gleichungen').first().waitFor();
 assert.equal(await page.evaluate(()=>location.hash),'#/learning','Parameter entfernt');
 await page.getByRole('button',{name:/Zurück zu Lernen/}).first().click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Sprechprobe (D194): Prüfer im Chat, Senden ohne Aufgaben, Auswertung mit Kriterien und Baustellen.
 await page.setViewportSize({width:390,height:844});
 await page.evaluate(()=>{location.hash='#/learning?oral=en9&topic_id=5';});
 await page.getByText('Hello! Tell me about your family.').waitFor().catch(dump);
 assert.deepEqual(sessionBody,{oral_exam_key:'en9',topic_id:5});
 await page.getByRole('button',{name:/Vorlesen an/}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Anders erklären'}).count(),0,'keine Erklärknöpfe in der Probe');
 await page.getByRole('textbox',{name:/Oder tippen/}).fill('I have a sister.');await page.getByRole('button',{name:'Senden',exact:true}).click();
 await page.getByText('Nice! What does your sister like?').waitFor();
 assert.equal(turns[0].kind,'message');
 /* D198: Bild zur Bildbeschreibung im Chat, antippen vergrößert in der App */
 await page.getByRole('img',{name:'Bild zur Bildbeschreibung'}).waitFor();await page.getByText('Buch S. 20 · antippen zum Vergrößern').click();
 await page.getByRole('dialog',{name:'Abbildung vergrößert'}).waitFor();await page.getByRole('dialog',{name:'Abbildung vergrößert'}).getByRole('button',{name:'Schließen'}).click();
 assert.equal(await page.getByRole('dialog',{name:'Abbildung vergrößert'}).count(),0);
 await page.getByRole('button',{name:/Beenden und auswerten/}).click();
 await page.getByText('Darauf achten wir beim nächsten Mal').waitFor();
 await page.getByText('Besser: „She has a dog.“').waitFor();
 assert.equal(turns.at(-1).kind,'finish');
 assert.equal(await page.locator('.oral-result .dots i.on').count(),5);
 await page.getByRole('heading',{name:'Sprechprobe ausgewertet'}).waitFor();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow oral');
 await page.getByRole('button',{name:'← Lernen'}).click();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor();
 // Mitlesen: exakt die Kinderansicht, ohne Knöpfe, die schreiben.
 mirror=true;await page.evaluate(()=>localStorage.setItem('viewMode',JSON.stringify({mode:'mirror',at:Date.now(),day:new Date().toISOString().slice(0,10)})));
 await page.reload();await page.getByRole('heading',{name:'Heute Pflicht'}).waitFor().catch(dump);
 assert.equal(await page.locator('#k-pflicht button',{hasText:'Los'}).count(),0);
 assert.equal(await page.getByRole('button',{name:'Angehen'}).count(),0);
 assert.equal(mentorCalls,0);
 assert.deepEqual(errors,[]);console.log('PASS: compass order, Los buttons, way to the exam, extra choice, in-page links, speaking simulation with assessment, reload, mirror, 320/390/768');await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1);});
