// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
// Übungsarbeiten (D178): Raster je Thema und Anforderungsbereich, Arbeit erstellen, Seiten, Auswertung.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4179,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.clock.install({time:new Date('2026-09-25T15:00:00+02:00')});
 const cell=(state,ratio=null,tasks=0)=>({state,ratio,tasks,helped:0});
 const topics=[
  {id:11,title:'Lineare Gleichungen lösen',detail:'',places_label:'S. 8–15',stage:'neu',cells:{'1':cell('offen'),'2':cell('offen'),'3':cell('offen')},level:0,target:1,ready:false},
  {id:12,title:'Wertetabellen und Graphen',detail:'',places_label:'S. 16–25',stage:'neu',cells:{'1':cell('sicher',.9,2),'2':cell('fast',.7,1),'3':cell('offen')},level:1,target:2,ready:false},
  {id:13,title:'Gleichungen grafisch lösen',detail:'',places_label:'S. 26–35',stage:'neu',cells:{'1':{...cell('sicher'),implied:true},'2':cell('bestaetigt',.85,3),'3':cell('unsicher',.4,1)},level:2,target:3,ready:true}];
 const formats=[['einstieg','Einstiegstest',30],['kurz','Kurztest',20],['mix','Mix',30],['probe','Probearbeit',45]].map(([key,label,minutes])=>({key,label,minutes,why:'Beschreibung '+label}));
 let created=null,graded=false,pages=[],sent=null;
 const task=(i,afb)=>({prompt:`Löse die Gleichung ${i}x + 3 = 12.`,solution:'x = 3',criteria:'1 P Ansatz; 2 P Rechnung',skill_title:topics[1].title,topic_id:12,afb,points:3,minutes:5,operator:'Löse'});
 const attempt=()=>({id:41,status:graded?'graded':'active',label:'Kurztest',format:'kurz',pages,read_only:false,answers:{},
  exam:{title:'Kurztest Wertetabellen',minutes:20,tasks:[task(1,2),task(2,2),task(3,3)]},
  feedback:graded?{'0':{points:3,rationale:'Alles richtig.',next_step:'Weiter mit III.',uncertain:false,transcription:'x = 3'},'1':{points:1.5,rationale:'Rechnung fehlt.',next_step:'Rechenweg aufschreiben.',uncertain:false},'2':{points:0,rationale:'Nicht lesbar.',next_step:'Deutlicher schreiben.',uncertain:true},overall:{text:'Guter Anfang.'}}:{}});
 await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),u=url.pathname;let body={};let status=200;
  if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
  else if(u.endsWith('/exams/all'))body={upcoming:[{exam_key:'k1',date:'2026-09-28',subject_name:'Mathematik',title:'Mathematik',topics:topics.map(t=>({...t,stale:0,places:[],self_view:null})),stages:{neu:3},sources:null,scope:null}],past:[],archived_count:0};
  else if(u==='/api/accounts/1/practice'&&req.method()==='GET'){assert.equal(url.searchParams.get('exam_key'),'k1');body={topics,ready:1,total:3,goal_afb:2,afb_names:{'1':'Wiedergeben','2':'Anwenden','3':'Übertragen'},formats,papers:created?[{id:5,attempt_id:41,label:'Kurztest',created_at:'2026-09-25T15:00:00',status:graded?'graded':'active',points:graded?4.5:null,points_max:9,tasks:3}]:[]};}
  else if(u==='/api/accounts/1/practice'&&req.method()==='POST'){created=req.postDataJSON();body=attempt();}
  else if(u==='/api/accounts/1/practice/attempts/41')body=attempt();
  else if(u.endsWith('/attempts/41/pages')){pages=[...pages,pages.length+100];body=attempt();}
  else if(u.endsWith('/attempts/41/grade')){sent=req.postDataJSON();graded=true;body=attempt();}
  else if(u.includes('/photos/'))return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=','base64')});
  await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://127.0.0.1:4179/#/klausuren?exam=k1');
 await page.getByText('Übungsarbeiten',{exact:true}).waitFor({timeout:8000}).catch(async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
 await page.getByText('1 von 3 Themen sicher in I und II').waitFor();
 assert.equal(await page.locator('.g-cell').count(),9);
 assert.equal(await page.locator('.g-cell.st-gefestigt').count(),1,'bestätigt');
 assert.equal(await page.locator('.g-cell.implied').count(),1,'mit gezeigt');
 if(process.env.SCHOOL_SCREENSHOT_DIR)await page.locator('.practice').screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'practice-raster.png')});
 await page.getByRole('button',{name:/^Kurztest/}).click();
 await page.getByRole('button',{name:'Wertetabellen und Graphen',exact:true}).click();
 await page.getByRole('button',{name:'Gleich III',exact:true}).click();
 await page.getByRole('button',{name:'Übungsarbeit erstellen'}).click();
 await page.getByRole('heading',{name:'Kurztest Wertetabellen'}).waitFor();
 assert.deepEqual(created,{exam_key:'k1',format:'kurz',topic_ids:[12],level:3});
 assert.match(await page.getByRole('link',{name:'Blatt öffnen und drucken'}).getAttribute('href'),/^\.\/api\/accounts\/1\/practice\/attempts\/41\/print$/);
 assert.equal(await page.getByRole('button',{name:'Abgeben und auswerten'}).isDisabled(),true);
 await page.locator('input[type=file]').setInputFiles({name:'seite.jpg',mimeType:'image/jpeg',buffer:Buffer.from([255,216,255,217])});
 await page.getByRole('img',{name:'Seite 1'}).waitFor();
 await page.getByLabel('Lieber am Gerät tippen').check();
 await page.locator('textarea').first().fill('x = 3');
 await page.getByRole('button',{name:'Abgeben und auswerten'}).click();
 await page.getByText('4,5 von 9 Punkten').waitFor();
 assert.deepEqual(sent,{answers:{'0':'x = 3'}});
 assert.equal(await page.locator('.pts').filter({hasText:'unklar'}).count(),1);
 for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);}
 await page.setViewportSize({width:390,height:844});
 if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'practice-result.png'),fullPage:true});
 await page.getByRole('button',{name:'Zum Raster',exact:true}).click();
 await page.getByText('4,5 von 9 Punkten').waitFor();
 await page.setViewportSize({width:320,height:800});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'raster overflow 320');
 assert.deepEqual(errors,[]);console.log('PASS: raster states, Kurztest with topic and level, print link, page upload, typed answer, grading result, 320/390/768 px, no JS exceptions');await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
