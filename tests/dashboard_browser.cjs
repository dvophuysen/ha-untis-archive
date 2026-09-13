// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4178,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.clock.install({time:new Date('2026-09-14T14:00:00+02:00')});
 let rating=null,done=false,failRating=true,failTask=true,failPack=true;
 const bags={};let schoolDate='2026-09-14';
 function bag(day){const states=bags[day]||={};const items=[{key:'subject:math',label:'Mathematik'},{key:'subject:sport',label:'Sport'}].map(i=>({...i,done:!!states[i.key],revision:states[i.key]?1:0}));return {school_day:day,items,schedule:[{id:1,subject_name:'Mathematik',start_hhmm:'08:00',end_hhmm:'08:45',room:'204',material_key:'subject:math',material_checkbox:true},{id:2,subject_name:'Mathematik',start_hhmm:'08:45',end_hhmm:'09:30',room:'204',material_key:'subject:math',material_checkbox:false},{id:3,subject_name:'Sport',start_hhmm:'09:50',end_hhmm:'10:35',room:'Halle 2',room_orig:'Halle 1',is_room_substituted:true,teacher_name:'Vertretung',teacher_orig_name:'Stammlehrkraft',is_teacher_substituted:true,material_key:'subject:sport',material_checkbox:true},{id:4,subject_name:'Physik',start_hhmm:'10:50',end_hhmm:'11:35',is_cancelled:true}],plan_key:'a'.repeat(64),can_write:true,confirmed_count:items.filter(i=>i.done).length,status:items.every(i=>i.done)?'packed':'open'};}
 await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};let status=200;
 if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
 else if(u.includes('/packing/')){const day=u.split('/').at(-1);if(req.method()==='PUT'){if(failPack){status=500;body={detail:'Packen nicht gespeichert'};}else{const update=req.postDataJSON();(bags[day]||={})[update.item_key]=update.done;body=bag(day);}}else body=bag(day);}
 else if(u.endsWith('/today'))body={date:schoolDate,lessons:[{id:1,date:schoolDate,subject_name:'Deutsch',subject_short:'DE',start_hhmm:'08:00',start_time:800,end_time:845,room:'204',lstext:'Groß- und Kleinschreibung',checkin:{rating,note:null}}],next:{date:'2026-09-15',lessons:[{id:2,subject_name:'Sport',start_hhmm:'08:00',end_time:845,room:'Halle'}]}};
 else if(u.endsWith('/tasks')&&req.method()==='GET')body={tasks:[{id:1,title:'Mathematik',notes:'Brüche: Aufgabe 3',due_date:'2026-09-15',status:done?'done':'open',estimated_minutes:10},{id:2,title:'Englisch',notes:'Seite 24 lesen',due_date:'2026-09-18',status:'open'},{id:3,title:'Notiz ohne Termin',status:'open'},{id:4,title:'Geschichte',notes:'Lies den Text und beschreibe die Unterschiede. '.repeat(5),due_date:'2026-09-21',status:'open'}]};
 else if(u.endsWith('/plan'))body={today:{actions:[{key:'math',subject:'Mathematik',title:'Brüche vergleichen',minutes:8,url:'#/learning?focus=math'}]},upcoming_exams:[],errors:[]};
 else if(u.endsWith('/checkin')){if(failRating){status=500;body={detail:'Test failure'};}else{rating=req.postDataJSON().rating;body={rating,note:null};}}
 else if(u==='/api/tasks/1'){if(failTask){status=500;body={detail:'Test failure'};}else{done=req.postDataJSON().status==='done';body={ok:true};}}
 await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://127.0.0.1:4178/#/today');await page.getByRole('heading',{name:'Heute erledigen',exact:true}).waitFor({timeout:8000}).catch(async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
 for(const title of ['Schon vorziehen','Noch ohne Termin','🌱 Üben & vorbereiten →'])assert.equal(await page.getByRole('heading',{name:title,exact:true}).count(),1);
 await page.getByRole('button',{name:'Verstanden',exact:true}).click();await page.getByRole('alert').filter({hasText:'Nicht gespeichert'}).waitFor();assert.equal(await page.getByRole('button',{name:'Verstanden',exact:true}).count(),1);
 failRating=false;await page.getByRole('button',{name:'Verstanden',exact:true}).click();await page.getByRole('button',{name:/Vergangene Stunden ansehen/}).waitFor();assert.equal(await page.getByRole('button',{name:'Verstanden',exact:true}).count(),0);
 await page.getByRole('button',{name:'Als erledigt markieren',exact:true}).first().click();await page.getByText('Test failure',{exact:true}).waitFor();assert.equal(done,false);
 failTask=false;await page.getByRole('button',{name:'Als erledigt markieren',exact:true}).first().click();await page.getByText('Für morgen ist nichts mehr offen!').waitFor();
 await page.locator('.schedule-row').first().waitFor();assert.equal(await page.locator('.schedule-row').count(),4);assert.equal(await page.getByRole('button',{name:'Material für Mathematik',exact:true}).count(),1);await page.getByText('❌ Entfällt',{exact:true}).waitFor();await page.getByText(/Raum Halle 2.*statt Halle 1/).waitFor();
 await page.getByRole('button',{name:'Material für Sport',exact:true}).click();await page.getByRole('alert').filter({hasText:'Packen nicht gespeichert'}).waitFor();
 assert.equal(await page.locator('.pack-row[aria-pressed="true"]').count(),0);
 failPack=false;await page.getByRole('button',{name:'Material für Sport',exact:true}).click();await page.locator('.pack-row[aria-pressed="true"]').waitFor();
 await page.reload();await page.locator('.pack-row[aria-pressed="true"]').waitFor();
 assert.equal(await page.locator('.pack-row[aria-pressed="true"]').count(),1);
 await page.getByRole('button',{name:'Material für Mathematik',exact:true}).click();await page.getByText('✓ Material für alle Fächer abgehakt.').first().waitFor();
 for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);}
 await page.setViewportSize({width:768,height:900});const edges=await page.locator('.row-actions').evaluateAll(rows=>rows.map(r=>r.getBoundingClientRect().right));assert(edges.every(x=>Math.abs(x-edges[0])<1),'task actions have one right edge');if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'dashboard-tablet.png'),fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'dashboard-390.png'),fullPage:true});
 await page.emulateMedia({colorScheme:'dark'});if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'dashboard-dark.png'),fullPage:true});
 schoolDate='2026-09-15';await page.clock.setFixedTime(new Date('2026-09-15T07:00:00+02:00'));await page.reload();await page.getByText('✓ Material für alle Fächer abgehakt.').first().waitFor();assert.equal(await page.locator('.school .pack-row[aria-pressed="true"]').count(),2,'evening confirmations remain in morning checklist');
 assert.deepEqual(errors,[]);console.log('PASS: dashboard sections, failed/successful checkin and task save, persistent packing and failed packing save, 320/390/768 px, no JS exceptions');await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
