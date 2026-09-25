// Woche rollend (D184). Build the frontend first. Requires playwright-core;
// optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
const fmt=t=>`${String(Math.floor(t/100)).padStart(2,'0')}:${String(t%100).padStart(2,'0')}`;
let nextId=1;
const les=(date,s,e,subject,extra={})=>({id:nextId++,date,start_time:s,end_time:e,start_hhmm:fmt(s),end_hhmm:fmt(e),subject_name:subject,subject_short:subject.slice(0,2).toUpperCase(),
  room:'A1',is_cancelled:false,was_absent:false,is_irregular:false,is_room_substituted:false,exam:null,exam_marked:false,checkin:null,rating:null,caught_up:false,lstext:null,...extra});
const per=l=>({short:l.subject_short,subject:l.subject_name,start:l.start_hhmm,end:l.end_hhmm,state:l.is_cancelled?'cancelled':l.is_irregular?'sub':'normal',exam:!!l.exam_marked,room_changed:false,room:l.room,absent:false,now:false,past:false});
const LABEL={'2026-09-17':'Do 17.09.','2026-09-18':'Fr 18.09.','2026-09-21':'Mo 21.09.','2026-09-22':'Di 22.09.','2026-09-23':'Mi 23.09.',
  '2026-09-24':'Do 24.09.','2026-09-25':'Fr 25.09.','2026-09-28':'Mo 28.09.','2026-09-29':'Di 29.09.','2026-09-30':'Mi 30.09.','2026-10-01':'Do 01.10.','2026-10-02':'Fr 02.10.'};
function day(date,lessons,{today='2026-09-24',headline='',changes=[],exams=[],tasks=[],early=false}={}){
  const held=lessons.filter(l=>!l.is_cancelled);
  const strip=lessons.length?{date,label:date===today?'Heute':LABEL[date],is_today:date===today,start:held[0]?.start_hhmm,end:held.at(-1)?.end_hhmm,planned_start:lessons[0].start_hhmm,planned_end:lessons.at(-1).end_hhmm,
    early_end:early,late_start:false,all_cancelled:!held.length,headline,changes,notes:changes.map(c=>c.text),deviates:!!(headline||changes.length),periods:lessons.map(per)}:null;
  return {date,label:LABEL[date],is_today:date===today,is_past:date<today,assumed:!lessons.length,week:date<'2026-09-28'?39:40,holiday:null,strip,lessons,exams,tasks,tasks_open:tasks.filter(t=>!t.done).length};
}
const std=(date,extra={})=>[les(date,750,835,'Mathematik'),les(date,840,925,'Mathematik'),les(date,945,1030,'Deutsch'),les(date,1035,1120,'Englisch',extra)];
const task=(id,title,due,done=false)=>({id,title,subject_name:'Mathematik',subject:'Mathematik',status:done?'done':'open',due_date:due,done});
function ahead(){
  nextId=1;
  const thu=[les('2026-09-24',750,835,'Mathematik'),les('2026-09-24',840,925,'Deutsch'),les('2026-09-24',1135,1220,'Englisch',{is_cancelled:true}),les('2026-09-24',1225,1310,'Englisch',{is_cancelled:true})];
  const fri=[les('2026-09-25',750,835,'Sport'),les('2026-09-25',945,1030,'Spanisch'),les('2026-09-25',945,1030,'Latein'),les('2026-09-25',1035,1120,'Musik',{is_irregular:true})];
  const tue=std('2026-09-29');tue[0].exam_marked=tue[1].exam_marked=true;
  return {today:'2026-09-24',default:true,mode:'ahead',range:{start:'2026-09-24',end:'2026-09-30'},prev_before:'2026-09-24',next_from:'2026-10-01',review:null,holiday:null,
    free:[{start:'2026-09-28',end:'2026-09-28',name:'Beweglicher Ferientag',label:'Mo 28.09.',holiday_end:'2026-09-28'}],
    feedback:{count:2,days:[{date:'2026-09-23',label:'Mi 23.09.',lessons:[les('2026-09-23',750,835,'Physik'),les('2026-09-23',945,1030,'Chemie')]}]},
    days:[day('2026-09-24',thu,{headline:'früher Schluss 09:25 statt 13:10',changes:[{kind:'cancelled',subject:'Englisch',start:'11:35',text:'Englisch 11:35–13:10 fällt aus'}],tasks:[task(1,'Arbeitsblatt Brüche','2026-09-24',true)],early:true}),
      day('2026-09-25',fri,{changes:[{kind:'sub',subject:'Musik',start:'10:35',text:'Musik 10:35 Vertretung'}],tasks:[task(2,'S. 12 Nr. 3','2026-09-25'),task(3,'Vokabeln lernen','2026-09-25')]}),
      day('2026-09-29',tue,{exams:[{exam_key:'cal:m',subject:'Mathematik',kind:'Arbeit',ready:1,total:2}],tasks:[task(4,'Übungsblatt','2026-09-29')]}),
      day('2026-09-30',std('2026-09-30'),{}),day('2026-10-01',std('2026-10-01'),{})]};
}
function later(){
  const days=['2026-10-01','2026-10-02'].map(d=>day(d,std(d)));
  return {today:'2026-09-24',default:false,mode:'ahead',range:{start:'2026-10-01',end:'2026-10-02'},prev_before:'2026-10-01',next_from:'2026-10-03',review:null,holiday:null,free:[],feedback:{count:0,days:[]},days};
}
function past(){
  const ds=['2026-09-17','2026-09-18','2026-09-21','2026-09-22','2026-09-23'];
  const days=ds.map(d=>day(d,std(d)));
  days[0].lessons[0].checkin={rating:3,note:null};
  return {today:'2026-09-24',default:false,mode:'past',range:{start:ds[0],end:ds[4]},prev_before:null,next_from:'2026-09-24',holiday:null,free:[],
    review:{lines:['4 Hausaufgaben erledigt','120 Vokabeln geübt, 101 richtig','1 Thema sitzt jetzt: Brüche','1 von 20 Stunden zurückgemeldet'],lessons:{held:20,rated:1}},
    feedback:{count:1,days:[{date:'2026-09-23',label:'Mi 23.09.',lessons:[days[4].lessons[3]]}]},days};
}
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const f=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',f.endsWith('.js')?'text/javascript':f.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(f));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4185,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
try {
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});
page.setDefaultTimeout(6000);const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
await page.clock.install({time:new Date('2026-09-24T10:00:00+02:00')});
const calls=[];const checkins=[];let slow=false;
await page.route('**/api/**',async route=>{
  const req=route.request(),url=new URL(req.url()),u=url.pathname;let body={};
  if(u==='/api/me')body={id:2,role:'child',is_admin:false,accounts:[{id:1,name:'Kind A'}]};
  else if(u==='/api/accounts/1/week/rolling'){
    calls.push(url.search);
    if(slow)await new Promise(r=>setTimeout(r,400));
    body=url.searchParams.get('before')?past():url.searchParams.get('from')?later():ahead();
  }
  else if(/\/lessons\/\d+\/checkin$/.test(u)){const b=req.postDataJSON();checkins.push({id:Number(u.split('/').at(-2)),...b});body={rating:b.rating,note:b.note};}
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
});
await page.goto('http://127.0.0.1:4185/#/week');
const glance=page.locator('section.glance');
await glance.getByRole('heading',{name:'Die nächsten Tage auf einen Blick'}).waitFor();
// Kopf: Zeitraum lesbar, KW, Pfeile mit Namen.
await page.getByText('Do 24.09. – Mi 30.09.',{exact:true}).waitFor();await page.getByText('KW 39/40').waitFor();
await page.getByRole('button',{name:'Fünf Schultage zurück'}).waitFor();await page.getByRole('button',{name:'Fünf Schultage weiter'}).waitFor();
assert.equal(await page.locator('.wk-head').getByRole('button',{name:'Heute',exact:true}).count(),0);
// Überblick: früher Schluss, Ausfall, Vertretung, freier Tag, Arbeit mit Lernstand, Hausaufgaben je Tag.
assert.deepEqual(await glance.locator('.g-day').allInnerTexts(),['Heute','Fr 25.09.','Mo 28.09.','Di 29.09.']);
await glance.getByText('früher Schluss 09:25 statt 13:10').waitFor();await glance.getByText('Englisch 11:35–13:10 fällt aus').waitFor();
await glance.getByText('Musik 10:35 Vertretung').waitFor();await glance.getByText('Beweglicher Ferientag').waitFor();
const exam=glance.getByRole('link',{name:/Mathematik-Arbeit/});
assert.match(await exam.innerText(),/1 von 2 Themen sicher/);assert.equal(await exam.getAttribute('href'),'#/klausuren?exam=cal%3Am');
const hw=glance.getByRole('link',{name:/Hausaufgaben fällig/});
assert.equal((await hw.innerText()).replace(/\s+/g,' '),'3 Hausaufgaben fällig Fr 2 · Di 1');assert.equal(await hw.getAttribute('href'),'#/tasks');
// Rückmelden für ältere Stunden direkt mit Gesichtern.
const fb=page.locator('section.fb');
await fb.getByRole('heading',{name:'Noch zurückmelden: 2 Stunden'}).waitFor();
await fb.getByRole('button',{name:'Verstanden'}).first().click();
await fb.getByRole('heading',{name:'Noch zurückmelden: 1 Stunde'}).waitFor();assert.equal(checkins.length,1);
// Kalender: Leisten, heute hervorgehoben, parallele Stunden beide sichtbar, freier Tag als Zeile.
const days=page.locator('.day');
assert.equal(await days.count(),5);
assert.equal(await page.locator('.day.today').count(),1);
assert.equal(await page.locator('.day[data-date="2026-09-25"] .par i').count(),2);
assert.equal(await page.locator('.day[data-date="2026-09-24"] .strip i.x').count(),2);
assert.equal(await page.locator('.day[data-date="2026-09-29"] .strip i.arbeit').count(),2);
await page.locator('.free-row',{hasText:'Mo 28.09. · Beweglicher Ferientag'}).waitFor();
// Aufklappen an Ort und Stelle: Tagesliste und Hausaufgaben des Tages.
const fri=page.locator('.day[data-date="2026-09-25"]');
await fri.locator('.day-btn').click();assert.equal(await fri.locator('.day-btn').getAttribute('aria-expanded'),'true');
await fri.locator('.day-schedule').waitFor();await fri.getByText('Hausaufgaben für Fr 25.09.').waitFor();await fri.getByText('S. 12 Nr. 3').waitFor();
assert.equal(await fri.locator('.ds-faces').count(),0,'Zukunft: noch nichts zurückzumelden');
await fri.locator('.day-btn').click();assert.equal(await fri.locator('.day-schedule').count(),0);
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);}
await page.setViewportSize({width:390,height:844});
if(process.env.SCHOOL_SCREENSHOT_DIR){await page.setViewportSize({width:390,height:1800});await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'week-strip.png'),fullPage:true});await page.setViewportSize({width:390,height:844});}
// Raster: Umschalter merkt sich die Wahl, parallele Stunden beide, Doppelstunde über zwei Zeilen.
await page.getByRole('button',{name:'Raster',exact:true}).click();
await page.locator('.wg').waitFor();
assert.equal(await page.evaluate(()=>localStorage.getItem('week.view')),'grid');
assert.equal(await page.getByRole('button',{name:/^Spanisch/}).count(),1);assert.equal(await page.getByRole('button',{name:/^Latein/}).count(),1);
assert.equal(await page.locator('.wg .les.x').count(),1,'Englisch-Doppelstunde als eine Zelle');
assert.equal(await page.locator('.wg .head.today').count(),1);assert.equal(await page.locator('.wg .today-col').count(),1);
assert.ok(await page.locator('.wg .les.arbeit').count()>=1);
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'grid overflow '+width);}
await page.setViewportSize({width:390,height:844});
if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'week-grid.png'),fullPage:true});
await page.reload();await page.locator('.wg').waitFor();
await page.getByRole('button',{name:'Streifen',exact:true}).click();await page.locator('.day').first().waitFor();
// Blättern: alter Inhalt bleibt stehen, bis die neuen Daten da sind.
slow=true;
await page.getByRole('button',{name:'Fünf Schultage weiter'}).click();
assert.equal(await page.locator('.day').count(),5,'kein Leerlauf beim Blättern');assert.equal(await page.locator('.spinner').count(),0);
await page.getByText('Do 01.10. – Fr 02.10.',{exact:true}).waitFor();
assert.equal(calls.at(-1),'?from=2026-10-01');
await page.locator('.wk-head').getByRole('button',{name:'Heute',exact:true}).click();await page.getByText('Do 24.09. – Mi 30.09.',{exact:true}).waitFor();
// Zurück: Rückblick statt Überblick, Link zu Ich, Rückmelden.
await page.getByRole('button',{name:'Fünf Schultage zurück'}).click();
await page.getByRole('heading',{name:'Rückblick'}).waitFor();
assert.equal(calls.at(-1),'?before=2026-09-24');
await page.getByText('120 Vokabeln geübt, 101 richtig').waitFor();
if(process.env.SCHOOL_SCREENSHOT_DIR){await page.setViewportSize({width:320,height:1400});await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'week-past-320.png'),fullPage:true});await page.setViewportSize({width:390,height:844});}
assert.equal(await page.getByText(/€|KI-Kosten/).count(),0);
assert.equal(await page.getByRole('link',{name:'Serie und Abzeichen unter Ich'}).getAttribute('href'),'#/ich');
await page.locator('section.fb').getByRole('heading',{name:'Noch zurückmelden: 1 Stunde'}).waitFor();
assert.equal(await page.getByRole('button',{name:'Fünf Schultage zurück'}).isDisabled(),true);
const pastDay=page.locator('.day[data-date="2026-09-22"]');await pastDay.locator('.day-btn').click();
assert.ok(await pastDay.locator('.ds-faces').count()>0,'vergangene Stunden lassen sich zurückmelden');
// Wischen blättert.
await page.evaluate(()=>{const el=document.querySelector('.wk');const t=(x)=>[new Touch({identifier:1,target:el,clientX:x,clientY:300})];
  el.dispatchEvent(new TouchEvent('touchstart',{touches:t(300),changedTouches:t(300),bubbles:true}));el.dispatchEvent(new TouchEvent('touchend',{touches:[],changedTouches:t(100),bubbles:true}));});
await page.waitForFunction(()=>document.body.innerText.includes('Die nächsten Tage auf einen Blick'));
assert.equal(calls.at(-1),'?from=2026-09-24');
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);}
assert.deepEqual(errors,[]);
console.log('PASS: rolling header, glance with deviations, exam readiness and homework, feedback faces, strip and grid with parallel lessons, expand in place, paging without flicker, review, swipe, responsive layout');
}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exit(1)});
