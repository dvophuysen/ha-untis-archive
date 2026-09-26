// Pensum in der Runde (D215): Das Kind sieht beim Üben „Pensum: x von y“; ist
// es erreicht, meldet der Trainer das gleich und nennt den nächsten Schritt im
// Lernplan. Übt es eine andere Einheit, sagt er, welche fürs Pensum zählt.
// Build the frontend first. Requires playwright-core; optionally set SCHOOL_TEST_CHROMIUM. Uses synthetic API fixtures only.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
(async()=>{
const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
const server=http.createServer((req,res)=>{const p=req.url.split('?')[0];const file=path.join(root,p==='/'?'index.html':p);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});
await new Promise(r=>server.listen(4187,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:390,height:844},timezoneId:'Europe/Berlin',serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
page.setDefaultTimeout(6000);
await page.clock.install({time:new Date('2026-09-26T15:00:00+02:00')});
const summary={neu:10,wackelt:0,sitzt:0,gefestigt:0};
const mk=(name)=>({unit:name,label:name,words:10,pages:[],unread:0,sections:[],s1:summary,s2:summary,progress:{wrong:0,uncertain:0,secure:0,new:10,total:10},writing_progress:{wrong:0,uncertain:0,secure:0,new:10,total:10}});
let practiced=15;
const card=(i)=>({id:i,foreign_word:`verbum${i}`,meanings:['Wort'],grammar:'',forms:{},example:'',unit:'L2',label:'Begleitband',page:16,state:{}});
await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={};
 if(u==='/api/me')body={accounts:[{id:2,name:'Beispielkind'}],role:'child',is_admin:false};
 else if(u==='/api/accounts/2/vocab/pensum')body={day:'2026-09-26',items:[{subject:'LATEIN',unit:'L2',unit_label:'Lektion 2',target:16,practiced,done:practiced>=16,href:'#/vokabeln/LATEIN?unit=L2',exam_key:'t1',why:'Aus der Liste vom Freitag; geübt seit Freitag.',carry_from:'2026-09-25'}]};
 else if(u.endsWith('/learning/vocab/LATEIN/units'))body={subject:'LATEIN',language:{name:'Latein',code:null,into:false},units:[mk('L1'),mk('L2')],reading:0,overview:{started_units:1,total_units:2,progress:mk('L2').progress,writing_progress:mk('L2').writing_progress},speech:false,hesitation_seconds:12};
 else if(u.endsWith('/learning/vocab/LATEIN/cards'))body={cards:[card(1),card(2),card(3)]};
 else if(u.endsWith('/learning/vocab/attempts')){practiced+=1;body={result:'incorrect',feedback:'Weiß ich nicht. Im Buch: verbum · Wort',matched:null,word:card(1)};}
 else if(u.endsWith('/study-plan/today'))body={day:'2026-09-25',steps:[{key:'v',kind:'vocab',title:'Vokabeln',done:true},{key:'m',kind:'paper',title:'Einstiegstest Mathematik',done:false}]};
 else if(u.includes('/vocab/papers'))body={papers:[]};
 await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(body)});});
// Andere Einheit: der Hinweis, welche fürs Pensum zählt.
await page.goto('http://127.0.0.1:4187/#/vokabeln/LATEIN?unit=L1');
await page.getByRole('button',{name:'Latein → Deutsch'}).click();
await page.getByText('Fürs Pensum zählt',{exact:false}).waitFor();
assert.match(await page.locator('.pensum-other').innerText(),/Lektion 2 \(15 von 16\)/);
// Richtige Einheit: Fortschritt in der Runde, dann die Meldung.
await page.goto('http://127.0.0.1:4187/#/vokabeln/LATEIN?unit=L2');await page.reload();
await page.getByRole('button',{name:'Latein → Deutsch'}).click();
await page.getByText('Pensum: 15 von 16').waitFor();
await page.getByRole('button',{name:'Weiß ich nicht – als Fehler werten'}).click();
await page.getByRole('heading',{name:/Pensum geschafft: 16 von 16/}).waitFor();
await page.getByText('Einstiegstest Mathematik').waitFor();
assert.equal(await page.getByRole('link',{name:'Weiter im Lernplan'}).getAttribute('href'),'#/today?s=lernen');
await page.getByRole('button',{name:'Noch weiterüben'}).click();
await page.getByRole('heading',{name:/Pensum geschafft/}).waitFor({state:'detached'});
// Aus dem Lernplan gestartet (plan=1): nur diese Lektion, keine andere wählbar.
await page.goto('http://127.0.0.1:4187/#/vokabeln/LATEIN?unit=L2&plan=1');await page.reload();
await page.getByRole('heading',{name:'Aus deinem Lernplan: L2'}).waitFor();
assert.equal(await page.locator('button.unit').count(),1,'nur die Lektion aus dem Lernplan');
assert.equal(await page.locator('button.unit',{hasText:'L1'}).count(),0);
await page.getByRole('button',{name:'Freiwillig eine andere Einheit üben'}).click();
await page.locator('button.unit',{hasText:'L1'}).waitFor();
assert.ok(!page.url().includes('plan=1'),'freiwillig: ohne Sperre');
assert.deepEqual(errors,[]);
console.log('PASS: pensum progress in the round, reached message with next plan step, hint for a unit that does not count');
}finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
