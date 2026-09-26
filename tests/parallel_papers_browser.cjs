// Zwei Kurztests unabhängig voneinander (Nutzer 26.09.2026): Während der erste
// ausgewertet wird oder noch entsteht, lässt sich der zweite beginnen; „Los“ beim
// Kurztest eines Themas öffnet nie den Kurztest eines anderen Themas.
// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const p=req.url.split('?')[0];const file=path.join(root,p==='/'?'index.html':p);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4186,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
page.setDefaultTimeout(6000);
await page.clock.install({time:new Date('2026-09-26T13:30:00+02:00')});
const day='2026-09-26';
const kurz=(topic,title,attempt_id)=>({key:`paper:ma:kurz:${topic}`,kind:'paper',title,why:'Arbeit am 28.09.',subject:'Mathematik',exam_key:'ma',exam_date:'2026-09-28',format:'kurz',topic_id:topic,level:null,href:null,done:false,tight:true,attempt_id});
const posts=[];let release=null;
const attempt=(id,title)=>({id,status:'active',label:'Kurztest',format:'kurz',pages:[],read_only:false,answers:{},exam:{title,minutes:20,tasks:[{number:1,topic_id:12,afb:1,points:3,prompt:'Ergänze die Tabelle.'}]},feedback:{}});
await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};
 if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
 else if(u.endsWith('/today'))body={date:day,lessons:[],next:{date:'2026-09-28',lessons:[]},study_plan:{day,steps:[kurz(11,'Kurztest Mathematik: Gleichungen',5),kurz(12,'Kurztest Mathematik: Wertetabellen',null)],engpass:true,tight:[],free_day:true,frozen:true,read_only:false,done:0,total:2},summary:{},upcoming_exams:[],new_results:[],retakes:[],photo_requests:[],day_close:{closed:null,reliability:null}};
 else if(u.endsWith('/tasks'))body={tasks:[]};
 else if(u.endsWith('/rewards'))body={streak:{current:1,record:1},today:{},total:1,badges:[],celebrate:[],next_up:[]};
 else if(u==='/api/accounts/1/practice'&&req.method()==='GET')body={topics:[],ready:0,total:2,goal_afb:2,afb_names:{},formats:[],papers:[{id:9,attempt_id:5,paper_format:'kurz',status:'grading',created_at:day+'T13:09:00+02:00',topic_ids:[11],label:'Kurztest'}]};
 else if(u==='/api/accounts/1/practice'&&req.method()==='POST'){posts.push(req.postDataJSON());await new Promise(r=>{release=r;});body=attempt(10,'Kurztest Wertetabellen');}
 else if(u==='/api/accounts/1/practice/attempts/10')body=attempt(10,'Kurztest Wertetabellen');
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});});
await page.goto('http://127.0.0.1:4186/#/today');
const second=page.locator('.learn-step',{hasText:'Wertetabellen'});await second.waitFor();
await second.getByRole('button',{name:'Los'}).click();
await second.getByRole('button',{name:'Wird erstellt …'}).waitFor();
for(let i=0;i<50&&!posts.length;i++)await new Promise(r=>setTimeout(r,100));
assert.deepEqual(posts,[{exam_key:'ma',format:'kurz',topic_ids:[12],level:null}],'neuer Kurztest statt des Kurztests zu Gleichungen, der gerade ausgewertet wird');
// Während er entsteht, bleibt der andere Kurztest bedienbar.
const first=page.locator('.learn-step',{hasText:'Gleichungen'});
assert.equal(await first.getByRole('button',{name:'Weiter'}).isEnabled(),true);
release();
await page.getByText('Kurztest Wertetabellen').first().waitFor();
assert.deepEqual(errors,[]);
console.log('PASS: a second short test starts while the first is graded; each step opens only its own topic');
}finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
