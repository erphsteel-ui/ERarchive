const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(__dirname+'/static/theme-toggle.js','utf8');
function setup(initial,blocked=false){
 const events={},button={setAttribute(k,v){this[k]=v},addEventListener(k,fn){events[k]=fn}},root={dataset:{}},published=[];
 let saved=initial;const context={document:{documentElement:root,addEventListener(k,fn){events[k]=fn},getElementById(){return button}},window:{dispatchEvent(event){published.push(event.detail.theme)}},localStorage:{getItem(){if(blocked)throw Error('blocked');return saved},setItem(k,value){if(blocked)throw Error('blocked');saved=value}},CustomEvent:class{constructor(name,options){this.detail=options.detail}}};
 vm.runInNewContext(code,context);events.DOMContentLoaded();return {root,button,events,published,get saved(){return saved}};
}
let dark=setup(null);assert.equal(dark.root.dataset.theme,'dark');assert.equal(dark.button.textContent,'☀️ 라이트 모드');dark.events.click();assert.equal(dark.root.dataset.theme,'light');assert.equal(dark.saved,'light');assert.equal(dark.button.textContent,'🌙 다크 모드');assert.deepEqual(dark.published,['light']);
let light=setup('light');assert.equal(light.root.dataset.theme,'light');light.events.click();assert.equal(light.saved,'dark');
let blocked=setup('light',true);assert.equal(blocked.root.dataset.theme,'dark');blocked.events.click();assert.equal(blocked.root.dataset.theme,'light');
assert.equal(setup('invalid').root.dataset.theme,'dark');console.log('PASS: theme defaults, persistence, accessibility state and blocked storage fallback');
