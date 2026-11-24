const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/arduino-sync.js'), 'utf8');
const tick = () => new Promise(r => setImmediate(r));

function bridge(reply = 'ACK,1\r\n', prescription = {}) {
  const nodes = {};
  for (const id of ['arduino-sync','arduino-connect','arduino-disconnect','arduino-plan','arduino-status','arduino-csrf','arduino-send']) {
    nodes[id] = {disabled:false,style:{},dataset:{},value:'73', addEventListener(type, handler) {this[type]=handler;}};
  }
  nodes['arduino-sync'].dataset = {uploadUrl:'/api/device/progress',prescriptionUrl:'/api/device/plans/0'};
  nodes['arduino-plan'].options = [{value:'73',dataset:{exercise:'Front Arm Raise'}}];
  const writes = [], requests = [], timers = new Map();
  let nextTimer = 0, deliver, closed = false, reloaded = false;
  const reader = {read:() => new Promise(r => {deliver=r;}), cancel:async () => deliver?.({done:true}),releaseLock(){}};
  const emit = async (line) => {deliver({value:new TextEncoder().encode(line),done:false});await tick();};
  const port = {open:async()=>{},close:async()=>{closed=true;},readable:{getReader:()=>reader},writable:{getWriter:()=>({
    write:async bytes => {writes.push(new TextDecoder().decode(bytes));if(reply) await emit(reply);}, releaseLock(){}
  })}};
  vm.runInNewContext(source, {
    document:{getElementById:id=>nodes[id]}, navigator:{serial:{requestPort:async()=>port}},TextEncoder,TextDecoder,Date,
    setTimeout(fn,ms){const id=++nextTimer;if(ms===5000) timers.set(id,fn);else queueMicrotask(fn);return id;},
    clearTimeout(id){timers.delete(id);},
    window:{location:{reload(){reloaded=true;}}},
    fetch:async(url,options)=>{requests.push({url,options});return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({ok:true,exercise_index:1,reps:20,seconds:120,exercise_name:'Front Arm Raise',...prescription})};}
  });
  return {nodes,writes,requests,emit,timers,closed:()=>closed,reloaded:()=>reloaded,
    connect:()=>nodes['arduino-connect'].click(),send:()=>nodes['arduino-send'].click(),
    disconnect:async()=>{await nodes['arduino-disconnect'].click();await tick();}};
}

test('send latest plan, map firmware index, write newline, and require ACK', async()=>{
  const b=bridge();await b.connect();assert.equal(b.nodes['arduino-send'].disabled,false);
  await b.send();assert.equal(b.requests[0].url,'/api/device/plans/73');
  assert.equal(b.requests[0].options.cache,'no-store');
  assert.deepEqual(b.writes,['SET,1,20,120\n']);
  assert.match(b.nodes['arduino-status'].textContent,/confirmed by Arduino/);
  await b.disconnect();assert.equal(b.closed(),true);assert.equal(b.nodes['arduino-send'].disabled,true);
});
test('BUSY is an error and explains reset',async()=>{
  const b=bridge('ERROR,BUSY\n');await b.connect();await b.send();
  assert.match(b.nodes['arduino-status'].textContent,/reset.*B4/);await b.disconnect();
});
test('invalid prescription never reaches serial',async()=>{
  const b=bridge(null,{seconds:0});await b.connect();await b.send();
  assert.equal(b.writes.length,0);assert.match(b.nodes['arduino-status'].textContent,/outside/);await b.disconnect();
});
test('fragmented ACK confirms only the matching exercise',async()=>{
  const b=bridge(null);await b.connect();const done=b.send();await tick();
  await b.emit('ACK,0\nACK,');assert.doesNotMatch(b.nodes['arduino-status'].textContent,/confirmed/);
  await b.emit('1\r\n');await done;assert.match(b.nodes['arduino-status'].textContent,/confirmed/);await b.disconnect();
});
test('timeout closes connection, never reports success',async()=>{
  const b=bridge(null);await b.connect();const done=b.send();await tick();
  for(const fn of b.timers.values()) fn();await done;await tick();
  assert.match(b.nodes['arduino-status'].textContent,/No acknowledgement/);assert.equal(b.closed(),true);
});
test('existing exercise upload includes plan and CSRF',async()=>{
  const b=bridge();await b.connect();
  await b.emit('EXERCISE,Front Arm Raise,TARGET_REPS,20,ACTUAL_REPS,18,TARGET_SECONDS,120,ACTUAL_SECONDS,110\n');
  const req=b.requests[0];assert.equal(req.url,'/api/device/progress');
  assert.equal(req.options.headers['X-CSRFToken'],'73');
  assert.deepEqual(JSON.parse(req.options.body),{exercise_name:'Front Arm Raise',actual_reps:18,actual_seconds:110,plan_id:73});
  assert.equal(b.reloaded(),true);
});
