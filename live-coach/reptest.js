function run(scores,SENS,MINHI){
  let noise=0.5,sm=0.5,st='quiet',above=0,hiN=0,peak=0,lastRepAt=0,reps=0,t=0;
  for(const raw of scores){
    t+=120;
    sm=sm*0.55+raw*0.45;
    if(st==='quiet'){noise=noise*0.97+sm*0.03;noise=Math.max(noise,0.15)}
    const hi=noise*SENS, lo=noise*1.55;
    if(st==='quiet'){
      if(sm>hi){above++;peak=Math.max(peak,sm);if(above>=2){st='active';hiN=above}}
      else{above=0;peak=0}
    }else{
      if(sm>hi)hiN++;                 // time spent genuinely moving, not the decay tail
      peak=Math.max(peak,sm);
      if(sm<lo){
        const real = hiN>=MINHI && t-lastRepAt>450;
        st='quiet';above=0;
        if(real){lastRepAt=t;reps++}
        peak=0;hiN=0;
      }
    }
  }
  return reps;
}
const rnd=(a,b)=>a+Math.random()*(b-a);
const mk={
  still:()=>Array.from({length:250},()=>rnd(0.2,0.9)),
  expo:()=>Array.from({length:250},(_,i)=>rnd(0.2,0.9)+(i%40<3?rnd(0,0.7):0)),
  fidget:()=>Array.from({length:250},(_,i)=>rnd(0.2,0.9)+(i%60<2?rnd(0,1.6):0)),
  headturn:()=>Array.from({length:250},(_,i)=>rnd(0.2,0.9)+(i%80<3?rnd(0,3.5):0)),
  walkby:()=>Array.from({length:250},(_,i)=>rnd(0.2,0.9)+(i>100&&i<108?rnd(4,9):0)),
  squats:()=>{const a=[];for(let r=0;r<10;r++){for(let i=0;i<8;i++)a.push(rnd(6,16));
    for(let i=0;i<9;i++)a.push(rnd(0.2,0.9))}return a},
  rolls:()=>{const a=[];for(let r=0;r<10;r++){for(let i=0;i<10;i++)a.push(rnd(2.2,4.5));
    for(let i=0;i<8;i++)a.push(rnd(0.2,0.9))}return a},
  tiny:()=>{const a=[];for(let r=0;r<10;r++){for(let i=0;i<12;i++)a.push(rnd(1.4,2.4));
    for(let i=0;i<8;i++)a.push(rnd(0.2,0.9))}return a},
  fast:()=>{const a=[];for(let r=0;r<10;r++){for(let i=0;i<6;i++)a.push(rnd(5,12));
    for(let i=0;i<6;i++)a.push(rnd(0.2,0.9))}return a},
};
const want={still:0,expo:0,fidget:0,headturn:0,walkby:0,squats:10,rolls:10,tiny:10,fast:10};
let best=null;
for(const SENS of [1.5,1.6,1.7,1.8,1.9,2.0]) for(const M of [4,5,6]){
  let ok=true,line='';
  for(const k of Object.keys(mk)){
    const got=[];for(let i=0;i<40;i++)got.push(run(mk[k](),SENS,M));
    const avg=got.reduce((a,b)=>a+b,0)/got.length;
    const good = want[k]===0 ? Math.max(...got)===0 : Math.abs(avg-want[k])<=1.0;
    if(!good)ok=false;
    line+=`${k}:${avg.toFixed(1)}${good?'':'!'} `;
  }
  if(ok&&!best)best=[SENS,M];
  console.log((ok?'PASS  ':'fail  ')+`SENS ${SENS} minHi ${M}  `+line);
}
console.log(best?`\n--> use SENS=${best[0]} MINHI=${best[1]}`:'\nno configuration passes');
