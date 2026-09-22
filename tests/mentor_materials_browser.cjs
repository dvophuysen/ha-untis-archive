// Production build; synthetic fixtures: several filed pages picked into a homework chat.
const {chromium}=require('playwright-core');const http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'../schul_cockpit/frontend/dist');
 const server=http.createServer((req,res)=>{let file=path.join(root,req.url.split('?')[0]==='/'?'index.html':req.url.split('?')[0]);try{res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));}catch{res.statusCode=404;res.end();}});await new Promise(r=>server.listen(4181,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.SCHOOL_TEST_CHROMIUM,args:['--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--no-zygote']});
 const page=await browser.newPage({viewport:{width:390,height:844},serviceWorkers:'block'});const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.log('PAGE ERROR',e.message);});page.setDefaultTimeout(8000);
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC','base64');
 const items=[{id:11,title:'Heft S. 12',label:'Heft S. 12',mime_type:'image/png',date:'2026-09-18',reason:'hängt an der Aufgabe',group:'linked',chosen:false},
  {id:12,title:'Arbeitsblatt Nomen',label:'',mime_type:'application/pdf',date:'2026-09-17',reason:'Blatt desselben Fachs vom 2026-09-17',group:'suggested',chosen:false},
  {id:13,title:'Heft S. 13',label:'Heft S. 13',mime_type:'image/png',date:'2026-09-16',reason:'',group:'subject',chosen:false}];
 const subjects=[{name:'Deutsch',count:3},{name:'Mathe',count:1}];let subjectAsked=null,chosen=[],version=1,added=null,turn=null,dropped=null;
 const session=()=>({id:7,version,subject:'Deutsch',goal:'Hilfe: Aufgabe 4',label:'Aufgabe 4',mode:'homework_help',task_id:42,untimed:true,status:'active',messages:[{id:1,role:'assistant',text:'Wobei hängst du?',payload:{choices:[]},author:null}].concat(turn?[{id:2,role:'user',text:'Meine Seiten ansehen',payload:{material_ids:turn.ids},author:'kind'}]:[]),attachments:[],quiz:[],quiz_open:[],
   materials:chosen.map(id=>{const x=items.find(y=>y.id===id);return {id,title:x.title,label:x.label,mime_type:x.mime_type,date:x.date,shown:!!turn&&turn.ids.includes(id)};})});
 await page.route('**/api/**',async route=>{const req=route.request(),u=new URL(req.url()).pathname;let body={},status=200;
  if(u.endsWith('/file'))return route.fulfill({status:200,contentType:'image/png',body:png});
  if(u==='/api/me')body={accounts:[{id:1,name:'Beispielkind'}],role:'child',is_admin:false};
  else if(u.endsWith('/settings'))body={default_daily_budget_minutes:60,budget_overrides:{},auto_budget:false,erlass:{}};
  else if(u.endsWith('/reminders'))body={enabled:false,remind_at:null,devices:0,can_manage:false};
  else if(u.endsWith('/mentor'))body={profile:{ai_enabled:true},can_manage:false,can_write:true,subjects:['Deutsch'],errors:[],sessions:[],progress:[],homework_choices:[],shared_plan:{goals:[],today:{actions:[],planned_minutes:0},week:[],deferred:[]},budget:{opening_confirmed:true,used_eur:0,limit_eur:50,rate_available:true},enabled:true};
  else if(u.endsWith('/sessions')&&req.method()==='POST')body=session();
  else if(u.endsWith('/sessions/7/materials')&&req.method()==='GET'){const wanted=new URL(req.url()).searchParams.get('subject');subjectAsked=wanted;
   body=wanted==='Mathe'?{subject:'Mathe',task_subject:'',subjects,max:12,items:[{id:21,title:'Brüche',label:'',mime_type:'image/png',date:'2026-09-15',reason:'',group:'subject',chosen:false}]}
    :{subject:'',task_subject:'',subjects,max:12,items:items.map(x=>({...x,chosen:chosen.includes(x.id)}))};}
  else if(u.endsWith('/sessions/7/materials')&&req.method()==='POST'){added=req.postDataJSON().material_ids;chosen=[...chosen,...added];version++;body=session();}
  else if(/\/sessions\/7\/materials\/\d+$/.test(u)){dropped=Number(u.split('/').pop());chosen=chosen.filter(x=>x!==dropped);version++;body=session();}
  else if(u.endsWith('/sessions/7/turn')){const b=req.postDataJSON();assert.equal(b.version,version);turn={ids:chosen.filter(id=>!(turn?.ids||[]).includes(id)),text:b.text};version++;body=session();}
  else if(u.endsWith('/pause'))body=session();
  await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('http://127.0.0.1:4181/#/learning?help=42');
 const sendButton=page.getByRole('button',{name:'Senden',exact:true});await sendButton.waitFor();assert(await sendButton.isDisabled());
 await page.getByRole('button',{name:'Aus Materialien',exact:true}).click();
 await page.getByText('Hängt schon an der Aufgabe',{exact:true}).waitFor();await page.getByText('Weitere Seiten im Fach',{exact:true}).waitFor();
 // Fach nicht erkannt: Hinweis und Auswahl von Hand, Angekreuztes bleibt beim Wechsel.
 await page.getByText('Das Fach dieser Hausaufgabe ist nicht erkannt. Wähle es oben aus.',{exact:true}).waitFor();
 await page.getByRole('checkbox',{name:/Heft S\. 12/}).check();
 await page.getByRole('combobox',{name:/^Fach/}).selectOption('Mathe');await page.getByRole('checkbox',{name:/Brüche/}).waitFor();assert.equal(subjectAsked,'Mathe');
 await page.getByRole('button',{name:'1 Seite einbinden',exact:true}).waitFor();
 await page.getByRole('combobox',{name:/^Fach/}).selectOption('Deutsch');await page.getByRole('checkbox',{name:/Heft S\. 13/}).waitFor();await page.getByRole('checkbox',{name:/Heft S\. 13/}).check();
 if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'mentor-materials-picker.png'),fullPage:true});
 await page.getByRole('button',{name:'2 Seiten einbinden',exact:true}).click();
 await page.getByText(/Eingebunden: 2 Seiten · 2 neu/).waitFor().catch(async e=>{console.log(await page.locator('body').innerText());throw e;});assert.deepEqual(added,[11,13]);
 for(const width of [320,390,768]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'overflow '+width);}
 if(process.env.SCHOOL_SCREENSHOT_DIR)await page.screenshot({path:path.join(process.env.SCHOOL_SCREENSHOT_DIR,'mentor-materials.png'),fullPage:true});
 // Frisch eingebundene Seiten sind schon eine Nachricht.
 assert(!(await sendButton.isDisabled()));await sendButton.click();
 await page.getByText('2 Seiten aus deinen Materialien eingebunden',{exact:true}).waitFor();assert.equal(turn.text,'');assert(await sendButton.isDisabled());
 await page.getByRole('button',{name:'Heft S. 13 wieder lösen',exact:true}).click();await page.getByText(/Eingebunden: 1 Seite$/).waitFor();assert.equal(dropped,13);
 // Schon eingebundene Seiten sind in der Auswahl gesetzt und nicht noch einmal wählbar.
 await page.getByRole('button',{name:'Aus Materialien',exact:true}).click();const first=page.getByRole('checkbox',{name:/Heft S\. 12/});await first.waitFor();assert(await first.isChecked());assert(await first.isDisabled());
 assert.deepEqual(errors,[]);console.log('PASS: several filed pages picked, embedded, sent without text, removed again');await browser.close();await new Promise(r=>server.close(r));
})().catch(e=>{console.error(e);process.exit(1);});
