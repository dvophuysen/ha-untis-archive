// Startseite der Eltern (D166). Build the frontend first. Requires playwright-core;
// optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
const go=(page,section=null,args=[])=>({page,args,section});
const stages=(sitzt,wackelt,angefangen,neu)=>({sitzt,wackelt,angefangen,neu});
const boardA={status:{level:'warn',label:'Nachsteuern',reasons:['Mathematik: noch nichts geübt']},evening:false,
  ok:['Aufgaben bis morgen erledigt','Tasche für Fr gepackt','6/6 Stunden bewertet'],acute:[],
  exams:[{exam_key:'cal:m',date:'2026-09-28',day:'Mo 28.09.',days_until:4,subject_name:'MATHEMATIK',kind:'Arbeit',topics:4,practiced:3,stages:stages(1,1,1,1),missing:0,material_ok:true,go:go('klausuren','arbeit-cal:m')},
         {exam_key:'cal:mu',date:'2026-10-05',day:'Mo 05.10.',days_until:11,subject_name:'MUSIK',kind:'Lernkontrolle',topics:1,practiced:0,stages:stages(0,0,0,1),missing:0,material_ok:true,go:go('klausuren','arbeit-cal:mu')}],
  later:[{exam_key:'cal:e',day:'Fr 30.10.',days_until:36,subject_name:'ENGLISCH',topics:3,missing:2,go:go('klausuren','arbeit-cal:e')},
         {exam_key:'cal:l',day:'Mo 16.11.',days_until:53,subject_name:'LATEIN',topics:0,missing:0,go:go('klausuren','arbeit-cal:l')}],
  watch:[{key:'hard-8',tone:'warn',icon:'∿',title:'Mathematik fällt schwer',detail:'4 von 10 bewerteten Stunden der letzten 3 Wochen als schwer bewertet',go:go('subject',null,['8'])}]};
const boardB={status:{level:'bad',label:'Eingreifen',reasons:['Aufgaben überfällig']},evening:false,ok:[],
  acute:[{key:'overdue',tone:'bad',icon:'⚠️',title:'1 Aufgabe überfällig',detail:'Brüche',go:go('today','aufgaben')},
         {key:'retake',tone:'warn',icon:'📷',title:'2 Seiten neu fotografieren',detail:'„Zerlegen“ · unscharf',go:go('materialien','fotos')}],
  exams:[{exam_key:'cal:s',date:'2026-10-01',day:'Do 01.10.',days_until:7,subject_name:'ENGLISCH',kind:'Sprechprüfung',topics:4,practiced:0,stages:stages(0,0,0,4),missing:5,material_ok:false,go:go('klausuren','arbeit-cal:s')}],
  later:[],watch:[]};
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const f=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',f.endsWith('.js')?'text/javascript':f.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(f));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4180,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
try {
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});
page.setDefaultTimeout(6000); const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
await page.clock.install({time:new Date('2026-09-24T14:00:00+02:00')});
await page.route('**/api/**',async route=>{
const u=new URL(route.request().url()).pathname;let body={};
if(u==='/api/me')body={id:1,role:'parent',accounts:[{id:1,name:'Kind A'},{id:2,name:'Kind B'}]};
else if(u==='/api/dashboard')body={today:'2026-09-24',kids:[{account_id:1,name:'Kind A',board:boardA},{account_id:2,name:'Kind B',board:boardB}]};
else if(u==='/api/parent-report')body={weekday:6,at:'18:00',targets:[],services:[]};
await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});
});
await page.goto('http://127.0.0.1:4180/#/overview');
const a=page.getByLabel('Stand von Kind A'),b=page.getByLabel('Stand von Kind B');
await a.waitFor();
assert.equal(await a.getAttribute('data-status'),'warn');assert.equal(await b.getAttribute('data-status'),'bad');
await a.getByText('Nachsteuern',{exact:true}).waitFor();await b.getByText('Eingreifen',{exact:true}).waitFor();
await a.getByText('✓ Aufgaben bis morgen erledigt · Tasche für Fr gepackt · 6/6 Stunden bewertet').waitFor();
assert.equal(await b.locator('.okline').count(),0);
// Arbeiten chronologisch, Balken nur mit bekannten Themen, Später in einer Zeile.
assert.deepEqual(await a.locator('.exam .l1 b').allInnerTexts(),['Mathematik-Arbeit Mo 28.09.','Musik-Lernkontrolle Mo 05.10.']);
assert.equal(await a.locator('.exam').first().locator('.stack i').count(),4);
await a.getByText('3 von 4 Themen geübt').waitFor();await a.getByText('in 4 Tagen').waitFor();
await a.getByText('2 fehlen').waitFor();await a.getByText('Themen unbekannt').waitFor();
await b.getByText('5 Seiten fehlen').waitFor();assert.equal(await b.locator('.badge.bad').count(),1);
assert.equal(await page.getByText('Diese Woche',{exact:true}).count(),0);assert.equal(await page.getByText(/Stundenplan/).count(),0);
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
if(process.env.SCHOOL_SCREENSHOT_DIR){await page.setViewportSize({width:390,height:1400});await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'family-board.png'),fullPage:true});}
assert.deepEqual(errors,[]);
// Schnellzugriffe: Kind wechseln, Seite und Abschnitt im Hash. Die Zielseiten
// haben hier keine Daten; geprüft wird nur der Sprung.
await b.getByText('1 Aufgabe überfällig').click();
assert.equal(await page.evaluate(()=>location.hash),'#/today?s=aufgaben');
assert.equal(await page.evaluate(()=>localStorage.getItem('activeAccountId')||''),'2');
await page.goto('http://127.0.0.1:4180/#/overview');await a.waitFor();
await a.getByText('Musik-Lernkontrolle Mo 05.10.').click();
assert.equal(await page.evaluate(()=>location.hash),'#/klausuren?s=arbeit-cal%3Amu');
await page.goto('http://127.0.0.1:4180/#/overview');await a.waitFor();
await a.getByText('Mathematik fällt schwer').click();
assert.equal(await page.evaluate(()=>location.hash),'#/subject/8');
console.log('PASS: status per child, all-done line, exams in order with bar, later line, jump links with child and section, responsive layout');
}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exit(1)});
