// Synthetic subjects: status order, truthful unknowns, drilldown and account switch.
const {chromium}=require('playwright-core');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{const file=path.join(root,req.url==='/'?'index.html':req.url);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});
 await new Promise(r=>server.listen(4182,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844},serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let fail=false;
 const topic={lesson_id:'topic-1',date:'2026-09-10',rating:2,lstext:'Argumentieren und Debattieren',url:'#/learning?goal=topic-1',source_count:2,sources:[{date:'2026-09-01',start_time:800,rating:1},{date:'2026-09-10',start_time:900,rating:2}]};
 await page.route('**/api/**',async route=>{const u=new URL(route.request().url()).pathname;let body={},status=200;
 if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
 else if(u.endsWith('/subjects'))body={subjects:[{subject_id:1,name:'Deutsch'},{subject_id:2,name:'Englisch'},{subject_id:3,name:'Physik'},{subject_id:4,name:'Werte und Normen'}]};
 else if(u.endsWith('/oral-suggestions')){if(fail){status=503;body={detail:'Fächer vorübergehend nicht verfügbar'};}else body={groups:[
 {subject_id:1,understood_topics:1,partial_topics:1,difficult_topics:1,unrated_topics:0,topics:[topic],feedback_history:[{lesson_id:1,date:'2026-09-01',rating:1},{lesson_id:2,date:'2026-09-10',rating:2}]},
 {subject_id:2,understood_topics:4,partial_topics:1,difficult_topics:0,unrated_topics:1,topics:[],feedback_history:[{lesson_id:3,date:'2026-09-01',rating:2},{lesson_id:4,date:'2026-09-10',rating:3}]}
 ],errors:[]};}
 await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://127.0.0.1:4182/#/subjects');await page.locator('.subject-row').first().waitFor();
 assert.deepEqual(await page.locator('.subject-name').allTextContents(),['🇬🇧 Englisch','🖋️ Deutsch','💡 Physik','🤝 Werte und Normen']);
 assert.equal(await page.locator('.subject-panel').count(),0);assert.equal(await page.locator('.subject-bar').count(),2);
 await page.getByRole('button',{name:/Deutsch/}).click();await page.getByRole('heading',{name:'Argumentieren und Debattieren'}).waitFor();
 assert.equal(await page.getByRole('link',{name:'Üben',exact:true}).getAttribute('href'),'#/learning?goal=topic-1');
 await page.getByText('Selbsteinschätzungen aus dem Unterricht · 2 Einträge').click();await page.getByText('Einzelne Rückmeldungen zu Stunden in zeitlicher Reihenfolge.',{exact:false}).waitFor();
 await page.getByRole('button',{name:/Physik/}).click();assert.equal(await page.locator('.subject-panel').count(),1);assert.equal(await page.getByRole('heading',{name:'Argumentieren und Debattieren'}).count(),0);
 await page.getByRole('button',{name:/Physik/}).press('Enter');assert.equal(await page.locator('.subject-panel').count(),0);
 for(const width of [320,390,430,768]){await page.setViewportSize({width,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);}
 await page.setViewportSize({width:390,height:844});
 if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'subjects-390.png'),fullPage:true});
 await page.emulateMedia({colorScheme:'dark'});if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'subjects-dark.png'),fullPage:true});
 await page.evaluate(()=>document.documentElement.style.fontSize='22px');await page.getByRole('button',{name:/Deutsch/}).click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'large text overflow');
 fail=true;await page.reload();await page.getByRole('alert').waitFor();assert.equal(await page.locator('.subject-row').count(),0);
 assert.deepEqual(errors,[]);console.log('PASS: status order, neutral unknowns, sources/learning links, one drilldown, keyboard, errors, 320/390/430/768px and large text');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exit(1)});
