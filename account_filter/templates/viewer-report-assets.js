// Local IDs remain in D; Blob URLs exist only while their DOM evidence is used.
const viewerPlaceholder='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
const viewerURLs=new Map(),viewerPending=new Map(),viewerObserved=new Set();
let viewerToken=null,viewerScanning=false;
function viewerURL(value){return typeof value==='string'&&value.startsWith('viewer-asset:')?viewerPlaceholder+'#'+value:encodeURI(value)}
function loadViewerAsset(id){
 if(viewerURLs.has(id))return Promise.resolve(viewerURLs.get(id));
 if(viewerPending.has(id))return viewerPending.get(id).promise;
 let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});viewerPending.set(id,{promise,resolve,reject});
 parent.postMessage({type:'viewer-asset-request',token:viewerToken,id},'*');return promise;
}
function paintViewerAsset(node){const id=node.dataset.viewerAsset;if(!id||node.dataset.viewerLoading)return;node.dataset.viewerLoading='1';
 loadViewerAsset(id).then(url=>{if(!node.isConnected)return;node.setAttribute(node.tagName==='IMG'?'src':'href',url)}).catch(()=>{if(!node.isConnected)return;if(node.tagName==='IMG'){node.alt='本地封面无法读取';node.removeAttribute('src')}else{node.removeAttribute('href');node.title='本地文件无法读取，请重新选择采集数据目录。'}});
}
const viewerImages=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting)paintViewerAsset(entry.target)},{rootMargin:'200px'});
function scanViewerAssets(){
 viewerScanning=false;const live=new Set();
 for(const node of document.querySelectorAll('img,a')){
  const attribute=node.tagName==='IMG'?'src':'href',value=node.getAttribute(attribute)||'';
  if(value.startsWith(viewerPlaceholder+'#viewer-asset:'))node.dataset.viewerAsset=value.slice(viewerPlaceholder.length+1);
  const id=node.dataset.viewerAsset;if(!id)continue;live.add(id);
  if(node.tagName==='IMG'){if(!viewerObserved.has(node)){viewerObserved.add(node);viewerImages.observe(node)}}else paintViewerAsset(node);
 }
 for(const node of viewerObserved)if(!node.isConnected){viewerImages.unobserve(node);viewerObserved.delete(node)}
 for(const [id,url] of viewerURLs)if(!live.has(id)){URL.revokeObjectURL(url);viewerURLs.delete(id)}
}
function scheduleViewerAssets(){if(!viewerScanning){viewerScanning=true;requestAnimationFrame(scanViewerAssets)}}
function initViewerAssets(token){
 viewerToken=token;
 window.addEventListener('message',event=>{if(event.source!==parent||event.data?.type!=='viewer-asset'||event.data.token!==viewerToken)return;const {id,file,error}=event.data,pending=viewerPending.get(id);if(!pending)return;viewerPending.delete(id);if(error){pending.reject(Error(error));return}const url=URL.createObjectURL(file);viewerURLs.set(id,url);pending.resolve(url);scheduleViewerAssets()});
 new MutationObserver(scheduleViewerAssets).observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['src','href']});scanViewerAssets();
}
