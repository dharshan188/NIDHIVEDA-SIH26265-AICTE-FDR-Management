import {BASE,apiFor,launch,newContext,login,open,settle,watchConsole} from './lib.mjs';
const browser=await launch(),ctx=await newContext(browser,{width:1536,height:1024}),errors=[];
const {csrf}=await login(ctx,'aicte'),api=apiFor(ctx,csrf),page=await ctx.newPage();watchConsole(page,errors);
const fid=(await api.get('/fdrs?size=1&sort=submitted&bucket=pending')).items[0].id;
for(const [name,path,selector] of [['07-fdr-detail-documents',`/aicte/fdr/${fid}`,'.doc-list'],['08-fdr-detail-timeline-no-gap',`/aicte/fdr/${fid}`,'.panel:has(.timeline)'],['11-notification-health','/aicte/notification-health',null]]) {
 await open(page,BASE+path);await settle(page,1200);
 if(selector){await page.locator(selector).first().evaluate(e=>e.scrollIntoView({block:'start'}));await page.evaluate(()=>window.scrollBy(0,-90));await page.waitForTimeout(500);}
 await page.screenshot({path:`docs/screenshots/final/${name}.png`});console.log(`Refreshed ${name}.png at 1536x1024, live record ${fid}`);
}
const history=await api.get(`/fdrs/${fid}/timeline`);console.log('Actual renewal gaps:',JSON.stringify(history.gaps));if(history.gaps.length)throw Error('Unexpected gap in no-gap screenshot');
const h=await api.get('/nudge/health?days=30');console.log('Current email counts:',JSON.stringify(h.by_channel.email));
for(const [c,v]of Object.entries(h.by_channel))if((v.sent??0)>v.total)throw Error(`${c} sent exceeds total`);
await ctx.close();await browser.close();console.log(`console errors: ${errors.length}`);process.exit(errors.length?1:0);
