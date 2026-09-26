// Teamunterricht: zwei Einträge im selben Fach zur selben Zeit (Musik mit zwei
// Lehrkräften) sind eine Stunde. „Heute“ und die Woche zeigen eine Zeile, eine
// Bewertung speichert beide Einträge, der Ring zählt sie einmal. Parallele
// Stunden in verschiedenen Fächern (Religion, Werte und Normen) bleiben getrennt.
// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
const fmt=t=>`${String(Math.floor(t/100)).padStart(2,'0')}:${String(t%100).padStart(2,'0')}`;
const les=(id,date,s,e,subject,extra={})=>({id,date,start_time:s,end_time:e,start_hhmm:fmt(s),end_hhmm:fmt(e),subject_name:subject,subject_short:subject.slice(0,2).toUpperCase(),
  room:'A1',is_cancelled:false,was_absent:false,is_irregular:false,is_room_substituted:false,exam:null,checkin:null,rating:null,caught_up:false,lstext:null,...extra});
const today=[les(10,'2026-09-24',800,845,'Religion',{subject_untis_id:1}),les(11,'2026-09-24',800,845,'Werte und Normen',{subject_untis_id:2}),
  les(12,'2026-09-24',1035,1120,'Musik',{subject_untis_id:7,teacher_name:'A',room:'M1'}),les(13,'2026-09-24',1035,1120,'Musik',{subject_untis_id:7,teacher_name:'B',room:'M2'})];
const backlog=[les(21,'2026-09-23',950,1035,'Musik',{subject_untis_id:7,teacher_name:'A'}),les(22,'2026-09-23',950,1035,'Musik',{subject_untis_id:7,teacher_name:'B'})];
const weekFb=[les(31,'2026-09-23',800,845,'Physik'),les(32,'2026-09-23',950,1035,'Musik',{subject_untis_id:7,teacher_name:'A'}),les(33,'2026-09-23',950,1035,'Musik',{subject_untis_id:7,teacher_name:'B'})];
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const p=req.url.split('?')[0];const file=path.join(root,p==='/'?'index.html':p);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4187,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
page.setDefaultTimeout(6000);
await page.clock.install({time:new Date('2026-09-24T14:00:00+02:00')});
let rated=[];const ratings={};
// Wie das Backend: Bewertungen bleiben stehen, eine bewertete Teamstunde fällt aus dem Nachholen.
const withCheckin=l=>({...l,checkin:ratings[l.id]?{rating:ratings[l.id],note:null}:null});
await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};
 if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
 else if(u.endsWith('/today'))body={date:'2026-09-24',lessons:today.map(withCheckin),carry_lessons:null,feedback_backlog:backlog.some(l=>ratings[l.id])?[]:backlog,next:{date:'2026-09-25',lessons:[{id:40,subject_name:'Deutsch',start_hhmm:'08:00',end_time:845,room:'1'}]},
   study_plan:{day:'2026-09-24',steps:[],engpass:false,tight:[],free_day:false,frozen:true,read_only:false,done:0,total:0},
   summary:{},upcoming_exams:[],new_results:[],retakes:[],photo_requests:[],day_close:{closed:null,reliability:null}};
 else if(u.endsWith('/tasks'))body={tasks:[]};
 else if(u.includes('/packing/'))body={school_day:'2026-09-25',items:[{key:'subject:de',label:'Deutsch',done:true,revision:1}],schedule:[],status:'packed',confirmed_count:1};
 else if(u.endsWith('/checkin')){const id=Number(u.split('/').at(-2));rated.push(id);ratings[id]=req.postDataJSON().rating;body={rating:req.postDataJSON().rating,note:null};}
 else if(u.endsWith('/rewards'))body={streak:{current:1,record:1},today:{},total:1,badges:[],celebrate:[],next_up:[]};
 else if(u.endsWith('/week/rolling'))body={today:'2026-09-24',default:true,mode:'ahead',range:{start:'2026-09-24',end:'2026-09-24'},prev_before:null,next_from:'2026-09-25',review:null,holiday:null,free:[],
   feedback:{count:2,days:[{date:'2026-09-23',label:'Mi 23.09.',lessons:weekFb}]},
   days:[{date:'2026-09-24',label:'Do 24.09.',is_today:true,is_past:false,assumed:true,week:39,holiday:null,strip:null,lessons:[],exams:[],tasks:[],tasks_open:0}]};
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});});

await page.goto('http://127.0.0.1:4187/#/today');
const ring=page.getByRole('button',{name:/^Feedback: /});await ring.waitFor({timeout:8000});
// Heute: Religion, Werte und Normen, Musik (eine Stunde); dazu Musik vom Mittwoch zum Nachholen.
assert.equal(await ring.getAttribute('aria-label'),'Feedback: 0 von 4');
const todayList=page.locator('.day-schedule').first();
assert.equal(await todayList.locator('.ds-row').count(),3,'Teamunterricht ist eine Zeile, parallele Fächer bleiben zwei');
assert.equal(await todayList.getByRole('group',{name:'Wie gut hast du Musik verstanden?'}).count(),1);
assert.equal(await todayList.locator('.ds-row',{hasText:'Musik'}).locator('.tag').count(),0,'keine „2 Std.“ für eine Teamstunde');
assert.match(await page.locator('.backlog-head').innerText(),/1 Stunde/);
await todayList.getByRole('group',{name:'Wie gut hast du Musik verstanden?'}).getByRole('button',{name:'Verstanden',exact:true}).click();
await page.waitForFunction(()=>document.querySelector('[aria-label^="Feedback: "]')?.getAttribute('aria-label')==='Feedback: 1 von 4');
assert.deepEqual(rated.sort(),[12,13],'eine Bewertung speichert beide Einträge');
// Religion bewertet: Werte und Normen bleibt offen.
rated=[];
await todayList.getByRole('group',{name:/Religion/}).getByRole('button',{name:'Verstanden',exact:true}).click();
await page.waitForFunction(()=>document.querySelector('[aria-label^="Feedback: "]')?.getAttribute('aria-label')==='Feedback: 2 von 4');
assert.deepEqual(rated,[10]);
assert.equal(await todayList.getByRole('group',{name:'Wie gut hast du Musik verstanden?'}).getByRole('button',{name:'Verstanden',exact:true}).getAttribute('aria-pressed'),'true');
// Nachholen: die Teamstunde vom Mittwoch ebenso; danach ist nichts mehr nachzuholen.
rated=[];
const late=page.locator('.day-schedule').nth(1);
await late.getByRole('button',{name:'Teilweise verstanden',exact:true}).click();
await page.waitForFunction(()=>document.querySelector('[aria-label^="Feedback: "]')?.getAttribute('aria-label')==='Feedback: 2 von 3');
assert.deepEqual(rated.sort(),[21,22]);
assert.equal(await page.locator('.backlog-head').count(),0);

// Woche: „Noch zurückmelden“ zählt die Teamstunde einmal, eine Bewertung trifft beide.
rated=[];
await page.goto('http://127.0.0.1:4187/#/week');
const fb=page.locator('section.fb');
await fb.getByRole('heading',{name:'Noch zurückmelden: 2 Stunden'}).waitFor();
assert.equal(await fb.locator('.ds-row').count(),2);
await fb.getByRole('group',{name:'Wie gut hast du Musik verstanden?'}).getByRole('button',{name:'Verstanden',exact:true}).click();
await fb.getByRole('heading',{name:'Noch zurückmelden: 1 Stunde'}).waitFor();
assert.deepEqual(rated.sort(),[32,33]);
for(const width of [320,390]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);}
assert.deepEqual(errors,[]);
console.log('PASS: team teaching is one lesson on Today and Week, one rating saves both entries, parallel subjects stay apart');
}finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
