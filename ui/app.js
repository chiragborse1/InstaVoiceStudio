'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = {ready:false, healthy:false, pending:false, voice:{connected:false,busy:false}, file:null, recording:false, playing:false, peaks:[], progress:0, confirmation:null, sessionImport:null, revision:0};
  let initialized = false, polling = false, timer;
  window.appReady = false;
  const clamp = (n, min, max) => Math.max(min, Math.min(max, Number(n) || 0));
  const time = n => `${Math.floor((Number(n)||0)/60)}:${String(Math.floor((Number(n)||0)%60)).padStart(2,'0')}`;
  const username = () => $('recipient').value.trim().replace(/^@/, '');
  const validUsername = () => /^[a-zA-Z0-9_](?:[a-zA-Z0-9._]{0,28}[a-zA-Z0-9_])?$/.test(username()) && !username().includes('..');
  const fileKey = f => f ? `${f.name}\n${f.duration}` : '';
  function notice(text, error=false) { $('status').textContent=text; $('status').classList.toggle('error',error); }
  async function call(name, ...args) {
    const api=window.pywebview?.api;
    if(typeof api?.[name] !== 'function') throw new Error(`Desktop control unavailable: ${name}. Open the updated InstaVoice Studio app.`);
    const result=await api[name](...args);
    if(result === false || result?.ok === false || result?.error) throw new Error(result?.error || result?.message || `${name} failed.`);
    return result;
  }
  function canSend() { return state.ready && state.healthy && !state.pending && !state.voice.busy && !state.recording && !state.playing && state.voice.connected && !!state.file && validUsername(); }
  function cancelConfirmation(focus=false) {
    state.confirmation=null; $('confirmation').hidden=true;
    if(focus) $('send').focus();
  }
  function cancelSessionImport(focus=false) {
    state.sessionImport=null; $('sessionImportConfirm').hidden=true;
    $('sessionImportInput').value='';
    if(focus) $('importSession').focus();
  }
  function render() {
    const locked=!state.ready || !state.healthy || state.pending || !!state.voice.busy;
    const reviewing=!!state.confirmation;
    const importing=!!state.sessionImport;
    const audioLocked=locked || state.recording || reviewing || importing;
    $('send').disabled=!canSend() || reviewing || importing;
    $('confirmSend').disabled=!canSend() || !reviewing;
    $('connectVoice').disabled=!state.ready || state.pending || state.voice.busy || state.voice.connected || reviewing || importing || state.recording;
    $('disconnectVoice').disabled=locked || !state.voice.connected || reviewing || importing || state.recording;
    $('importSession').disabled=!state.ready || state.pending || state.voice.busy || reviewing || importing || state.recording;
    $('open').disabled=audioLocked;
    $('recipient').disabled=state.pending || !!state.voice.busy || reviewing || importing;
    $('play').disabled=audioLocked || !state.file || !$('speaker').value || ($('routeEnabled').checked && !$('route').value);
    $('stop').disabled=!state.ready || state.pending || !state.playing;
    $('testSound').disabled=audioLocked || !$('speaker').value;
    $('startRecording').disabled=audioLocked || state.playing || !$('mic').value;
    $('stopRecording').disabled=!state.ready || state.pending || !state.recording;
    $('mic').disabled=audioLocked;
    for(const id of ['speaker','route','volume','speed']) $(id).disabled=audioLocked || state.playing;
    $('routeEnabled').disabled=audioLocked || state.playing || !$('route').value;
    $('refreshDevices').disabled=!state.ready || state.pending || state.voice.busy || state.recording || state.playing || reviewing || importing;
    $('openInstagram').disabled=!state.ready || state.pending || state.voice.busy;
    $('routeDetails').hidden=!$('routeEnabled').checked;
    $('recordingState').textContent=state.recording?'Recording…':'Mic off';
    $('playbackState').textContent=state.playing?'Playing preview…':'Preview only';
    $('sessionAccount').textContent=state.voice.connected ? `Connected${state.voice.username ? ' as @'+state.voice.username : ''}` : 'Not connected';
    $('recipient').setAttribute('aria-invalid',String(!!$('recipient').value && !validUsername()));
    $('confirmSessionImport').disabled=!state.sessionImport || !$('sessionImportInput').value.trim();
    $('sendHelp').textContent=state.pending || state.voice.busy ? 'Operation in progress. No automatic retries.' : state.recording ? 'Stop recording before reviewing a send.' : state.playing ? 'Stop the preview before reviewing a send.' : importing ? 'Importing session…' : !state.healthy ? 'Waiting for current desktop status.' : !state.voice.connected ? 'Connect your saved session to enable sending.' : !state.file ? 'Choose an audio file or record a clip.' : !validUsername() ? 'Enter a valid username (1–30 letters, numbers, underscores or periods).' : 'Review the recipient and file before confirming. Sends the original audio.';
    $('filename').textContent=state.file?.name || 'No audio selected';
    $('filemeta').textContent=state.file ? `${time(state.file.duration)}${state.file.sampleRate ? ' · '+(state.file.sampleRate/1000)+' kHz' : ''} · Original audio` : 'Choose an audio file or record a new clip below.';
    $('duration').textContent=time(state.file?.duration);
    $('elapsed').textContent=time((state.file?.duration||0)*state.progress);
    $('empty').hidden=!!state.peaks.length;
    draw();
  }
  function loadFile(file) {
    cancelConfirmation(); state.file=file; state.peaks=Array.isArray(file?.peaks)?file.peaks:[]; state.progress=0;
  }
  function applyStatus(s) {
    state.voice=s.voice || {connected:false,busy:false,status:'Sending backend unavailable. Update the desktop app.'};
    state.recording=!!s.recording; state.playing=!!s.playing; state.progress=clamp(s.progress,0,1);
    if(Object.prototype.hasOwnProperty.call(s,'file')) {
      if(fileKey(s.file)!==fileKey(state.file)) loadFile(s.file);
      else if(!s.file) state.file=null;
    }
    $('voiceStatus').textContent=state.voice.status || 'No session status reported.';
    $('voiceStatus').classList.toggle('error', /fail|error|invalid|expired|not found|unavailable|challenge|denied/i.test(state.voice.status||''));
    $('messageId').hidden=!state.voice.message_id;
    $('messageId').textContent=state.voice.message_id ? 'Message ID: '+state.voice.message_id : '';
    $('logs').textContent=Array.isArray(s.logs) ? s.logs.map(String).join('\n') || 'No activity yet.' : 'No activity reported.';
    $('browserState').textContent=s.browser?'Browser open':'Browser not open';
    const level=state.recording?clamp(s.micLevel,0,1):0;
    $('micLevel').value=level; $('micLevelValue').textContent=Math.round(level*100)+'%';
    state.healthy=true;
    if(state.confirmation && (!state.voice.connected || state.voice.busy || state.recording || fileKey(state.file)!==state.confirmation.key)) cancelConfirmation();
    render();
  }
  async function refreshStatus() {
    const revision=state.revision;
    try { const s=await call('status'); if(revision===state.revision) applyStatus(s); return true; }
    catch(e) { if(revision===state.revision) { state.healthy=false; cancelConfirmation(); notice(e.message||String(e),true); render(); } return false; }
  }
  // Read-only polling never retries an action. Stop on bridge failure.
  async function poll() {
    if(polling) return;
    polling=true;
    const ok=await refreshStatus(); polling=false;
    if(ok) timer=setTimeout(poll,300);
  }
  function resumePolling() { clearTimeout(timer); timer=setTimeout(poll,300); }
  async function action(work, message) {
    if(state.pending) return;
    state.pending=true; state.revision++; render();
    try { await work(); if(message) notice(message); }
    catch(e) { notice(e.message||String(e),true); }
    finally { await refreshStatus(); state.pending=false; render(); resumePolling(); }
  }
  function options(id, names, selected) {
    const list=Array.isArray(names)?names:[];
    const opts=list.map(name=>{const o=document.createElement('option');o.value=name;o.textContent=name;return o;});
    if(!opts.length) { const o=document.createElement('option');o.value='';o.textContent='No devices available';opts.push(o); }
    $(id).replaceChildren(...opts); if(list.includes(selected)) $(id).value=selected;
  }
  async function devices() {
    const data=await call('devices');
    options('speaker',data.outputs,data.default); options('route',data.virtual,$('route').value); options('mic',data.inputs,data.inputDefault);
    if(!$('route').value) $('routeEnabled').checked=false;
  }
  function draw() {
    const canvas=$('wave'),rect=canvas.getBoundingClientRect(); if(!rect.width)return;
    const dpr=window.devicePixelRatio||1; canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;
    const c=canvas.getContext('2d');if(!c)return;c.scale(dpr,dpr);
    const peaks=state.peaks,max=peaks.reduce((m,p)=>Math.max(m,Number(p)||0),.01),step=rect.width/(peaks.length||1);
    if(!peaks.length) {c.fillStyle='#e6e6eb';c.fillRect(0,rect.height/2,rect.width,1);return;}
    peaks.forEach((p,i)=>{const h=Math.max(2,clamp(p/max,0,1)*(rect.height-8));c.fillStyle=i/peaks.length<state.progress?'#242424':'#bfc2cc';c.fillRect(i*step,(rect.height-h)/2,Math.max(1,step-2),h);});
  }
  $('recipient').addEventListener('input',()=>{cancelConfirmation();render();});
  $('sessionImportInput').addEventListener('input',render);
  $('open').addEventListener('click',()=>{if($('open').disabled)return;return action(async()=>{const file=await call('choose_file');if(file) {loadFile(file);notice('Audio loaded. Preview or review your send.');}});});
  $('play').addEventListener('click',()=>{if($('play').disabled)return;return action(()=>call('play',$('speaker').value,$('routeEnabled').checked,$('route').value,clamp($('volume').value,0,1),clamp($('speed').value,.5,2)),'Preview requested.');});
  $('stop').addEventListener('click',()=>{if($('stop').disabled)return;return action(()=>call('stop'),'Playback stopped.');});
  $('testSound').addEventListener('click',()=>{if($('testSound').disabled)return;return action(()=>call('test_sound',$('speaker').value),'Test sound requested.');});
  $('refreshDevices').addEventListener('click',()=>{if($('refreshDevices').disabled)return;return action(devices,'Devices refreshed.');});
  $('startRecording').addEventListener('click',()=>{if($('startRecording').disabled)return;return action(async()=>{await call('start_recording',$('mic').value);state.recording=true;},'Recording started. Stop to create your clip.');});
  $('stopRecording').addEventListener('click',()=>{if($('stopRecording').disabled)return;return action(async()=>{const file=await call('stop_recording');state.recording=false;if(file)loadFile(file);},'Recording stopped. Check the selected clip before sending.');});
  $('connectVoice').addEventListener('click',()=>{if($('connectVoice').disabled)return;return action(()=>call('connect_voice'),'Session check requested. See session status above.');});
  $('disconnectVoice').addEventListener('click',()=>{if($('disconnectVoice').disabled)return;return action(()=>call('disconnect_voice'),'Disconnect requested.');});
  $('openInstagram').addEventListener('click',()=>{if($('openInstagram').disabled)return;return action(()=>call('open_instagram'),'Instagram inbox requested in your default browser.');});
  $('importSession').addEventListener('click',()=>{if($('importSession').disabled)return;state.sessionImport=true;$('sessionImportInput').value='';$('sessionImportConfirm').hidden=false;render();$('sessionImportInput').focus();});
  $('cancelSessionImport').addEventListener('click',()=>{cancelSessionImport(true);render();});
  $('confirmSessionImport').addEventListener('click',()=>{
    if(!state.sessionImport)return;
    const token=$('sessionImportInput').value.trim();
    if(!token)return;
    cancelSessionImport();
    return action(()=>call('import_session',token),'Session imported. Connect to validate.');
  });
  $('send').addEventListener('click',()=>{
    if(!canSend() || state.confirmation)return;
    state.confirmation={username:username(),key:fileKey(state.file)};
    $('confirmRecipient').textContent='@'+state.confirmation.username;
    $('confirmFile').textContent=state.file.name;
    $('confirmation').hidden=false;render();$('confirmSend').focus();
  });
  $('cancelSend').addEventListener('click',()=>{cancelConfirmation(true);render();});
  $('confirmSend').addEventListener('click',()=>{
    const confirmed=state.confirmation;
    if(!confirmed || !canSend() || confirmed.username!==username() || confirmed.key!==fileKey(state.file))return;
    // Consume this confirmation synchronously before awaiting the bridge.
    cancelConfirmation();
    return action(()=>call('send_voice',confirmed.username,true),'Send requested once. See the backend result above; no automatic retries.');
  });
  for(const id of ['speaker','route','routeEnabled']) $(id).addEventListener('change',render);
  for(const id of ['volume','speed']) $(id).addEventListener('input',()=>{
    $('volumeValue').textContent=Math.round(clamp($('volume').value,0,1)*100)+'%';
    $('speedValue').textContent=clamp($('speed').value,.5,2).toFixed(2)+'×';
  });
  async function init() {
    if(initialized)return;initialized=true;
    try { await devices();state.ready=true;window.appReady=true;notice('Audio controls ready. Connect the saved session only when you want to send.');await refreshStatus();render();resumePolling(); }
    catch(e) {notice(e.message||String(e),true);initialized=false;render();}
  }
  window.refreshStatus=refreshStatus;
  window.addEventListener('resize',draw);
  window.addEventListener('pywebviewready',init);
  if(window.pywebview?.api) init();
  render();
})();
