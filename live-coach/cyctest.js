// A rotation keeps the motion magnitude flat but swings its CENTROID left-right.
// Count oscillations of the centroid instead of bursts of magnitude.
function count(cxs, band=0.10){
  let base=cxs[0], side=0, reps=0, last=-1e9, t=0;
  for(const cx of cxs){
    t+=120;
    base = base*0.97 + cx*0.03;
    const d = cx-base;
    if(side<=0 && d> band){ side=1;  if(t-last>500){last=t;reps++} }
    if(side>=0 && d<-band){ side=-1; }
  }
  return reps;
}
const rnd=(a,b)=>a+Math.random()*(b-a);
// 10 head circles, ~2s each: centroid traces a sine
const circles=[];for(let r=0;r<10;r++)for(let i=0;i<17;i++)
  circles.push(0.5+0.22*Math.sin(i/17*2*Math.PI)+rnd(-0.02,0.02));
// 10 tilts, out and back, with a pause: also a sine but with flat parts
const tilts=[];for(let r=0;r<10;r++){
  for(let i=0;i<9;i++)tilts.push(0.5+0.25*Math.sin(i/9*Math.PI)+rnd(-0.02,0.02));
  for(let i=0;i<8;i++)tilts.push(0.5+rnd(-0.02,0.02));}
// sitting still: centroid is noise only
const still=Array.from({length:200},()=>0.5+rnd(-0.04,0.04));
for(const [n,d,want] of [['10 head circles',circles,10],['10 tilts',tilts,10],
                         ['sitting still',still,0]]){
  const got=count(d);
  console.log(`  ${(got===want||Math.abs(got-want)<=1)?'PASS':'FAIL'}  ${n.padEnd(16)} counted ${got} (want ${want})`);
}
