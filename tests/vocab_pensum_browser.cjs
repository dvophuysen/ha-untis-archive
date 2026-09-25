// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
// Vokabelpensum und Vokabeltest auf Papier (D181): Zeile „Heute: x von y Wörtern“, Blatt, Seiten, Auswertung.
const {chromium:pw}=require('playwright-core');
const fs=require('fs');const http=require('http');const path=require('path');const assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4181,'127.0.0.1',r));
 const browser=await pw.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.clock.install({time:new Date('2026-10-05T15:00:00+02:00')});
 const summary={neu:20,wackelt:5,sitzt:0,gefestigt:0};
 const unit={unit:'Unit 3',label:'Unit 3',words:25,pages:[],unread:0,sections:[],s1:summary,s2:{neu:25,wackelt:0,sitzt:0,gefestigt:0},progress:{wrong:2,uncertain:3,secure:0,new:20,total:25},writing_progress:{wrong:0,uncertain:0,secure:0,new:25,total:25}};
 let graded=false,pages=[],created=null;
 const words=Array.from({length:10},(_,i)=>({nr:i+1,prompt:`Wort ${i+1}`,...(graded?{expected:`word${i+1}`,verdict:i<6?'richtig':i<9?'falsch':'unklar',read:`w${i+1}`,note:''}:{})}));
 const paper=()=>({id:7,code:'V7',subject:'ENGLISCH',unit:'Unit 3',unit_label:'Unit 3',direction:'into',language:'Englisch',status:graded?'graded':'active',counts:true,pages,
  words:words.map(w=>graded?{...w,expected:`word${w.nr}`,verdict:w.nr<=6?'richtig':w.nr<=9?'falsch':'unklar',read:`w${w.nr}`,note:''}:w),overall:graded?'Gut gemacht.':'',result:graded?{richtig:6,falsch:3,unklar:1}:null,read_only:false});
 await page.route('**/api/**',async route=>{const req=route.request(),url=new URL(req.url()),u=url.pathname;let body={};
  if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
  else if(u==='/api/accounts/1/vocab/pensum')body={day:'2026-10-05',items:[{subject:'ENGLISCH',unit:'Unit 3',unit_label:'Unit 3',target:25,practiced:graded?21:12,done:false,href:'#/vokabeln/ENGLISCH?unit=Unit%203',exam_key:'k1',why:'Der Vokabeltest ist am Freitag. 25 Wörter sitzen noch nicht.'}]};
  else if(u.endsWith('/learning/vocab/ENGLISCH/units'))body={subject:'ENGLISCH',language:{name:'Englisch',code:'en',into:true},units:[unit],reading:0,overview:{started_units:1,total_units:1,progress:unit.progress,writing_progress:unit.writing_progress},speech:false,hesitation_seconds:12};
  else if(u==='/api/accounts/1/vocab/papers'&&req.method()==='GET')body={papers:created?[{id:7,code:'V7',unit:'Unit 3',status:graded?'graded':'active',right:graded?6:0,total:graded?10:0}]:[]};
  else if(u==='/api/accounts/1/vocab/papers'&&req.method()==='POST'){created=req.postDataJSON();body=paper();}
  else if(u==='/api/accounts/1/vocab/papers/7')body=paper();
  else if(u.endsWith('/papers/7/pages')&&req.method()==='POST'){pages=[...pages,pages.length+100];body=paper();}
  else if(u.includes('/papers/7/pages/'))return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=','base64')});
  else if(u.endsWith('/papers/7/grade')){graded=true;body=paper();}
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://127.0.0.1:4181/#/vokabeln/ENGLISCH?unit=Unit%203');
 await page.getByText('Heute: 12 von 25 Wörtern').waitFor({timeout:8000}).catch(async e=>{console.log('ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
 await page.getByText('Der Vokabeltest ist am Freitag.').waitFor();
 assert.equal(await page.locator('.pensum-bar').getAttribute('aria-valuenow'),'12');
 const width=await page.locator('.pensum-bar span').evaluate(el=>el.style.width);assert.equal(width,'48%');
 if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'vocab-pensum.png'),fullPage:true});
 await page.getByRole('heading',{name:'Test auf Papier'}).waitFor();
 await page.getByRole('button',{name:'Blatt erstellen'}).click();
 await page.getByRole('heading',{name:'Vokabeltest · Unit 3'}).waitFor();
 assert.deepEqual(created,{subject:'ENGLISCH',unit:'Unit 3',section:'',count:20});
 assert.match(await page.getByRole('link',{name:'Blatt öffnen und drucken'}).getAttribute('href'),/^\.\/api\/accounts\/1\/vocab\/papers\/7\/print$/);
 assert.equal(await page.getByRole('button',{name:'Auswerten'}).isDisabled(),true);
 await page.locator('input[type=file]').setInputFiles({name:'seite.jpg',mimeType:'image/jpeg',buffer:Buffer.from([255,216,255,217])});
 await page.getByRole('img',{name:'Seite 1'}).waitFor();
 await page.getByRole('button',{name:'Auswerten'}).click();
 await page.getByText('6 von 10 richtig').waitFor();
 assert.equal(await page.locator('.words li.unklar').count(),1);
 for(const w of [320,390,768]){await page.setViewportSize({width:w,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+w);}
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Fertig'}).click();
 await page.getByText('Heute: 21 von 25 Wörtern').waitFor();
 await page.getByRole('button',{name:/Blatt V7 · 6 von 10 richtig/}).waitFor();
 assert.deepEqual(errors,[]);console.log('PASS: pensum line with bar and reason, paper sheet created, print link, page upload, grading result, 320/390/768 px, no JS exceptions');await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1)});
