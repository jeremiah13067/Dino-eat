const fs=require('fs'),path=require('path'),http=require('http');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');
const JSZip=require('jszip');
let sb3;
const server=http.createServer((req,res)=>{
 res.setHeader('Access-Control-Allow-Origin','*'); const pathname=decodeURIComponent(req.url.split('?')[0]);
 if(pathname==='/project.sb3'){res.end(sb3);return;}
 const filename=path.resolve(__dirname,'node_modules','.'+pathname);
 if(!filename.startsWith(path.resolve(__dirname,'node_modules')+path.sep)){res.writeHead(403);return res.end();}
 fs.readFile(filename,(err,data)=>{if(err){res.writeHead(404);res.end();}else{res.setHeader('Content-Type',filename.endsWith('.js')?'application/javascript':'application/octet-stream');res.end(data);}});
});
(async()=>{
 const zip=new JSZip();
 for(const name of fs.readdirSync(path.join(root,'reference')))if(name==='project.json'||/\.(svg|png|wav)$/.test(name))zip.file(name,fs.readFileSync(path.join(root,'reference',name)));
 sb3=await zip.generateAsync({type:'nodebuffer'});
 await new Promise(r=>server.listen(0,'127.0.0.1',r)); const base='http://127.0.0.1:'+server.address().port;
 const browser=await chromium.launch({...(process.env.CHROME_PATH?{executablePath:process.env.CHROME_PATH}:{}),headless:true,args:['--enable-unsafe-swiftshader']});
 try {
 const page=await browser.newPage({viewport:{width:480,height:360}});
 page.on('pageerror',e=>console.error('PAGE',e));
 await page.setContent('<style>body{margin:0}canvas{display:block}</style><canvas width="480" height="360"></canvas>');
 for(const pkg of ['scratch-vm','scratch-render','scratch-storage','scratch-svg-renderer'])await page.addScriptTag({url:base+'/'+pkg+'/dist/web/'+pkg+'.js'});
 
 const result=await page.evaluate(async(base)=>{
 const vm=new window.VirtualMachine();
 const renderer=new window.ScratchRender(document.querySelector('canvas'));
 vm.attachRenderer(renderer);
 vm.attachStorage(new window.ScratchStorage.ScratchStorage());
 vm.attachV2BitmapAdapter(new window.ScratchSVGRenderer.BitmapAdapter());
 await vm.loadProject(await (await fetch(base+'/project.sb3')).arrayBuffer());
 const rt=vm.runtime;rt.currentStepTime=1000/30;
 let time=0;rt.updateCurrentMSecs=()=>{rt.currentMSecs=time;};Math.random=()=>.5;
 const snapshots=[];
 function step(){time+=1000/30;rt._step();}
 function capture(label){snapshots.push({label,time,variables:Object.fromEntries(Object.values(rt.getTargetForStage().variables).map(v=>[v.name,v.value])),targets:rt.targets.map(t=>({name:t.getName(),x:t.x,y:t.y,costume:t.currentCostume,original:t.isOriginal,visible:t.visible})),threadHats:rt.threads.filter(t=>!t.updateMonitor).map(t=>t.topBlock)});}
 vm.greenFlag();step();capture('initial');window.initialPNG=document.querySelector('canvas').toDataURL();
 for(const key of ['d','w','a','s','d']){vm.postIOData('keyboard',{key,isDown:true});step();vm.postIOData('keyboard',{key,isDown:false});}capture('keys');
 while(time<1100)step();capture('one_second');while(time<5100)step();capture('five_seconds');
 window.fivePNG=document.querySelector('canvas').toDataURL();
 vm.greenFlag();step();capture('restart');vm.stopAll();
 const collisionGrid={};
 const dinosaur=rt.getSpriteTargetByName('Dinosaur1');dinosaur.setXY(0,0);
 for(const name of ['Apple','Cake','Cheesy Puffs','Muffin','Watermelon','Rocks']){
   const food=rt.getSpriteTargetByName(name);if(name==='Rocks')food.setCostume(0);
   const samples=[];
   for(let y=-120;y<=140;y+=10)for(let x=-140;x<=180;x+=10){food.setXY(x,y);samples.push([x,y,food.isTouchingSprite('Dinosaur1')]);}
   collisionGrid[name]=samples;
 }
 const collisionAssets={};
 for(const target of rt.targets.filter(t=>t.isOriginal&&!t.isStage)){
  target.setXY(0,0);target.setVisible(true);
  for(let i=0;i<target.sprite.costumes.length;i++){
   target.setCostume(i);const drawable=renderer._allDrawables[target.drawableID];
   drawable.updateCPURenderAttributes();const bounds=drawable.getAABB();
   const left=Math.floor(bounds.left),right=Math.ceil(bounds.right),top=Math.ceil(bounds.top),bottom=Math.floor(bounds.bottom);
   const width=right-left+1,height=top-bottom+1;
   if(!(width>1&&height>1))continue;
   const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
   const ctx=canvas.getContext('2d'),data=ctx.createImageData(width,height);
   for(let py=0;py<height;py++)for(let px=0;px<width;px++)if(drawable.isTouching([left+px,top-py])){
    const pos=(py*width+px)*4;data.data[pos]=255;data.data[pos+1]=255;data.data[pos+2]=255;data.data[pos+3]=255;
   }
   ctx.putImageData(data,0,0);
   const key=target.getName()+':'+i;
   collisionAssets[key]={offset:[left,-top],png:canvas.toDataURL()};
  }
 }
 return {collisionAssets,collisionGrid,engine:'scratch-vm@5.0.300',renderer:'scratch-render WebGL in headless Chrome',audio:false,rng:.5,snapshots};
 },base);
 const masks={};fs.mkdirSync(root+'/assets/collision',{recursive:true});
 for(const [key,value] of Object.entries(result.collisionAssets)){
  const filename=key.replace(/[^a-zA-Z0-9]/g,'_')+'.png';
  fs.writeFileSync(root+'/assets/collision/'+filename,Buffer.from(value.png.split(',')[1],'base64'));
  masks[key]={file:'collision/'+filename,offset:value.offset};
 }
 delete result.collisionAssets;
 fs.writeFileSync(root+'/reference/collision_metadata.json',JSON.stringify(masks,null,2));
 fs.writeFileSync(root+'/verification/scratch_vm_reference.json',JSON.stringify(result,null,2));
 for(const [key,file] of [['initialPNG','scratch_initial.png'],['fivePNG','scratch_five_seconds.png']]){
 const data=await page.evaluate(key=>window[key],key);fs.writeFileSync(root+'/verification/'+file,Buffer.from(data.split(',')[1],'base64'));}
 console.log('Reference captured:',result.snapshots.length,'snapshots and',Object.values(result.collisionGrid).flat().length,'collision probes');
 } finally {await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1});


