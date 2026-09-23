<script lang="ts">
	import { page } from '$app/state';
	import { player, type SongRow } from '$lib/domain/player.svelte.js';

	/**
	 * The details drawer: what the song is, who made it, with what, and the
	 * words. It asks the API for the full row when it opens, because the
	 * library list does not carry lyrics or the file's own facts.
	 */
	let full = $state<SongRow | null>(null);

	$effect(() => {
		const song = player.current;
		if (!player.drawer || !song) {
			full = null;
			return;
		}
		full = song;
		let cancelled = false;
		fetch(`/api/song/${song.id}`)
			.then((r) => (r.ok ? r.json() : song))
			.then((d: SongRow) => {
				if (!cancelled) full = d;
			})
			.catch(() => undefined);
		return () => {
			cancelled = true;
		};
	});

	const model_name = $derived(
		full ? ((page.data as { model_names?: Record<string, string> }).model_names?.[full.model] ?? full.model) : ''
	);
	const maker = $derived(full?.creator_id && full.creator_id !== 'migrated' ? full.creator_id : 'unknown');
	const rate = $derived(
		full ? `${(full.sample_rate / 1000).toFixed(1)} kHz · ${full.channels === 2 ? 'stereo' : 'mono'}` : ''
	);

</script>

<aside
	class="fixed right-0 top-0 bottom-[90px] z-[60] w-[24rem] max-w-[92vw] glass-panel border-y-0 border-r-0 p-5 overflow-y-auto no-scrollbar transition-transform duration-200
	       {player.drawer ? 'translate-x-0' : 'translate-x-full'}"
	aria-hidden={!player.drawer}
>
	<div class="flex items-center justify-between mb-4">
		<span class="text-xs font-bold uppercase tracking-wide text-muted">Now playing</span>
		<button class="text-muted hover:text-ink text-xl" aria-label="Close details" onclick={() => player.close_drawer()}>
			<i class="ph ph-x"></i>
		</button>
	</div>

	{#if full}
		<img
			src="/media/covers/{full.id}.png?v={full.cover_v}"
			alt=""
			class="w-full aspect-square rounded-xl object-cover mb-4 bg-glasshover"
		/>
		<h3 class="text-lg font-bold mb-1">{full.title}</h3>
		<p class="text-xs text-muted mb-4">
			made by <span class="text-ink font-medium">{maker}</span> with
			<span class="text-ink font-medium">{model_name}</span>
		</p>

		<div class="flex flex-wrap items-center gap-2 text-xs text-muted mb-4">
			<span class="tabular-nums">{player.mmss(full.seconds)}</span>
			{#each full.tags.slice(0, 4) as tag (tag)}
				<span class="rounded-full border border-line px-2 py-0.5">{tag}</span>
			{/each}
		</div>

		<div class="glass-panel rounded-xl p-3 grid gap-1 text-[11px] mb-4">
			<div><span class="text-muted">made</span> {full.created_at.replace('T', ' ')}</div>
			<div><span class="text-muted">audio</span> {rate}</div>
			<div><span class="text-muted">seed</span> {full.seed || '—'}</div>
			<div><span class="text-muted">formats</span> {(full.formats ?? []).join(', ')}</div>
		</div>

		{#if full.style}
			<h4 class="text-sm font-bold mb-1">Style</h4>
			<p class="text-xs text-muted leading-relaxed mb-4">{full.style}</p>
		{/if}
		{#if full.lyrics}
			<h4 class="text-sm font-bold mb-2">Lyrics</h4>
			<pre class="whitespace-pre-wrap text-[13px] leading-relaxed text-muted" style="font-family:inherit">{full.lyrics}</pre>
		{/if}
	{:else}
		<p class="text-sm text-muted">Nothing playing yet. Pick a song and its words and details appear here.</p>
	{/if}
</aside>
