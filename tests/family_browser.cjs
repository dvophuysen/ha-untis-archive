const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const f=path.join(root,req.url==='/'?'index.html':req.url);try{res.setHeader('Content-Type',f.endsWith('.js')?'text/javascript':f.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(f));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4180,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
try {
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});
page.setDefaultTimeout(6000); const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});
await page.clock.install({time:new Date('2026-09-14T14:00:00+02:00')});
let fail=false;
await page.route('**/api/**',async route=>{
const u=new URL(route.request().url()).pathname;let status=200,body={};
const id=u.includes('/accounts/2/')?2:1;
if(u==='/api/me')body={id:1,role:'parent',accounts:[{id:1,name:'Kind A'},{id:2,name:'Kind B'}]};
else if(u==='/api/dashboard')body={today:'2026-09-14',kids:[1,2].map(i=>({account_id:i,name:i===1?'Kind A':'Kind B',now:{icon:'☀️',label:'Schulschluss'},exams:[],support:[],tasks:{open_count:i===1?1:0,items:i===1?[{id:1,title:'Brüche',due_date:'2026-09-13',urgency:'overdue'}]:[]},plan:{columns:[],period_times:[]},feedback_gap:{total_lessons:0}}))};
else if(u.endsWith('/subjects'))body={subjects:[{subject_id:7,name:'Politik'},{subject_id:8,name:'Mathematik'}]};
else if(u.endsWith('/oral-suggestions'))body={groups:[{subject_id:8,uncertain_topics:1,feedback_count:3,understood_topics:0,items:[{lesson_id:'topic:one',lstext:'Gleichungen lösen',date:'2026-09-10',url:'#/learning?goal=topic:one',source_count:3,sources:[{date:'2026-09-10',rating:2},{date:'2026-09-10',rating:1},{date:'2026-08-17',rating:1}]}]}]};
else if(u.endsWith('/today'))body={date:'2026-09-14',lessons:[{id:1,end_time:1200,checkin:id===2?{rating:1}:null},{id:2,end_time:1500}],next:{date:'2026-09-15'}};
else if(u.includes('/packing/')) {if(fail&&id===2){status=503;body={detail:'Materialstand nicht verfügbar'};}else body={school_day:'2026-09-15',items:[{},{}],confirmed_count:id===1?1:2};}
await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
});
await page.goto('http://127.0.0.1:4180/#/overview');
const a=page.getByLabel('Tagescheck für Kind A'),b=page.getByLabel('Tagescheck für Kind B');
await a.getByText('1 von 2 Fächern abgehakt').waitFor().catch(async e=>{console.log(await page.locator('body').innerText());throw e;});await b.getByText('2 von 2 Fächern abgehakt').waitFor();
await a.getByText('1 Rückmeldung offen',{exact:true}).waitFor();await b.getByText('Keine Rückmeldungen offen',{exact:true}).waitFor();
assert.equal(await page.getByText('überfällig',{exact:true}).count(),1);
assert.equal(await page.getByText('verpasst',{exact:true}).count(),0);
for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
fail=true;await page.reload();await page.getByRole('alert').getByText('Materialstand nicht verfügbar').waitFor();assert.equal(await page.getByText('2 von 2 Fächern abgehakt').count(),0);
await page.goto('http://127.0.0.1:4180/#/subjects');await page.getByRole('heading',{name:'Deine Fächer',exact:true}).waitFor();await page.getByText('1 Thema zum Klären').waitFor();assert.equal(await page.getByRole('heading',{name:'Gleichungen lösen',exact:true}).count(),1);await page.getByText('Rückmeldungen ansehen').click();assert.equal(await page.getByText(/Noch schwierig/).count(),2);for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'subjects-redesign.png'),fullPage:true});assert.deepEqual(errors,[]);console.log('PASS: two children, independent counts, ended lessons only, no false failure claim, source failure, responsive layout');
}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exit(1)});
