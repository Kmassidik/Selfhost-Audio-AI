// Browser checks: the things a unit test cannot see — that a card plays, that
// the page does not scroll sideways on a phone, that the picker names every
// model in the catalogue.
//
// Needs a Chrome listening on the debugging port, with autoplay allowed: a
// click made from script is not a user gesture, and without the flag every
// playback check fails for a reason that has nothing to do with the site.
//
//   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
//       --headless=new --remote-debugging-port=9446 \
//       --autoplay-policy=no-user-gesture-required --user-data-dir=/tmp/chrome-ui &
//   BASE=http://10.0.0.20:8095 OWNER_PASSWORD= node browser-checks.mjs
//
// OWNER_PASSWORD= (empty) matches a box that allows creating from the local
// network only. It enqueues one real job to prove the queue answers, and takes
// it out again unless the worker has already claimed it.
const port = Number(process.env.PORT || 9446), base = process.env.BASE || "http://127.0.0.1:8099";
// An empty OWNER_PASSWORD is a real setting — it means "local network only" —
// so it must survive, where `||` would quietly turn it back into a password.
const pass = process.env.OWNER_PASSWORD ?? "demo";
const open = async url => {
  const t = await (await fetch(`http://127.0.0.1:${port}/json/new?${url}`, {method:"PUT"})).json();
  const ws = new WebSocket(t.webSocketDebuggerUrl); let id = 0; const pend = new Map(); const errs = [];
  ws.onmessage = e => { const m = JSON.parse(e.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
    if (m.method === "Runtime.exceptionThrown") errs.push(m.params.exceptionDetails.exception?.description?.split("\n")[0]); };
  await new Promise(r => ws.onopen = r);
  const cmd = (method, params={}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({id:i, method, params})); });
  await cmd("Runtime.enable");
  const ev = async expr => (await cmd("Runtime.evaluate", {expression: expr, awaitPromise: true, returnByValue: true})).result.result.value;
  return {ev, errs, close: () => ws.close(), cmd};
};
const wait = ms => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (name, ok, extra = "") => { results.push(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? " — " + extra : ""}`); };

// ── listener page ────────────────────────────────────────────
{
  const p = await open(base + "/");
  await wait(2500);
  const total = await p.ev(`(async()=>(await (await fetch("/api/library?limit=1")).json()).total)()`);
  const cards = await p.ev(`document.querySelectorAll("#grid .card, #rows .card").length`);
  check("library renders every song it has", cards >= Math.min(total, 12) && cards > 0,
        `${cards} cards of ${total} songs`);
  const feature = await p.ev(`document.querySelector("#rows [data-play]") ? 1 : 0`);
  check("the newest song is featured", feature === 1);

  // play the first card, then force a library refresh and confirm the element survives
  await p.ev(`(()=>{const a=document.querySelector("#grid .card");window.__id=a.dataset.id;a.click();
                    const au=document.getElementById("audio");au.muted=true;window.__el=au;return 1})()`);
  await wait(1200);
  const playing = await p.ev(`(()=>{const a=document.getElementById("audio");return !a.paused && a.currentSrc.includes("/media/mp3/")})()`);
  check("clicking a card plays it", playing);
  await p.ev(`loadPage(true)`); await wait(1200);
  const survived = await p.ev(`(()=>{const a=document.getElementById("audio");
      return a===window.__el && !a.paused && a.currentTime>0})()`);
  check("playback survives a library refresh", survived);

  // a song that has words: instrumentals legitimately have none
  const withLyrics = await p.ev(`(async()=>{const r=await fetch("/api/library?q=umbrella&limit=1");
      return (await r.json()).items[0].id})()`);
  await p.ev(`playSong("${withLyrics}")`);
  await wait(1500);
  const npLyrics = await p.ev(`document.querySelector("#np pre") ? document.querySelector("#np pre").textContent.length : 0`);
  check("now playing shows lyrics", npLyrics > 0, `${npLyrics} chars`);

  await p.ev(`(()=>{const q=document.getElementById("q");q.value="umbrella";q.dispatchEvent(new Event("input"));return 1})()`);
  await wait(900);
  const found = await p.ev(`document.querySelectorAll("#grid .card").length`);
  const titles = await p.ev(`[...document.querySelectorAll("#grid .card")].map(c=>c.textContent.trim().slice(0,20)).join("|")`);
  check("search narrows the grid", found > 0 && found < cards && titles.toLowerCase().includes("umbrella"), `${found} results`);

  // like round-trip
  await p.ev(`(async()=>{const id=window.__id;await fetch("/api/like/"+id,{method:"POST"});return 1})()`);
  const liked = await p.ev(`(async()=>{const r=await fetch("/api/library?liked=true");return (await r.json()).total})()`);
  check("liking a song works", liked >= 1, `${liked} liked`);

  // the listener side is about songs, not machinery
  const leaked = await p.ev(`document.body.innerText.match(/MiniMax|YuE2|ACE-Step|Stable Audio/g)?.join(",") || ""`);
  check("no model names on the listener page", leaked === "", leaked);

  check("no page errors", p.errs.length === 0, p.errs.join(" / "));
  p.close();
}

// ── phone width ──────────────────────────────────────────────
{
  const p = await open(base + "/");
  await p.cmd("Emulation.setDeviceMetricsOverride", {width: 390, height: 844, deviceScaleFactor: 2, mobile: true});
  await wait(2000);
  const overflow = await p.ev(`document.documentElement.scrollWidth - document.documentElement.clientWidth`);
  check("no sideways scrolling at 390px", overflow <= 0, `overflow ${overflow}px`);
  const playerVisible = await p.ev(`!!document.querySelector("#pbPlay").getBoundingClientRect().width`);
  check("player bar visible on phone", playerVisible);
  p.close();
}

// ── creator page ─────────────────────────────────────────────
{
  const p = await open(base + "/create");
  await wait(2000);
  const offered = await p.ev(`(async()=>(await (await fetch("/api/models")).json()).items.length)()`);
  const kinds = await p.ev(`document.querySelectorAll("#kinds [data-kind]").length`);
  check("every model in the catalogue can be chosen", kinds === offered && kinds > 0,
        `${kinds} of ${offered}`);
  const first = await p.ev(`(document.querySelector('#kinds [aria-pressed="true"]')||{}).innerText || ""`);
  check("one model is chosen to begin with", first.trim().length > 0, first.split("\n")[0]);
  // the choice is only a choice if the trade-off is on the card
  const traits = await p.ev(`[...document.querySelectorAll("#kinds [data-kind]")].every(b =>
      /sings words|instrumental/.test(b.innerText) && /card/.test(b.innerText)) ? 1 : 0`);
  check("each card says whether it sings and what it costs", traits === 1);
  const named = await p.ev(`(async()=>{const items=(await (await fetch("/api/models")).json()).items;
      const text=document.querySelector("#kinds").innerText;
      return items.filter(m=>!text.includes(m.title)).map(m=>m.title).join(",")})()`);
  check("models are named, so a person can pick one", named === "", "missing " + named);
  const est = await p.ev(`document.querySelector("#estimate").textContent`);
  check("an honest time estimate is shown", /takes/.test(est), est);
  // With no password set, the box allows creation from the local network only,
  // and the check machine is on it — there is nothing to refuse.
  if (pass) {
    const refused = await p.ev(`(async()=>{const r=await fetch("/api/jobs",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({model:"yue2",params:{lyrics:"x"}})});return r.status})()`);
    check("creating without the password is refused", refused === 401, "status " + refused);
  }
  const posted = await p.ev(`(async()=>{const r=await fetch("/api/jobs",{method:"POST",
      headers:{"Content-Type":"application/json"${pass ? ',"Authorization":"Bearer ' + pass + '"' : ""}},
      body:JSON.stringify({model:"yue2",params:{lyrics:"x",style:"test"},title:"browser check"}) });
      return {status:r.status, body: await r.json()}})()`);
  check("a request joins the queue and is given a place",
        posted.status === 200 && (posted.body.queued + posted.body.running) >= 1,
        `status ${posted.status}, ${posted.body?.queued} waiting`);
  // The check must leave nothing behind: the queued job if it is still queued,
  // and the song if the worker was quick enough to make one.
  await p.ev(`(async()=>{await fetch("/api/jobs/${posted.body.id}",{method:"DELETE"${pass ? ',headers:{"Authorization":"Bearer ' + pass + '"}' : ""}});
      const jobs = (await (await fetch("/api/jobs?limit=20"${pass ? ',{headers:{"Authorization":"Bearer ' + pass + '"}}' : ""})).json()).items;
      for (const j of jobs.filter(j => j.title === "browser check" && j.song_id))
        await fetch("/api/song/" + j.song_id, {method:"DELETE"${pass ? ',headers:{"Authorization":"Bearer ' + pass + '"}' : ""}});
      return 1})()`);
  check("no creator page errors", p.errs.length === 0, p.errs.join(" / "));
  p.close();
}

console.log(results.join("\n"));
process.exit(results.some(r => r.startsWith("FAIL")) ? 1 : 0);
