// Am freien Tag zeigen die Ringe auf „Heute“ den Stand des letzten Schultags
// (D205): Feedback zu den Freitagsstunden, die sich noch bewerten lassen.
// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const p=req.url.split('?')[0];const file=path.join(root,p==='/'?'index.html':p);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4183,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.clock.install({time:new Date('2026-09-26T10:00:00+02:00')});
const friday=[{id:31,date:'2026-09-25',subject_name:'Mathematik',subject_short:'MA',start_time:800,end_time:845,start_hhmm:'08:00',end_hhmm:'08:45',is_cancelled:false,was_absent:false,checkin:{rating:3,note:null}},
  {id:32,date:'2026-09-25',subject_name:'Mathematik',subject_short:'MA',start_time:850,end_time:935,start_hhmm:'08:50',end_hhmm:'09:35',is_cancelled:false,was_absent:false,checkin:{rating:3,note:null}},
  {id:33,date:'2026-09-25',subject_name:'Englisch',subject_short:'EN',start_time:1130,end_time:1215,start_hhmm:'11:30',end_hhmm:'12:15',is_cancelled:false,was_absent:false,checkin:null}];
let rated=[];
await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};
 if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
 else if(u.endsWith('/today'))body={date:'2026-09-26',lessons:[],carry_lessons:{date:'2026-09-25',lessons:friday},feedback_backlog:[{id:21,date:'2026-09-24',subject_name:'Physik',subject_short:'PH',start_time:800,end_time:845,start_hhmm:'08:00',end_hhmm:'08:45',is_cancelled:false,was_absent:false,checkin:null},{id:22,date:'2026-09-24',subject_name:'Physik',subject_short:'PH',start_time:850,end_time:935,start_hhmm:'08:50',end_hhmm:'09:35',is_cancelled:false,was_absent:false,checkin:null}],next:{date:'2026-09-28',lessons:[{id:40,subject_name:'Deutsch',start_hhmm:'08:00',end_time:845,room:'1'}]},
   study_plan:{day:'2026-09-25',steps:[{key:'a',kind:'dialog',title:'Brüche üben',subject:'Mathematik',done:true},{key:'b',kind:'dialog',title:'Vokabeln',subject:'Englisch',done:false}],engpass:false,tight:[],free_day:true,frozen:true,read_only:false,done:1,total:2,carry:{from:'2026-09-25',until:'2026-09-27',open:1}},
   summary:{},upcoming_exams:[],new_results:[],retakes:[],photo_requests:[],day_close:{closed:null,reliability:null}};
 else if(u.endsWith('/tasks'))body={tasks:[]};
 else if(u.includes('/packing/'))body={school_day:'2026-09-28',items:[{key:'subject:de',label:'Deutsch',done:true,revision:1}],schedule:[],status:'packed',confirmed_count:1};
 else if(u.endsWith('/checkin')){rated.push(Number(u.split('/').at(-2)));body={rating:req.postDataJSON().rating,note:null};}
 else if(u.endsWith('/rewards'))body={streak:{current:1,record:1},today:{},total:1,badges:[],celebrate:[],next_up:[]};
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});});
await page.goto('http://127.0.0.1:4183/#/today');
const ring=page.getByRole('button',{name:/^Feedback: /});await ring.waitFor({timeout:8000});
// Freitag: Doppelstunde bewertet, Englisch offen; dazu die vergessene
// Physik-Doppelstunde vom Donnerstag (D210): 1 von 3.
assert.equal(await ring.getAttribute('aria-label'),'Feedback: 1 von 3');
await page.getByRole('heading',{name:/^Noch nachholen/}).waitFor();
assert.match(await page.locator('.backlog-head').innerText(),/1 Stunde/);
assert.equal(await page.locator('.backlog-day').innerText(),'Do. 24.09.');
assert.equal(await page.getByRole('button',{name:'Lernen: 1 von 2'}).count(),1);
await page.getByRole('heading',{name:/^Stunden vom Freitag/}).waitFor();
assert.equal(await page.getByText('Stunden von heute').count(),0);
assert.deepEqual(errors,[]);
console.log('PASS: weekend rings show the Friday state, Friday lessons can still be rated, forgotten feedback stays open to catch up');
await browser.close();server.close();
})().catch(e=>{console.error(e);process.exit(1);});
