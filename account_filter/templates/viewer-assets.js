// Keep image bytes out of report initialization and load a few files at a time.
const assetKeys=new WeakMap();
function assetKey(file){if(!assetKeys.has(file))assetKeys.set(file,crypto.randomUUID());return assetKeys.get(file)}
function assetReferences(payload){
 const refs=[];for(const row of payload.rows){refs.push([row,'snapshot']);for(const video of row.videos)refs.push([video,'cover'])}
 if(payload.cover_audit){refs.push([payload.cover_audit,'csv']);for(const row of payload.cover_audit.rows||[]){refs.push([row,'response']);for(const video of row.videos||[])refs.push([video,'cover'])}}
 return refs;
}
const assetBroker={items:new Map(),queue:[],active:0};
async function readViewerAsset(item){
 if(item.file)return item.file;
 if(!session.db||!item.key)throw Error('本地文件副本不可用，请重新选择采集数据目录。');
 return new Promise((resolve,reject)=>{const request=session.db.transaction('assets').objectStore('assets').get(item.key);request.onsuccess=()=>request.result?resolve(request.result):reject(Error('本地文件副本缺失，请重新选择采集数据目录。'));request.onerror=()=>reject(request.error)});
}
async function serveViewerAssets(){
 while(assetBroker.active<4&&assetBroker.queue.length){const request=assetBroker.queue.shift();if(request.token!==model.reportToken)continue;assetBroker.active++;
  (async()=>{try{const file=await readViewerAsset(request.item);if(request.token===model.reportToken)$('report').contentWindow.postMessage({type:'viewer-asset',token:request.token,id:request.id,file},'*')}
   catch(error){if(request.token===model.reportToken)$('report').contentWindow.postMessage({type:'viewer-asset',token:request.token,id:request.id,error:'本地文件无法读取，请重新选择采集数据目录。'},'*')}
   finally{assetBroker.active--;serveViewerAssets()}})();
 }
}
window.addEventListener('message',event=>{
 if(event.source!==$('report').contentWindow||event.data?.token!==model.reportToken||event.data?.type!=='viewer-asset-request')return;
 const item=assetBroker.items.get(event.data.id);if(!item)return;
 assetBroker.queue.push({item,id:event.data.id,token:event.data.token});serveViewerAssets();
});
