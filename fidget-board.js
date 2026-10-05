/* Fidget scoreboard: players give their name once, scores save automatically,
   and the top 3 (one place per player) shows on the game-over screen with pixel trophies.
   Scores live in Supabase; if it can't be reached, a local top 3 on this device is used. */
(function(){
  // ---- Supabase settings (public publishable key is safe to ship: the table only allows read + insert) ----
  var FIDGET_DB = {
    url: 'https://txohigzxsieqwgycektl.supabase.co',
    key: 'sb_publishable_P4PAITc5FyR7ulPbnqJ2uA_4ju0fiDz'
  };
  var TABLE = 'fidget_scores', TOP = 3, MAX_NAME = 10;
  var online = !!(FIDGET_DB.url && FIDGET_DB.key);

  var $ = function(id){ return document.getElementById(id); };
  var list = $('hs-list'), title = $('hs-title');
  var ovStart = $('ov-start'), ovName = $('ov-name');
  var input = $('hs-name'), goBtn = $('hs-go');
  var who = $('hs-who'), whoName = $('hs-who-name'), changeBtn = $('hs-change');
  if(!list || !ovName || !input) return;

  var top = [], naming = false;
  function getName(){ try{ return localStorage.getItem('fidget_name')||''; }catch(e){ return ''; } }
  function setName(n){ try{ localStorage.setItem('fidget_name', n); }catch(e){} }
  function myBest(){ try{ return parseInt(localStorage.getItem('fidget_sent')||'0',10)||0; }catch(e){ return 0; } }
  function setMyBest(n){ try{ localStorage.setItem('fidget_sent', String(n)); }catch(e){} }

  // ---- pixel trophy (12x12 grid, crisp edges) ----
  var TROPHY = [
    '..HHHHHHHH..','MMHCCCCCCCMM','M.HCCCCCCC.M','M.HCCCCCCC.M','.MHCCCCCCCM.','..HCCCCCCD..',
    '...CCCCCD...','.....CD.....','.....CD.....','....BBBB....','...BBBBBB...','...BBBBBB...'
  ];
  var TONES = {
    1: {C:'#FFD23F', D:'#D9A400', H:'#FFF3B0', M:'#E8B800', B:'#8A5A12'},
    2: {C:'#D7DEE6', D:'#9AA7B4', H:'#FFFFFF', M:'#B4BFCA', B:'#5E6B78'},
    3: {C:'#E59A5B', D:'#B0642C', H:'#FFD1A6', M:'#C97A3D', B:'#6E3D17'}
  };
  function trophy(rank){
    var t = TONES[rank], r = '';
    for(var y=0;y<12;y++) for(var x=0;x<12;x++){
      var k = TROPHY[y][x]; if(k==='.') continue;
      r += '<rect x="'+x+'" y="'+y+'" width="1" height="1" fill="'+t[k]+'"/>';
    }
    return '<svg class="hs-trophy" viewBox="0 0 12 12" shape-rendering="crispEdges" aria-hidden="true">'+r+'</svg>';
  }

  function clean(n){ return String(n||'').toUpperCase().replace(/[^A-Z0-9 ._-]/g,'').replace(/\s+/g,' ').trim().slice(0,MAX_NAME); }

  function render(){
    var me = getName();
    list.innerHTML = '';
    for(var i=0;i<TOP;i++){
      var row = document.createElement('li'), p = top[i];
      row.className = 'hs-row hs-row--'+(i+1)+(p?'':' hs-row--empty')+(p && me && p.name===me ? ' hs-row--me':'');
      row.innerHTML = trophy(i+1)+'<span class="hs-rank">'+(i+1)+'</span><span class="hs-who"></span><span class="hs-pts"></span>';
      row.querySelector('.hs-who').textContent = p ? p.name : '---';
      row.querySelector('.hs-pts').textContent = p ? String(p.score) : '0';
      list.appendChild(row);
    }
  }

  // names kept off the board
  var HIDDEN = {'ISH HATER':1};

  // one place per player: keep each name's best score only
  function uniqueTop(rows){
    var seen = {}, out = [];
    rows = rows.slice().sort(function(a,b){ return b.score-a.score || (a.t||0)-(b.t||0); });
    for(var i=0;i<rows.length && out.length<TOP;i++){ if(seen[rows[i].name] || HIDDEN[rows[i].name]) continue; seen[rows[i].name]=1; out.push(rows[i]); }
    return out;
  }

  // ---- storage ----
  function localLoad(){ try{ return JSON.parse(localStorage.getItem('fidget_top')||'[]'); }catch(e){ return []; } }
  function localAdd(name, score){ var a = localLoad(); a.push({name:name,score:score,t:Date.now()}); try{ localStorage.setItem('fidget_top', JSON.stringify(uniqueTop(a))); }catch(e){} }
  function headers(extra){
    var h = {'apikey':FIDGET_DB.key,'Content-Type':'application/json'};
    if(/^eyJ/.test(FIDGET_DB.key)) h['Authorization'] = 'Bearer '+FIDGET_DB.key;   // legacy anon JWT; sb_publishable_ keys go in apikey only
    for(var k in extra) h[k]=extra[k];
    return h;
  }
  function load(){
    if(!online){ top = uniqueTop(localLoad()); render(); return Promise.resolve(); }
    return fetch(FIDGET_DB.url+'/rest/v1/'+TABLE+'?select=name,score,created_at&order=score.desc,created_at.asc&limit=30',{headers:headers({})})
      .then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); })
      .then(function(rows){ rows.forEach(function(r){ r.t = Date.parse(r.created_at)||0; }); top = uniqueTop(rows); render(); })
      .catch(function(){ top = uniqueTop(localLoad()); render(); });
  }
  function save(name, score){
    localAdd(name, score);
    if(!online) return load();
    return fetch(FIDGET_DB.url+'/rest/v1/'+TABLE,{method:'POST',headers:headers({'Prefer':'return=minimal'}),body:JSON.stringify({name:name,score:score})})
      .then(function(r){ if(!r.ok) throw new Error(r.status); }).then(load, load);
  }
  function qualifies(score){
    if(score<=0) return false;
    var me = getName(), mine = null;
    for(var i=0;i<top.length;i++) if(top[i].name===me) mine = top[i];
    if(mine) return score > mine.score;                       // already on the board: only a better score moves you
    return top.length<TOP || score>top[TOP-1].score;
  }

  // ---- name prompt (asked once, before the first game) ----
  function updateWho(){ var n = getName(); whoName.textContent = n; who.hidden = !n; }
  function askName(){
    naming = true; ovStart.hidden = true; ovName.hidden = false;
    input.value = getName();
    setTimeout(function(){ try{ input.focus({preventScroll:true}); input.select(); }catch(e){} }, 60);
  }
  var confirmed = false;                                      // name is confirmed once per visit (prefilled from last time)
  try{ confirmed = sessionStorage.getItem('fidget_ok')==='1'; }catch(e){}
  function closeName(){ naming = false; ovName.hidden = true; ovStart.hidden = false; try{ $('game').focus({preventScroll:true}); }catch(e){} }
  function confirmName(){
    var n = clean(input.value);
    if(!n){ input.focus(); return; }
    if(n!==getName()) setMyBest(0);
    setName(n); updateWho(); render();
    confirmed = true; try{ sessionStorage.setItem('fidget_ok','1'); }catch(e){}
    naming = false; ovName.hidden = true;
    try{ $('game').focus({preventScroll:true}); }catch(e){}
    if(window.fidgetStart) window.fidgetStart();              // PLAY goes straight into the game
  }
  input.addEventListener('input', function(){ var c = clean(input.value); if(c!==input.value.toUpperCase().trim()) input.value = c; });
  input.addEventListener('keydown', function(e){
    e.stopPropagation();                                      // typing never flaps the bird
    if(e.key==='Enter'){ e.preventDefault(); confirmName(); }
    else if(e.key==='Escape' && getName()){ e.preventDefault(); closeName(); }
  });
  goBtn.addEventListener('click', confirmName);
  changeBtn.addEventListener('click', function(e){ e.stopPropagation(); askName(); });
  goBtn.addEventListener('mousedown', function(e){ e.stopPropagation(); });
  ['mousedown','touchstart'].forEach(function(ev){
    ovName.addEventListener(ev, function(e){ e.stopPropagation(); }, {passive:true});
    changeBtn.addEventListener(ev, function(e){ e.stopPropagation(); }, {passive:true});
  });

  // ---- hooks used by the game ----
  window.fidgetBoard = {
    ready: function(){ return confirmed && !!getName(); },
    busy: function(){ return naming; },
    askName: askName,
    gameOver: function(score){
      title.textContent = 'TOP 3';
      if(qualifies(score) && score > myBest()){
        setMyBest(score);
        title.textContent = 'NEW TOP 3!';
        var me = getName(), rows = top.filter(function(r){ return r.name!==me; });   // show it straight away,
        rows.push({name:me, score:score, t:Date.now()}); top = uniqueTop(rows); render();
        save(me, score);                                                              // then confirm with the server
      } else { render(); load(); }
    }
  };

  updateWho(); render(); load();
})();
