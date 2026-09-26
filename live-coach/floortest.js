// Replay the floor-learning rule over a real set to confirm it no longer climbs.
function run(scores, guard){
  let noise=2.4, sm=2.4, st='quiet', above=0, hiN=0, last=0, reps=0, t=0;
  const floors=[];
  for(const raw of scores){
    t+=120; sm=sm*0.55+raw*0.45;
    if(st==='quiet' && (!guard || sm<noise*1.5)){
      noise=noise*(guard?0.98:0.97)+sm*(guard?0.02:0.03); noise=Math.max(noise,0.15);
    }
    const hi=noise*1.7, lo=noise*1.55;
    if(st==='quiet'){ if(sm>hi){above++; if(above>=2){st='active';hiN=above}} else above=0; }
    else { if(sm>hi)hiN++;
      if(sm<lo){ if(hiN>=3 && t-last>450){last=t;reps++;} st='quiet';above=0;hiN=0; } }
    floors.push(noise);
  }
  return {reps, first:floors[0], last:floors[floors.length-1]};
}
const rnd=(a,b)=>a+Math.random()*(b-a);
// ten neck rotations: ~1s of movement, ~1s rest, on a noisy 2.4 baseline
const set=[];for(let r=0;r<10;r++){
  for(let i=0;i<9;i++)set.push(rnd(6,11));
  for(let i=0;i<8;i++)set.push(rnd(1.8,3.0));}
for(const guard of [false,true]){
  const out=[];for(let i=0;i<30;i++)out.push(run(set.slice(),guard));
  const avg=a=>(a.reduce((x,y)=>x+y,0)/a.length).toFixed(2);
  console.log(`${guard?'WITH guard   ':'without guard'}  reps ${avg(out.map(o=>o.reps))}/10  `+
    `floor ${avg(out.map(o=>o.first))} -> ${avg(out.map(o=>o.last))}`);
}
