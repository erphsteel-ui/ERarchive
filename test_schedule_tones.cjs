const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');let js=fs.readFileSync(__dirname+'/static/schedule.js','utf8');let ctx=vm.createContext({});vm.runInContext(js.slice(js.indexOf('function scheduleTone('),js.indexOf('function scheduleVisibleDates(')),ctx);
for(const title of ['교섭 회의','운영위원회','현장 회의','노사협의회 회의'])assert.equal(vm.runInContext(`scheduleTone({title:${JSON.stringify(title)}})`,ctx),'meeting');
assert.equal(vm.runInContext("scheduleTone({title:'본교섭'})",ctx),'labor');console.log('PASS: meeting colors follow meeting type across rows');
