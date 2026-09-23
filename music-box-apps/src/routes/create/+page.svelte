<script lang="ts">
	import { goto } from '$app/navigation';
	import TopBar from '$lib/components/TopBar.svelte';
	import { onMount } from 'svelte';

	/**
	 * Making a song. The page holds the words, the style and the length; the
	 * box holds the cards. Every number here is either this box's own
	 * measurement or the catalogue's declared guess, and says which.
	 */
	type Model = {
		id: string;
		title: string;
		blurb: string;
		fields: string[];
		cards: number;
		limits: { max_duration?: number; min_duration?: number };
		rate: number;
		rate_source: string;
		seconds_per_word: number;
		traits: { max_minutes?: number; cards_note?: string };
	};

	let { data } = $props();
	const models = data.models as Model[];

	let model = $state<Model>(models[0]);
	let style = $state('');
	let lyrics = $state('');
	let duration = $state(150);
	let chosen = $state<string[]>([]);
	let title = $state('');
	let message = $state('');
	let bad = $state(false);
	let sending = $state(false);
	let jobs = $state<Record<string, unknown>[]>([]);
	let status = $state({ queued: 0, running: 0, cards: [] as { used: number; total: number }[] });

	const templates: [string, string][] = [
		['Write my own', ''],
		[
			'Anime opening (bass-forward)',
			'Global Metadata: Genre: anime opening (anison), J-rock, cinematic. BPM: 168. Key: D major. Emotional progression: tense verse, soaring pre-chorus, wide final chorus. Production: loud modern master, wide stereo image, deep low end, punchy transients. Vocal Details: powerful female lead, bright and high, close-mic\'d with air, stacked octave harmonies on the chorus. Arrangement: driving eighth-note electric bass with deep sub extension, weighty kick and snappy snare, fast distorted rhythm guitars double-tracked wide, piano intro, orchestral stabs in the chorus; bass and drums lead the groove, guitars fill the mids.'
		],
		[
			'Lo-fi study',
			'Global Metadata: Genre: lo-fi hip hop. BPM: 82. Key: F minor. Emotional progression: steady, unhurried. Production: warm and soft, vinyl noise, low end present but gentle, quiet master. Vocal Details: none — instrumental. Arrangement: dusty boom-bap drums with a soft kick, round upright-style bass, mellow Rhodes chords, brushed hats, tape hiss; bass and drums sit low in the mix, piano and vinyl crackle fill the space.'
		],
		[
			'Indie pop',
			'Global Metadata: Genre: indie pop. BPM: 112. Key: C major. Emotional progression: bright, hopeful, building into the last chorus. Production: clean and open, bright top end, tight low end, modern loud master. Vocal Details: warm female lead, close and clear, light harmonies on the chorus. Arrangement: jangly rhythm guitar, live drums with a punchy kick, melodic bass guitar, synth pad underneath; drums and bass carry the groove, guitars answer the vocal.'
		],
		[
			'Cinematic score',
			'Global Metadata: Genre: cinematic score. BPM: 90. Key: A minor. Emotional progression: tension, release, resolve. Production: wide and deep, long reverb, sub-bass weight, dynamic master. Vocal Details: none — instrumental. Arrangement: sustained strings, low brass, taiko and timpani with real low-end thump, sub-bass drone under the strings, piano figure; percussion and low strings lead, high strings add air.'
		]
	];

	const hints = ['+ BPM: 90', '+ Key: F major', '+ warm female vocal', '+ male rap', '+ acoustic guitar', '+ dusty drums', '+ vinyl crackle', '+ Rhodes piano', '+ big drums', '+ polished mix'];

	const has = (field: string) => model.fields.includes(field);

	/** what each model's own card says matters — shown, not buried in a README */
	const ADVICE: Record<string, string[]> = {
		minimax: [
			'Put each section tag on its own line — text on the same line as a tag is dropped.',
			'Name the vocal in the description (e.g. "soft female lead, breathy") or it may drift instrumental.',
			'Write it in three sections: Global Metadata (genre, BPM, key, progression, production), Vocal Details (gender, timbre, harmony), Arrangement (instruments, groove, bass, percussion, space).',
			'Describe the bass as a SOUND — "deep sub extension", "round upright-style bass" — not just as an instrument. A mix with no low-end instruction comes back mid-forward.',
			'Give a production profile: "loud modern master, wide stereo image" or "warm and quiet". Without it the master is whatever the model felt like.',
			'About three minutes is roughly 155 words at this box\'s measured 1.15 s per word.'
		],
		yue2: [
			'Start the style with the language — "English, indie pop, …" or "Mandarin, funk, …".',
			'About 30 seconds of lyrics per section; do not cram a whole song into one.',
			'[intro] is unstable: open on [verse] or [chorus].',
			'This box plans with cot=melody (melody only). The model default is full (melody and chords): faster here, less arrangement control.',
			'About three minutes is around 115 words at this box\'s measured 1.54 s per word.'
		],
		'ace-step': [
			'Caption up to 512 characters, lyrics up to 4096.',
			'State the language of the lyrics when it is not English.',
			'Turbo ignores the guidance scale by design; this box sets shift=3.0 as its docs require.'
		],
		'stable-audio': [
			'Instrumental only — there is no lyrics input for this family.',
			'Name genre, instruments, mood and BPM.',
			'Medium reaches 380 s; the small model stopped at 120 s.'
		],
		musicgen: [
			'Instrumental only — MusicGen has no singing.',
			'Duration is a token budget: 50 frames per second, so 120 s asks for 6,000 frames.',
			'Describe genre, instruments and mood; it follows text, not structure tags.'
		]
	};

	/**
	 * The knobs that are actually applied, per model. Anything the runner does
	 * not accept is not offered: MiniMax's script takes only prompt, lyrics,
	 * seconds and seed, so it has no sampling controls here (offering them
	 * would be a control that changes nothing).
	 */
	const KNOBS: Record<string, { key: string; label: string; min: number; max: number; step: number; help: string }[]> = {
		yue2: [
			{ key: 'guidance_scale', label: 'Text guidance', min: 0, max: 20, step: 0.1, help: 'semantic CFG; runs 1.0 by default' },
			{ key: 'num_inference_steps', label: 'Steps', min: 1, max: 32, step: 1, help: 'NAR midpoint ODE steps; 8 by default' }
		],
		'stable-audio': [
			{ key: 'num_inference_steps', label: 'Steps', min: 4, max: 32, step: 1, help: '8 is the default; more rarely helps on post-trained checkpoints' }
		],
		musicgen: [
			{ key: 'guidance_scale', label: 'Guidance', min: 1, max: 10, step: 0.5, help: 'classifier-free guidance; 3.0 is the default' },
			{ key: 'temperature', label: 'Temperature', min: 0.1, max: 2, step: 0.05, help: 'sampling temperature; 1.0 is the default' },
			{ key: 'top_k', label: 'Top-k', min: 0, max: 500, step: 10, help: '250 is the default; 0 disables it' }
		]
	};

	let advanced = $state(false);
	let cover_asset = $state('');
	let queue_open = $state(false);
	let knobs = $state<Record<string, string>>({});
	const words = $derived(lyrics.replace(/\[[^\]]*\]/g, ' ').split(/\s+/).filter(Boolean).length);
	const forecast = $derived(model.seconds_per_word ? Math.round(words * model.seconds_per_word) : 0);
	const work = $derived(Math.round((has('duration') ? duration : 150) * (model.rate || 1)));
	const needs = $derived(
		[
			has('style') && !style.trim() ? 'a style' : '',
			has('lyrics') && !lyrics.trim() ? 'words to sing' : ''
		].filter(Boolean)
	);

	const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

	/** a tag on or off; the ceiling is the box's, not the page's invention */
	function toggle_tag(tag: string) {
		if (chosen.includes(tag)) chosen = chosen.filter((t) => t !== tag);
		else if (chosen.length < data.max_tags) chosen = [...chosen, tag];
	}

	async function api(path: string, options: RequestInit = {}) {
		const r = await fetch(path, {
			...options,
			headers: { 'Content-Type': 'application/json', ...(options.headers as object) }
		});
		if (r.status === 401) {
			goto('/login?next=/create');
			throw new Error('signed out');
		}
		if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
		return r.json();
	}

	async function refresh() {
		try {
			const [list, state] = await Promise.all([api('/api/jobs?limit=8'), api('/api/status')]);
			jobs = list.items;
			status = state;
			bad = false;
		} catch (e) {
			message = (e as Error).message;
			bad = true;
		}
	}

	async function create() {
		if (needs.length) {
			message = `This model needs ${needs.join(' and ')}.`;
			bad = true;
			return;
		}
		sending = true;
		message = '';
		bad = false;
		try {
			const params: Record<string, unknown> = {};
			if (has('style')) params.style = style;
			if (has('lyrics')) params.lyrics = lyrics;
			if (has('duration')) params.duration = duration;
			if (chosen.length) params.tags = chosen;
			if (cover_asset) params.cover_asset = cover_asset;
			for (const [key, value] of Object.entries(knobs)) {
				if (value !== '') params[key] = key === 'num_inference_steps' ? Number(value) : value;
			}

			const r = await api('/api/jobs', {
				method: 'POST',
				body: JSON.stringify({ model: model.id, params, title: title.trim() })
			});
			message = r.queued > 1 ? `Queued — ${r.queued} jobs in line.` : 'Queued. It appears in the library when it is done.';
			refresh();
		} catch (e) {
			message = (e as Error).message;
			bad = true;
		} finally {
			sending = false;
		}
	}

	async function cancel(id: number) {
		try {
			await api(`/api/jobs/${id}`, { method: 'DELETE' });
			refresh();
		} catch (e) {
			message = (e as Error).message;
		}
	}

	onMount(() => {
		refresh();
		const timer = setInterval(refresh, 5000);
		return () => clearInterval(timer);
	});
</script>

<TopBar user={data.user} is_admin={data.user?.role === 'admin'}>
	{#snippet children()}
		<button
			class="flex items-center gap-2 rounded-full border border-line px-3 py-1.5 text-xs hover:bg-glasshover"
			onclick={() => (queue_open = true)}
		>
			<i class="ph ph-queue text-sm"></i>
			<span class="hidden sm:inline">Queue</span>
			{#if status.queued + status.running > 0}
				<span class="rounded-full bg-accent text-white px-1.5 text-[10px]">{status.queued + status.running}</span>
			{:else}
				<span class="text-muted text-[10px]">idle</span>
			{/if}
		</button>
	{/snippet}
</TopBar>

<main class="mx-auto max-w-6xl px-6 md:px-8 pt-5 pb-24">
	<header class="mb-5">
		<h1 class="text-3xl md:text-4xl font-extrabold tracking-tight">Make a song</h1>
		<p class="text-xs md:text-sm text-muted mt-1">
			One song at a time on the cards. Every number here is this box's own measurement.
		</p>
	</header>

	<!-- two columns on a wide screen: the sound on the left, the words on the
	     right, so the page is a screenful instead of a scroll -->
	<div class="grid gap-6 lg:grid-cols-2 lg:items-start">
		<div class="space-y-6">
			<section>
				<h2 class="text-sm font-bold text-muted mb-3">1 · Pick a model</h2>
				<p class="text-[11px] text-muted mb-3">
					<strong class="text-ink">longest here</strong> is the longest take this box has measured for
					that model — memory, the model's own cap, or simply what has been run. How long your song
					turns out is decided by the words, not by that number.
				</p>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
					{#each models as m (m.id)}
						<button
							class="text-left rounded-xl p-4 border transition {model.id === m.id ? 'border-accent bg-glasshover' : 'border-line hover:bg-glasshover'}"
							onclick={() => {
								model = m;
								if (m.limits?.max_duration) duration = Math.min(duration, m.limits.max_duration);
							}}
						>
							<div class="flex items-center justify-between mb-2">
								<i class="ph ph-{m.fields.includes('lyrics') ? 'music-notes' : 'piano-keys'} text-lg"></i>
								{#if model.id === m.id}<i class="ph-fill ph-check-circle text-accent"></i>{/if}
							</div>
							<div class="font-bold text-sm">{m.title}</div>
							<p class="text-xs text-muted mt-1">{m.blurb}</p>
							<div class="flex flex-wrap gap-1.5 mt-3 text-[10px]">
								<span class="rounded-full border border-line px-2 py-0.5">
									{m.fields.includes('lyrics') ? 'sings words' : 'instrumental'}
								</span>
								<span
									class="rounded-full border border-line px-2 py-0.5"
									title="The longest take this box has measured for {m.title} — set by memory, by the model's own cap, or by what has actually been run here."
								>
									{m.traits?.max_minutes ? `longest here ${m.traits.max_minutes} min` : 'no measured ceiling'}
								</span>
							</div>
						</button>
					{/each}
				</div>
			</section>

			{#if ADVICE[model.id]?.length}
				<section class="glass-panel rounded-xl p-4">
					<h3 class="text-xs font-bold text-muted mb-2">What {model.title} asks for</h3>
					<ul class="text-xs text-muted space-y-1 list-disc list-inside">
						{#each ADVICE[model.id] as line (line)}<li>{line}</li>{/each}
					</ul>
				</section>
			{/if}

			{#if has('style')}
				<section>
					<h2 class="text-sm font-bold text-muted mb-3">2 · How should it sound?</h2>
					<div class="flex flex-wrap items-center gap-3 mb-3">
						<label class="text-xs text-muted">Start from a template</label>
						<select
							class="bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
							onchange={(e) => (style = templates.find(([n]) => n === e.currentTarget.value)?.[1] ?? '')}
						>
							{#each templates as [name] (name)}<option>{name}</option>{/each}
						</select>
					</div>
					{#if model.id === 'ace-step' && style.length > 512}
						<p class="text-xs text-accent mb-2">ACE-Step takes at most 512 characters of caption ({style.length} now).</p>
					{/if}
					<textarea bind:value={style} rows="4"
						placeholder="Genre: lo-fi hip hop. BPM: 88. Mood: calm, rainy. Vocals: soft female. Arrangement: Rhodes, dusty drums, vinyl crackle."
						class="w-full bg-glasshover border border-line rounded-xl p-4 text-sm focus:outline-none focus:ring-2 focus:ring-accent"></textarea>
					<div class="flex flex-wrap gap-2 mt-3">
						{#each hints as hint (hint)}
							<button class="rounded-full border border-line px-3 py-1 text-xs hover:bg-glasshover"
								onclick={() => (style = (style.trim() ? style.trim() + ' ' : '') + hint.replace(/^\+\s*/, '') + '.')}>{hint}</button>
						{/each}
					</div>
				</section>
			{/if}

			{#if KNOBS[model.id]?.length}
				<section>
					<button class="text-xs font-bold text-muted hover:text-ink" onclick={() => (advanced = !advanced)}>
						<i class="ph ph-{advanced ? 'caret-down' : 'caret-right'}"></i> Advanced (sampling)
					</button>
					{#if advanced}
						<div class="glass-panel rounded-xl p-4 mt-3 grid gap-4 sm:grid-cols-2">
							{#each KNOBS[model.id] as knob (knob.key)}
								<label class="block">
									<span class="block text-xs font-bold text-muted mb-1">{knob.label}</span>
									<input
										type="number"
										min={knob.min}
										max={knob.max}
										step={knob.step}
										value={knobs[knob.key] ?? ''}
										placeholder="engine default"
										oninput={(e) => (knobs = { ...knobs, [knob.key]: e.currentTarget.value })}
										class="w-full bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
									/>
									<span class="block text-[11px] text-muted mt-1">{knob.help}</span>
								</label>
							{/each}
						</div>
					{/if}
				</section>
			{/if}
		</div>

		<div class="space-y-6">
			{#if has('lyrics')}
				<section>
					<h2 class="text-sm font-bold text-muted mb-3">3 · What should it sing?</h2>
					<p class="text-xs text-muted mb-3">
						Put each section tag on its own line. The song ends when the words do — this box measured
						{model.seconds_per_word ? `${model.seconds_per_word} s per word` : 'no rate yet'} for {model.title}.
					</p>
					<textarea bind:value={lyrics} rows="8" placeholder="[Verse]&#10;A line to sing&#10;&#10;[Chorus]&#10;Another line"
						class="w-full bg-glasshover border border-line rounded-xl p-4 text-sm focus:outline-none focus:ring-2 focus:ring-accent"></textarea>
					<p class="text-xs text-muted mt-2">
						{words} word{words === 1 ? '' : 's'}{forecast ? ` — likely about ${fmt(forecast)} of music` : ''}
					</p>
					{#if model.id === 'minimax' && /\[[^\]]+\][^\n\r]+/.test(lyrics)}
						<p class="text-xs text-accent mt-2">
							A section tag has text on the same line — MiniMax drops it. Put the tag on its own line.
						</p>
					{/if}
					{#if !has('duration') && forecast > 180}
						<p class="text-xs text-accent mt-2">
							That is about {fmt(forecast)} of singing — past the three-minute target. This model
							has no length setting; it stops when the words do, so trim them.
						</p>
					{/if}
				</section>
			{/if}

			{#if has('duration')}
				<section>
					<h2 class="text-sm font-bold text-muted mb-3">4 · How long a ceiling?</h2>
					<input type="range" min={model.limits?.min_duration ?? 30} max={model.limits?.max_duration ?? 300} bind:value={duration} class="w-full" />
					<p class="text-xs text-muted mt-1">{fmt(duration)} ceiling · the model may stop earlier, because it sings the words and stops</p>
				</section>
			{/if}

			<section>
				<h2 class="text-sm font-bold text-muted mb-1">Title</h2>
				<input bind:value={title} placeholder="Untitled"
					class="w-full bg-glasshover border border-line rounded-lg py-2 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
			</section>

			<section>
				<div class="flex items-baseline justify-between mb-2">
					<h2 class="text-sm font-bold text-muted">Tags</h2>
					<span class="text-[11px] text-muted">{chosen.length} of {data.max_tags}</span>
				</div>
				<p class="text-[11px] text-muted mb-3">
					How the song is filed — and what colour its sleeve takes. Pick from the box's own
					categories; there is no free text, so one shelf never becomes three.
				</p>
				<div class="space-y-3">
					{#each Object.entries(data.tag_groups) as [group, list] (group)}
						<div>
							<div class="text-[11px] text-muted mb-1.5">{group}</div>
							<div class="flex flex-wrap gap-1.5">
								{#each list as tag (tag)}
									{@const on = chosen.includes(tag)}
									<button
										class="rounded-full border px-2.5 py-1 text-xs transition {on ? 'border-accent bg-glasshover text-ink' : 'border-line text-muted hover:text-ink hover:bg-glasshover'}"
										aria-pressed={on}
										disabled={!on && chosen.length >= data.max_tags}
										onclick={() => toggle_tag(tag)}
									>{tag}</button>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			</section>

			<section>
				<h2 class="text-sm font-bold text-muted mb-3">5 · Cover background</h2>
				<p class="text-xs text-muted mb-3">
					Pick one, or leave it and the box chooses by the song's title.
				</p>
				<div class="grid grid-cols-4 sm:grid-cols-6 gap-2">
					<button
						class="aspect-square rounded-lg border text-[10px] grid place-items-center {cover_asset === '' ? 'border-accent bg-glasshover' : 'border-line hover:bg-glasshover'}"
						onclick={() => (cover_asset = '')}
					>Auto</button>
					{#each data.assets as asset (asset)}
						<button
							class="aspect-square rounded-lg overflow-hidden border {cover_asset === asset ? 'border-accent' : 'border-line'}"
							title={asset}
							onclick={() => (cover_asset = asset)}
						>
							<img src="/media/assets/{asset}" alt="" loading="lazy" class="w-full h-full object-cover" />
						</button>
					{/each}
				</div>
			</section>

			<div class="glass-panel rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3">
				<p class="text-sm {bad ? 'text-accent' : 'text-muted'}">
					{message || `Pick what you want, then press Create. ${model.title} · about ${Math.round(work / 60)} min of card time (${model.rate_source}).`}
				</p>
				<button class="px-6 py-2.5 rounded-full bg-accent text-white text-sm font-semibold disabled:opacity-50"
					disabled={sending || needs.length > 0} onclick={create}>{sending ? 'Sending…' : 'Create'}</button>
			</div>
		</div>
	</div>
</main>

{#if queue_open}
	<div
		class="fixed inset-0 z-[70] grid place-items-center px-6 bg-black/40 backdrop-blur-sm"
		role="dialog"
		aria-label="The queue"
		onclick={(e) => e.target === e.currentTarget && (queue_open = false)}
	>
		<div class="glass-panel rounded-2xl p-6 w-full max-w-lg max-h-[80vh] overflow-y-auto">
			<div class="flex items-center justify-between mb-4">
				<div>
					<h2 class="font-bold">The queue</h2>
					<p class="text-xs text-muted">
						{status.running ? (status.queued ? `working · ${status.queued} waiting` : 'working') : status.queued ? `${status.queued} waiting` : 'idle'}
					</p>
				</div>
				<button class="text-muted hover:text-ink text-xl" aria-label="Close" onclick={() => (queue_open = false)}>
					<i class="ph ph-x"></i>
				</button>
			</div>
			{#each jobs as job (job.id)}
				<div class="rounded-xl border border-line p-3 mb-2">
					<div class="flex items-center gap-2">
						<span class="w-2 h-2 rounded-full shrink-0"
							style="background:{job.status === 'running' ? 'var(--accent)' : job.status === 'queued' ? '#d6b24a' : job.status === 'failed' ? '#ff6b6b' : '#4ade80'}"></span>
						<span class="truncate text-sm">{(job.title as string) || 'Untitled'}</span>
					</div>
					<div class="text-[11px] text-muted mt-1">
						{job.model} · {job.status === 'queued' && job.position
							? job.position === 1 ? 'next in line' : `${job.position} in line`
							: job.status}
						{job.wall_s ? ` · took ${Math.round(job.wall_s as number)} s` : ''}
					</div>
					{#if job.error}<div class="text-[11px] text-accent mt-1">{job.error}</div>{/if}
					{#if job.song_id}<div class="text-[11px] text-accent mt-1">it is in the library now</div>{/if}
					{#if job.status === 'queued'}
						<button class="text-[11px] text-muted underline mt-1" onclick={() => cancel(job.id as number)}>
							Take it out of the queue
						</button>
					{/if}
				</div>
			{:else}
				<p class="text-sm text-muted">Nothing in the queue. Songs you make appear here, then in the library.</p>
			{/each}
		</div>
	</div>
{/if}
