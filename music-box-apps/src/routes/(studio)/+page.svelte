<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import SongCard from '$lib/components/SongCard.svelte';
	import { player } from '$lib/domain/player.svelte.js';
	import type { SongRow } from '$lib/db/library.js';

	/**
	 * The listen page: shelves when there is something to shelve, one grid
	 * otherwise, and an honest empty state when the box has no songs at all.
	 */
	let { data } = $props();

	// the dock's play button starts the first song of whatever this page shows
	$effect(() => {
		player.set_page(data.items);
	});

	const heading = $derived(
		data.shape === 'home' ? 'Home' : data.q ? data.title : data.view === 'liked' ? 'Liked' : 'All songs'
	);
	const sorts = [
		['new', 'Newest'],
		['old', 'Oldest'],
		['played', 'Most played'],
		['long', 'Longest'],
		['short', 'Shortest'],
		['title', 'Title'],
		['random', 'Shuffle']
	] as const;

	let renaming = $state(false);
	let new_name = $state('');
	let confirming = $state(false);

	async function rename_playlist() {
		if (!data.playlist || !new_name.trim()) return;
		await fetch(`/api/playlists/${data.playlist.id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ name: new_name })
		});
		renaming = false;
		await invalidateAll();
	}

	async function delete_playlist() {
		if (!data.playlist) return;
		await fetch(`/api/playlists/${data.playlist.id}`, { method: 'DELETE' });
		await invalidateAll();
		goto('/');
	}

	function change_sort(value: string) {
		const p = new URLSearchParams({ view: data.view === 'home' ? 'all' : data.view, sort: value });
		if (data.q) p.set('q', data.q);
		if (data.tag) p.set('tag', data.tag);
		goto(`/?${p}`);
	}
</script>

<header class="px-6 md:px-10 pt-6 md:pt-8 pb-4 flex items-end justify-between gap-4">
	<h1 class="text-4xl md:text-5xl font-extrabold tracking-tight">{heading}</h1>
	<label class="flex items-center gap-2 text-xs text-muted">
		Order
		<select
			class="bg-glasshover border border-line rounded-lg py-1.5 px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent"
			value={data.sort}
			onchange={(e) => change_sort(e.currentTarget.value)}
		>
			{#each sorts as [value, label] (value)}
				<option {value}>{label}</option>
			{/each}
		</select>
	</label>
</header>

<div class="px-6 md:px-10 pb-32">
	{#if data.items.length === 0}
		<div class="glass-panel rounded-2xl p-10 text-center">
			<div class="text-3xl mb-3 text-muted"><i class="ph ph-music-notes-simple"></i></div>
			<p class="text-sm font-semibold">
				{#if data.q}Nothing matches “{data.q}”.
				{:else if data.tag}No songs carry the {data.tag} tag yet.
				{:else if data.view === 'liked'}Nothing liked yet — the heart keeps a song here.
				{:else}No songs yet{/if}
			</p>
			<p class="text-xs text-muted mt-1">Songs made on the three cards appear here.</p>
			<a
				href="/create"
				class="inline-block mt-4 px-5 py-2 rounded-full bg-accent text-white text-sm font-semibold"
			>Make a song</a>
		</div>
	{:else if data.shape === 'home'}
		{#each data.shelves as shelf (shelf.title)}
			{#if shelf.items.length}
				<section class="mb-12">
					<div class="flex items-center justify-between mb-4">
						<div>
							<h2 class="text-sm font-bold text-muted tracking-wide">{shelf.title}</h2>
						</div>
					</div>
					<div class="flex overflow-x-auto snap-x snap-mandatory gap-6 pb-4 no-scrollbar -mx-6 px-6 md:mx-0 md:px-0">
						{#each shelf.items as song (song.id)}
							<SongCard {song} list={shelf.items} wide />
						{/each}
					</div>
				</section>
			{/if}
		{/each}
	{:else}
		<section>
			<div class="flex flex-wrap items-center gap-3 mb-4">
				{#if renaming && data.playlist}
					<input
						bind:value={new_name}
						onkeydown={(e) => e.key === 'Enter' && rename_playlist()}
						class="bg-glasshover border border-line rounded-lg py-1.5 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
					/>
					<button class="text-xs font-semibold text-accent" onclick={rename_playlist}>Save</button>
					<button class="text-xs text-muted" onclick={() => (renaming = false)}>Cancel</button>
				{:else}
					<h2 class="text-lg font-bold">{data.title}</h2>
					<span class="text-xs text-muted">{data.total}</span>
					{#if data.view === 'playlist' && data.playlist}
						<button
							class="text-xs text-muted hover:text-ink"
							onclick={() => {
								new_name = data.playlist.name;
								renaming = true;
							}}>Rename</button
						>
						{#if confirming}
							<button class="text-xs font-semibold text-accent" onclick={delete_playlist}>Really delete it</button>
							<button class="text-xs text-muted" onclick={() => (confirming = false)}>Keep</button>
						{:else}
							<button class="text-xs text-muted hover:text-accent" onclick={() => (confirming = true)}>
								Delete playlist
							</button>
						{/if}
					{/if}
				{/if}
			</div>
			<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 md:gap-6">
				{#each data.items as song (song.id)}
					<SongCard {song} list={data.items} playlist_id={data.view === 'playlist' && data.playlist ? data.playlist.id : 0} />
				{/each}
			</div>
			{#if data.view === 'playlist' && !data.items.length}
				<p class="text-sm text-muted">Nothing in this playlist yet — the + on a card files a song here.</p>
			{/if}
		</section>
	{/if}
</div>
