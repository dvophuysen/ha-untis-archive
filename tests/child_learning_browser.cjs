// Production build; synthetic child/parent fixtures, no real account writes.
const {chromium}=require('playwright-core');const http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{let file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4179,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote']});
 const page=await browser.newPage({viewport:{width:390,height:844},serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});page.setDefaultTimeout(8000);let parent=false,created=false,published=false,sessionBody=null,deleted=false,failDelete=true;
 const tasks=Array.from({length:3},(_,i)=>({prompt:'Eine vollständig sichtbare Aufgabe. '.repeat(30)+`ENDE ${i}`,solution:'Nur in der Elternprüfung sichtbar',criteria:'Begründung',skill_title:'Stromkreis',points:4,minutes:5}));
 const exam=()=>({id:5,title:'Physik üben',subject:'Physik',minutes:15,status:published?'published':'draft',scope:{topics:['Stromkreis'],confirmed:false},tasks});
 await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={},status=200;
 if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:parent?'parent':'child',is_admin:false};
 else if(u.endsWith('/mentor'))body={profile:{ai_enabled:true},can_manage:parent,can_write:true,subjects:['Physik','Politik'],errors:[],sessions:[],progress:[],homework_choices:[{id:1,subject:'Physik',title:'Vorbereitung auf den Test'}],shared_plan:{goals:[],today:{actions:[]},week:[],deferred:[]},budget:{opening_confirmed:true,used_eur:0,limit_eur:50,rate_available:true},enabled:true};
 else if(u.endsWith('/sessions/1')){if(req.method()==='DELETE'){if(failDelete){status=500;body={detail:'Löschen nicht gespeichert'};}else{deleted=true;body={ok:true};}}else body={id:1,version:3,subject:'Mathematik',goal:'Gemeinsame Übung',status:'completed',messages:[],summary:'Gespeichert'};}
 else if(u.endsWith('/sessions')&&req.method()==='POST'){sessionBody=req.postDataJSON();body={id:1,subject:sessionBody.subject,goal:sessionBody.goal,status:'completed',messages:[],summary:'Gespeichert'};}
 else if(u.endsWith('/exams')&&req.method()==='POST'){created=true;body={id:5};}
 else if(u.endsWith('/exams'))body={exams:parent||created?[exam()]:[],attempts:[]};
 else if(u.endsWith('/review'))body=exam();
 else if(u.endsWith('/publish')){published=true;body={ok:true};}
 else if(u.endsWith('/start'))body={id:8,version:0,status:'active',exam:{...exam(),tasks:tasks.map(({solution,...t})=>t)},answers:{},feedback:{}};
 else if(u.endsWith('/photos'))body=[];
 await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://127.0.0.1:4179/#/learning');await page.getByRole('heading',{name:'Was möchtest du üben?',exact:true}).waitFor().catch(async e=>{console.log(await page.locator('body').innerText());throw e;});
 assert.equal(await page.locator('details .free-choice').count(),0);
 await page.getByLabel(/^Fach/).selectOption('Politik');await page.getByLabel('Worum geht es ungefähr?').fill('Demokratie');await page.getByRole('button',{name:'Üben starten',exact:true}).click();await page.getByRole('button',{name:'Zur Übersicht',exact:true}).waitFor();assert.equal(sessionBody.subject,'Politik');assert.equal(sessionBody.voluntary,true);
 await page.getByRole('button',{name:'Zur Übersicht',exact:true}).click();await page.getByRole('button',{name:'Übungstest vorbereiten',exact:true}).click();
 await page.getByRole('heading',{name:'Übungstest zusammenstellen'}).waitFor();assert.equal(await page.getByLabel(/^Fach/).inputValue(),'Physik');
 await page.getByLabel('Eigene Themen (auch ohne automatische Vorschläge)').fill('Stromkreis');await page.getByLabel(/^Dauer/).selectOption('15');await page.getByRole('button',{name:'Übungstest erstellen und starten',exact:true}).click();await page.getByLabel('Deine Antwort',{exact:true}).waitFor();assert(created);assert.equal(await page.getByText('Nur in der Elternprüfung sichtbar',{exact:true}).count(),0);
 parent=true;await page.reload();await page.getByRole('button',{name:'Übungsklausur',exact:true}).click();await page.getByText(/Entwurf · für das Kind noch nicht sichtbar/).waitFor();await page.getByRole('button',{name:'Aufgaben ansehen und freigeben',exact:true}).click();
 await page.getByRole('button',{name:'Aufgaben bearbeiten',exact:true}).waitFor();assert.equal(await page.locator('textarea').count(),0);assert.equal(await page.getByText(/ENDE 2/).count(),1);
 await page.getByLabel('Ich habe Aufgaben, Lösungen, Umfang und Punkte geprüft.').check();await page.getByRole('button',{name:'Für das Kind freigeben (Echtdaten)',exact:true}).click();await page.getByRole('button',{name:'Aufgaben ansehen und freigeben',exact:true}).waitFor();assert(published);
 for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);}
 await page.goto('http://127.0.0.1:4179/#/learning?session=1');await page.reload();await page.getByRole('button',{name:'Diese Einheit entfernen',exact:true}).click();await page.getByRole('button',{name:'Einheit endgültig löschen',exact:true}).click();await page.getByText('Löschen nicht gespeichert',{exact:true}).waitFor();assert.equal(deleted,false);failDelete=false;await page.getByRole('button',{name:'Einheit endgültig löschen',exact:true}).click();await page.getByRole('heading',{name:'Der echte Lernverlauf.',exact:true}).waitFor();assert(deleted);
 assert.deepEqual(errors,[]);console.log('PASS: visible free subject choice, homework-to-test, child generation without calendar, hidden answers, parent reading and publication, responsive layout');await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
