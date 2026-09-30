/* Fidget scoreboard: top 3 players with pixel trophies.
   Scores live in Supabase once FIDGET_DB is filled in below; until then each
   visitor gets a local top 3 on their own device so the board still works. */
(function(){
  // ---- Supabase settings (public "anon" key is safe to ship: the table only allows read + insert) ----
  var FIDGET_DB = {
    url: '',   // e.g. https://abcdefgh.supabase.co
    key: ''    // Project Settings > API Keys > publishable key (or legacy anon key)
  };
  var TABLE = 'fidget_scores', TOP = 3, MAX_NAME = 10;
  var online = !!(FIDGET_DB.url && FIDGET_DB.key);

  var board = document.getElementById('hs-board');
  var list = document.getElementById('hs-list');
  var entry = document.getElementById('hs-entry');
  var input = document.getElementById('hs-name');
  var saveBtn = document.getElementById('hs-save');
  var skipBtn = document.getElementById('hs-skip');
  var note = document.getElementById('hs-note');
  if(!board || !list || !entry) return;

  var top = [], pending = null;

  // ---- pixel trophy (12x12 grid, crisp edges) ----
  var TROPHY = [
    '..HHHHHHHH..',
    'MMHCCCCCCCMM',
    'M.HCCCCCCC.M',
    'M.HCCCCCCC.M',
    '.MHCCCCCCCM.',
    '..HCCCCCCD..',
    '...CCCCCD...',
    '.....CD.....',
    '.....CD.....',
    '....BBBB....',
    '...BBBBBB...',
    '...BBBBBB...'
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
    list.innerHTML = '';
    for(var i=0;i<TOP;i++){
      var row = document.createElement('li'), p = top[i];
      row.className = 'hs-row hs-row--'+(i+1)+(p?'':' hs-row--empty');
      row.innerHTML = trophy(i+1)+'<span class="hs-rank">'+(i+1)+'</span><span class="hs-who"></span><span class="hs-pts"></span>';
      row.querySelector('.hs-who').textContent = p ? p.name : '---';
      row.querySelector('.hs-pts').textContent = p ? String(p.score) : '0';
      list.appendChild(row);
    }
  }

  // ---- storage ----
  function localLoad(){ try{ return JSON.parse(localStorage.getItem('fidget_top')||'[]'); }catch(e){ return []; } }
  function localSave(arr){ try{ localStorage.setItem('fidget_top', JSON.stringify(arr)); }catch(e){} }
  function sortTop(arr){ return arr.sort(function(a,b){ return b.score-a.score || (a.t||0)-(b.t||0); }).slice(0,TOP); }

  function headers(extra){
    var h = {'apikey':FIDGET_DB.key,'Content-Type':'application/json'};
    if(/^eyJ/.test(FIDGET_DB.key)) h['Authorization'] = 'Bearer '+FIDGET_DB.key;   // legacy anon JWT; new sb_publishable_ keys go in apikey only
    for(var k in extra) h[k]=extra[k];
    return h;
  }
  function load(){
    if(!online){ top = sortTop(localLoad()); render(); return Promise.resolve(); }
    return fetch(FIDGET_DB.url+'/rest/v1/'+TABLE+'?select=name,score&order=score.desc,created_at.asc&limit='+TOP,{headers:headers({})})
      .then(function(r){ if(!r.ok) throw new Error(r.status); return r.json(); })
      .then(function(rows){ top = rows; render(); })
      .catch(function(){ render(); });
  }
  function save(name, score){
    if(!online){ var a = localLoad(); a.push({name:name,score:score,t:Date.now()}); localSave(sortTop(a)); return load(); }
    return fetch(FIDGET_DB.url+'/rest/v1/'+TABLE,{method:'POST',headers:headers({'Prefer':'return=minimal'}),body:JSON.stringify({name:name,score:score})})
      .then(function(r){ if(!r.ok) throw new Error(r.status); })
      .then(load);
  }

  function qualifies(score){ return score>0 && (top.length<TOP || score>top[TOP-1].score); }

  function closeEntry(msg){
    pending = null; entry.hidden = true;
    note.textContent = msg||''; note.hidden = !msg;
    try{ document.getElementById('game').focus({preventScroll:true}); }catch(e){}
  }
  function submit(){
    if(pending==null) return;
    var name = clean(input.value);
    if(!name){ input.focus(); return; }
    try{ localStorage.setItem('fidget_name', name); }catch(e){}
    var s = pending; saveBtn.disabled = true; saveBtn.textContent = '...';
    save(name, s).then(function(){ closeEntry('SAVED!'); }, function(){ closeEntry('COULD NOT SAVE'); })
      .then(function(){ saveBtn.disabled = false; saveBtn.textContent = 'SAVE'; });
  }

  input.setAttribute('maxlength', MAX_NAME);
  input.addEventListener('input', function(){ var c = clean(input.value); if(c!==input.value.toUpperCase().trim()) input.value = c; });
  input.addEventListener('keydown', function(e){
    e.stopPropagation();                                  // typing never flaps/restarts the game
    if(e.key==='Enter'){ e.preventDefault(); submit(); }
    else if(e.key==='Escape'){ e.preventDefault(); closeEntry(''); }
  });
  saveBtn.addEventListener('click', submit);
  skipBtn.addEventListener('click', function(){ closeEntry(''); });
  ['mousedown','touchstart'].forEach(function(ev){ entry.addEventListener(ev, function(e){ e.stopPropagation(); }, {passive:true}); });

  // ---- hooks used by the game ----
  window.fidgetBoard = {
    busy: function(){ return pending!=null; },          // game ignores flaps while a name is being entered
    gameOver: function(score){
      note.hidden = true;
      if(!qualifies(score)) return;
      pending = score;
      try{ input.value = localStorage.getItem('fidget_name')||''; }catch(e){ input.value=''; }
      entry.hidden = false;
      setTimeout(function(){ try{ input.focus({preventScroll:true}); input.select(); }catch(e){} }, 60);
    }
  };

  render(); load();
})();
